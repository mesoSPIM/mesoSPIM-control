"""Turning a few placed stores into a neuroglancer state.

Everything here is a pure function from plain data to the JSON neuroglancer
already understands. An acquisition is a :class:`Layer` here and becomes one
engine layer *per channel*, all sharing the same sources and composited on
the graphics card by their brightness. One layer per channel is how
neuroglancer's own multichannel setup arranges an OME-Zarr, and the only
arrangement that reads a store whose chunks hold one channel each: the engine
reads every channel of a voxel from one chunk, so a channel dimension across
chunks draws nothing. Each source is a neuroglancer source with a
``transform`` carrying its shift. Nothing is invented that the engine does not
have a word for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .omezarr import Channel, Store

# False colours for channels the store does not colour itself. One channel is
# white; several take turns around a palette that reads well when overlaid.
PALETTE = ("#00ff66", "#ff33ff", "#33ccff", "#ffbf1a", "#ff4d4d", "#a0a0ff", "#ffffff")

# False colours by excitation wavelength in nanometres, the same the mesoSPIM
# OME-Zarr writer puts into a store's omero block.
WAVELENGTH_COLOURS = {
    "405": "#5a73ff",
    "488": "#00ff66",
    "561": "#ffbf1a",
    "640": "#ff33ff",
    "647": "#ff33ff",
    "785": "#ffffff",
}

LAYOUTS = ("xy", "yz", "xz", "4panel", "3d", "xy-3d", "yz-3d", "xz-3d")


@dataclass(frozen=True)
class Placement:
    """One store inside a layer, and where it goes.

    ``offset`` shifts the store from where its own metadata puts it; ``origin``
    places the store's first voxel at an absolute coordinate instead, ignoring
    the metadata's translation. Both are keyed by axis name and measured in the
    axis's own unit as written in the store (micrometres for a mesoSPIM tile).
    """

    store: Store
    url: str
    offset: dict[str, float] = field(default_factory=dict)
    origin: dict[str, float] | None = None
    # For a store that holds one channel of its acquisition, when a writer saves one
    # store per tile *and* channel: which channel it is, as its own metadata says.
    # Stores of different channels then feed different channel layers.
    channel: Channel | None = None

    def shift_voxels(self, index: int) -> float:
        axis = self.store.axes[index]
        shift = self.offset.get(axis.name, 0.0)
        if self.origin is not None and axis.name in self.origin:
            shift += self.origin[axis.name] - self.store.translation[index]
        return shift / self.store.scale[index]


def source_json(placement: Placement) -> dict:
    """A neuroglancer data source: the address, and a transform when shifted.

    The transform is the identity with the shift in its translation column, in
    voxels of the output space, whose dimensions repeat the store's own axes
    and scales in SI so nothing is stretched. The channel axis keeps the
    engine's local-dimension name (``c'``): each channel layer pins it.
    """
    store = placement.store
    shifts = [placement.shift_voxels(i) for i in range(len(store.axes))]
    if not any(shifts):
        return {"url": placement.url}
    rank = len(store.axes)
    output: dict[str, list] = {}
    for i, axis in enumerate(store.axes):
        if axis.is_channel:
            output[f"{axis.name}'"] = [1, ""]
            continue
        unit, factor = axis.si
        output[axis.name] = [store.scale[i] * factor if unit else 1, unit]
    matrix = [[1.0 if r == c else 0.0 for c in range(rank)] + [shifts[r]] for r in range(rank)]
    return {"url": placement.url, "transform": {"outputDimensions": output, "matrix": matrix}}


def channels_for(store: Store, override: list[Channel] | None = None) -> list[Channel]:
    """The channels a layer shows, one per index along the store's channel axis.

    What the store declares wins; what it leaves out is filled in with a label,
    a colour from the palette and no window, so the engine's own default range
    applies until somebody sets one.
    """
    count = store.channel_count
    declared = list(override if override is not None else store.channels)[:count]
    filled = []
    for index in range(count):
        given = declared[index] if index < len(declared) else Channel(label=f"channel {index}")
        color = given.color or (PALETTE[-1] if count == 1 else PALETTE[index % (len(PALETTE) - 1)])
        filled.append(
            Channel(
                label=given.label,
                color=color,
                window=given.window,
                limits=given.limits,
                active=given.active,
            )
        )
    return filled


def _glsl_number(value: float) -> str:
    text = repr(float(value))
    return text if "e" not in text and "." in text else f"{value:.6g}"


def channel_shader(channel: Channel) -> str:
    """One channel's program, with the store's window and colour as the controls'
    starting values.

    Brightness rides in the alpha, and the layers are composited over one
    another rather than added: a dim pixel lets the channel beneath show
    through, a bright one covers it, so channels mix without the sum ever
    clipping to white, and two tiles of one acquisition that overlap do not add
    up to a bright seam along the join. The colour itself is emitted at full
    strength: the engine multiplies it by the alpha when it lays the pixel over
    the picture, so multiplying it here as well would square the brightness.
    The alpha never quite reaches zero inside a tile, so a transparent ground
    still shows acquired black as black.
    """
    parameters = []
    if channel.window:
        lo, hi = channel.window
        parameters.append(f"range=[{_glsl_number(lo)}, {_glsl_number(hi)}]")
    if channel.limits:
        lo, hi = channel.limits
        parameters.append(f"window=[{_glsl_number(lo)}, {_glsl_number(hi)}]")
    return "\n".join(
        [
            f"#uicontrol invlerp contrast({', '.join(parameters)})",
            f'#uicontrol vec3 color color(default="{channel.color}")',
            "void main() {",
            "  float value = contrast();",
            "  emitRGBA(vec4(color, max(value, 1.0 / 255.0)));",
            "}",
            "",
        ]
    )


def channel_layer_name(layer: str, channel: Channel) -> str:
    return f"{layer} · {channel.label}"


@dataclass
class Layer:
    """One acquisition: a name, its placed stores and its channels.

    It becomes one engine layer per channel. ``revision`` is bumped when a store
    on disk has grown, so the page re-reads it; the page strips it before the
    engine sees the layer.
    """

    name: str
    placements: list[Placement] = field(default_factory=list)
    channels: list[Channel] | None = None
    visible: bool = True
    revision: int = 0

    def to_json(self) -> list[dict]:
        if not self.placements:
            raise ValueError(f"layer {self.name!r} has no stores")
        if any(placement.channel is not None for placement in self.placements):
            return self._split_channels_json()
        first = self.placements[0].store
        sources = [source_json(placement) for placement in self.placements]
        return [
            self._engine_layer(channel, sources, index if first.channel_axis is not None else None)
            for index, channel in enumerate(channels_for(first, self.channels))
        ]

    def _split_channels_json(self) -> list[dict]:
        """One engine layer per channel, each reading only the stores of that channel.

        For acquisitions saved as one store per tile and channel. Stores in order of
        arrival; channels in the order they were first seen, coloured by wavelength
        where the label is one (``"488"``), else from the palette.
        """
        groups: dict[str, tuple[Channel, list[Placement]]] = {}
        for placement in self.placements:
            channel = placement.channel or Channel(label="channel 0")
            groups.setdefault(channel.label, (channel, []))[1].append(placement)
        layers = []
        for index, (channel, placements) in enumerate(groups.values()):
            color = (
                channel.color
                or WAVELENGTH_COLOURS.get(channel.label.split()[0])
                or (PALETTE[-1] if len(groups) == 1 else PALETTE[index % (len(PALETTE) - 1)])
            )
            shown = Channel(
                label=channel.label,
                color=color,
                window=channel.window,
                limits=channel.limits,
                active=channel.active,
            )
            sources = [source_json(placement) for placement in placements]
            # A store that has a channel axis of its own holds this channel at index 0.
            pinned = 0 if placements[0].store.channel_axis is not None else None
            layers.append(self._engine_layer(shown, sources, pinned))
        return layers

    def _engine_layer(self, channel: Channel, sources: list[dict], pinned: int | None) -> dict:
        layer = {
            "type": "image",
            "name": channel_layer_name(self.name, channel),
            "source": sources,
            "shader": channel_shader(channel),
            # Composited over one another by their brightness (see channel_shader).
            "blend": "default",
            "opacity": 1.0,
            "visible": self.visible and channel.active,
            "_revision": self.revision,
        }
        if pinned is not None:
            # Which channel of the store this layer reads: the engine keeps the c
            # axis as a per-layer dimension, pinned here. A store without a c axis
            # has nothing to pin.
            layer["localPosition"] = [pinned]
        return layer


def state_json(layers: list[Layer], *, layout: str = "xy") -> dict:
    """The whole scene as neuroglancer state, ready for ``viewer.state.restoreState``."""
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, not {layout!r}")
    return {
        "layers": [engine_layer for layer in layers for engine_layer in layer.to_json()],
        "layout": layout,
        # Left to itself the engine draws the first three axes it meets, which
        # with ``t`` in front is time against depth. The picture is x, y, z.
        "displayDimensions": ["x", "y", "z"],
    }
