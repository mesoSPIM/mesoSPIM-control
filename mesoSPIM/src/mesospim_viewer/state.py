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

    Brightness rides in the alpha as well as the colour, and the layers are
    composited over one another rather than added: a dim pixel lets the channel
    beneath show through, a bright one covers it, so channels mix without the
    sum ever clipping to white, and two tiles of one acquisition that overlap
    do not add up to a bright seam along the join. The alpha never quite
    reaches zero inside a tile, so a transparent ground still shows acquired
    black as black.
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
            "  emitRGBA(vec4(color * value, max(value, 1.0 / 255.0)));",
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
        first = self.placements[0].store
        sources = [source_json(placement) for placement in self.placements]
        return [
            {
                "type": "image",
                "name": channel_layer_name(self.name, channel),
                "source": sources,
                # Which channel of the store this layer reads: the engine keeps
                # the c axis as a per-layer dimension, pinned here.
                "localPosition": [index],
                "shader": channel_shader(channel),
                # Composited over one another by their brightness (see channel_shader).
                "blend": "default",
                "opacity": 1.0,
                "visible": self.visible and channel.active,
                "_revision": self.revision,
            }
            for index, channel in enumerate(channels_for(first, self.channels))
        ]


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
