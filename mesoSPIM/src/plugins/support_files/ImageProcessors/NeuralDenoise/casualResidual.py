import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualBlock2D(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.act1 = nn.LeakyReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)

    def forward(self, x):
        residual = x
        x = self.conv1(x)
        x = self.act1(x)
        x = self.conv2(x)
        return self.act1(x + residual)


class DownBlock(nn.Module):
    def __init__(self, in_ch, out_ch, num_res_blocks=1):
        super().__init__()
        layers = [
            nn.Conv2d(in_ch, out_ch, kernel_size=3, stride=2, padding=1),
            nn.LeakyReLU(inplace=True),
        ]
        for _ in range(num_res_blocks):
            layers.append(ResidualBlock2D(out_ch))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)


class UpBlock(nn.Module):
    def __init__(self, in_ch, skip_ch, out_ch, num_res_blocks=1):
        super().__init__()
        self.conv = nn.Conv2d(in_ch + skip_ch, out_ch, kernel_size=3, padding=1)
        self.act = nn.LeakyReLU(inplace=True)
        self.res_blocks = nn.Sequential(
            *[ResidualBlock2D(out_ch) for _ in range(num_res_blocks)]
        )

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, skip], dim=1)
        x = self.conv(x)
        x = self.act(x)
        x = self.res_blocks(x)
        return x


class CausalLastPlaneDenoiser(nn.Module):
    """
    Causal 2.5D residual U-Net for denoising the LAST plane in a short z-stack.

    Expected input:
        x: (N, D, H, W)      or
           (N, 1, D, H, W)

    Interpretation:
        D = number of planes in the causal context window
        The model predicts a denoised version of x[:, -1, :, :]

    Design:
        - Treat z-planes as channels -> use Conv2d, not Conv3d
        - Residual prediction: output = noisy_last - predicted_noise
        - Much faster / lower-latency than small 3D encoder-decoders
    """
    def __init__(self, in_planes=5, base_ch=32, out_activation=None):
        super().__init__()
        self.in_planes = in_planes
        self.out_activation = out_activation

        # Encoder
        self.in_conv = nn.Sequential(
            nn.Conv2d(in_planes, base_ch, kernel_size=3, padding=1),
            nn.LeakyReLU(inplace=True),
            ResidualBlock2D(base_ch),
        )

        self.down1 = DownBlock(base_ch, base_ch * 2, num_res_blocks=1)
        self.down2 = DownBlock(base_ch * 2, base_ch * 4, num_res_blocks=1)

        # Bottleneck
        self.bottleneck = nn.Sequential(
            ResidualBlock2D(base_ch * 4),
            ResidualBlock2D(base_ch * 4),
        )

        # Decoder
        self.up1 = UpBlock(base_ch * 4, base_ch * 2, base_ch * 2, num_res_blocks=1)
        self.up2 = UpBlock(base_ch * 2, base_ch, base_ch, num_res_blocks=1)

        # Noise prediction head
        self.noise_head = nn.Conv2d(base_ch, 1, kernel_size=3, padding=1)

    def _normalize_input_shape(self, x):
        """
        Accept:
            (N, D, H, W)
            (N, 1, D, H, W)

        Return:
            x_2d: (N, D, H, W)   where D is treated as channels
            noisy_last: (N, 1, H, W)
        """
        if x.ndim == 5:
            if x.shape[1] != 1:
                raise ValueError(
                    f"For 5D input expected shape (N,1,D,H,W), got {tuple(x.shape)}"
                )
            x = x[:, 0]  # -> (N, D, H, W)
        elif x.ndim != 4:
            raise ValueError(
                f"Expected input shape (N,D,H,W) or (N,1,D,H,W), got {tuple(x.shape)}"
            )

        if x.shape[1] != self.in_planes:
            raise ValueError(
                f"Model was initialized with in_planes={self.in_planes}, "
                f"but got input with D={x.shape[1]} planes"
            )

        noisy_last = x[:, -1:, :, :]  # last plane as target/reference
        return x, noisy_last

    def forward(self, x):
        x, noisy_last = self._normalize_input_shape(x)

        # Encoder
        s0 = self.in_conv(x)     # (N, base, H, W)
        s1 = self.down1(s0)      # (N, 2*base, H/2, W/2)
        s2 = self.down2(s1)      # (N, 4*base, H/4, W/4)

        # Bottleneck
        b = self.bottleneck(s2)

        # Decoder
        x = self.up1(b, s1)
        x = self.up2(x, s0)

        # Predict noise in last plane, then subtract it
        pred_noise = self.noise_head(x)
        denoised = noisy_last - pred_noise

        if self.out_activation is not None:
            denoised = self.out_activation(denoised)

        return denoised