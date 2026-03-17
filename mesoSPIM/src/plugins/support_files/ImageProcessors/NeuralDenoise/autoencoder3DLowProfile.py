import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, kernel_size=3, padding=1),
            nn.LeakyReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class Autoencoder(nn.Module):
    """
    Option A implemented:
        - 3D encoder/decoder over a small z-stack
        - pool only in XY, never in Z
        - final prediction is made from the LAST z-plane features only
    """
    def __init__(self):
        super().__init__()

        # Encoder
        self.enc_in = ConvBlock(1, 4)
        self.enc_blocks = nn.ModuleList([
            ConvBlock(4, 4),
            ConvBlock(4, 4),
            ConvBlock(4, 4),
            ConvBlock(4, 4),
            ConvBlock(4, 4),
            ConvBlock(4, 4),
        ])

        # Pool only spatially, not across z
        self.pool = nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2))

        # Decoder
        self.dec_blocks = nn.ModuleList([
            ConvBlock(8, 8),
            ConvBlock(12, 8),
            ConvBlock(12, 8),
            ConvBlock(12, 8),
            ConvBlock(9, 6),
        ])

        # ----- Option A: center-plane readout -----
        # Keep the same overall structure, but instead of collapsing depth
        # with a mean, produce 3D features, extract the center plane, and
        # finish with a small 2D head.
        self.out1 = ConvBlock(6, 8)
        self.out2 = nn.Conv3d(8, 8, kernel_size=3, padding=1)
        self.final2d = nn.Conv2d(8, 1, kernel_size=3, padding=1)

        # ------------------------------------------------------------------
        # Option B (commented idea only): learned weighted fusion across depth
        #
        # If you want to test Option B instead of Option A, replace the
        # Option A output head above with something like:
        #
        # self.out1 = ConvBlock(6, 8)
        # self.out_img = nn.Conv3d(8, 1, kernel_size=3, padding=1)
        # self.weight_head = nn.Conv3d(8, 1, kernel_size=1)
        #
        # Then in forward():
        #
        # x = self.out1(x)                      # (N, 8, D, H, W)
        # img = self.out_img(x)                 # (N, 1, D, H, W)
        # w = self.weight_head(x)               # (N, 1, D, H, W)
        # w = torch.softmax(w, dim=2)           # normalize across z
        # x = (img * w).sum(dim=2)              # (N, 1, H, W)
        # return x
        #
        # This is more flexible than a mean and still works with variable D.
        # ------------------------------------------------------------------

    def _upsample_to_skip(self, x, skip):
        """
        Upsample x so spatial/depth dims exactly match skip.
        This avoids odd-size mismatches caused by pooling floors.
        """
        return F.interpolate(x, size=skip.shape[2:], mode="nearest")

    def forward(self, x):
        # Accept either:
        #   (N, D, H, W)
        # or
        #   (N, 1, D, H, W)
        if x.ndim == 4:
            x = x.unsqueeze(1)  # -> (N, 1, D, H, W)
        elif x.ndim != 5:
            raise ValueError(
                f"Expected input shape (N,D,H,W) or (N,1,D,H,W), got {tuple(x.shape)}"
            )

        # if x.shape[2] % 2 == 0:
        #     raise ValueError(
        #         f"Expected an odd number of z-planes so there is a center slice, got D={x.shape[2]}"
        #     )

        skips = [x]

        # Encode
        x = self.enc_in(x)
        x = self.enc_blocks[0](x)
        x = self.pool(x)
        skips.append(x)

        # for block in self.enc_blocks[1:4]:
        #     x = block(x)
        #     x = self.pool(x)
        #     skips.append(x)

        x = self.enc_blocks[4](x)
        x = self.pool(x)
        x = self.enc_blocks[5](x)

        # Decode
        skip = skips.pop()
        x = self._upsample_to_skip(x, skip)
        x = torch.cat([x, skip], dim=1)
        x = self.dec_blocks[0](x)

        # skip = skips.pop()
        # x = self._upsample_to_skip(x, skip)
        # x = torch.cat([x, skip], dim=1)
        # x = self.dec_blocks[1](x)
        #
        # skip = skips.pop()
        # x = self._upsample_to_skip(x, skip)
        # x = torch.cat([x, skip], dim=1)
        # x = self.dec_blocks[2](x)
        #
        # skip = skips.pop()
        # x = self._upsample_to_skip(x, skip)
        # x = torch.cat([x, skip], dim=1)
        # x = self.dec_blocks[3](x)

        skip = skips.pop()
        x = self._upsample_to_skip(x, skip)
        x = torch.cat([x, skip], dim=1)
        x = self.dec_blocks[4](x)

        # Option A: center-plane readout
        x = self.out1(x)                  # (N, 8, D, H, W)
        x = self.out2(x)                  # (N, 8, D, H, W)

        # center_idx = x.shape[2] // 2
        x = x[:, :, -1, :, :]     # (N, 8, H, W)

        x = self.final2d(x)               # (N, 1, H, W)
        return x


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Autoencoder().to(device)

    # odd H/W test
    x = torch.randn(1, 3, 187, 243, device=device)
    y = model(x)
    print("x shape:", x.shape)
    print("y shape:", y.shape)