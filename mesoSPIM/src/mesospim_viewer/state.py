"""Turning a few placed stores into what the page shows.

Everything here is a pure function from plain data to JSON. An acquisition is a
:class:`Layer` here and becomes one engine layer *per channel*, all sharing the
same sources and composited on the graphics card by their brightness. One layer
per channel is how neuroglancer's own multichannel setup arranges an OME-Zarr,
and the only arrangement that reads a store whose chunks hold one channel each:
the engine reads every channel of a voxel from one chunk, so a channel dimension
across chunks draws nothing. Each source is a neuroglancer source with a
``transform`` carrying its shift.

Each engine layer is described the way neuroglancer itself would write it
(``type``, ``source``, ``shader``, ``shaderControls``...), so
:func:`engine_state` is a state stock neuroglancer restores. The page is given
the same description with three things added, each under a name beginning with
an underscore: which acquisition and channel the layer belongs to, and a
lasting name for every source. With those the page brings a layer into line
*in place* -- one source added, one read again, one control moved -- instead of
building it anew, so a tile landing never blanks the picture or resets a
control (``source/src/layers.js``).

The shader's text is the same for every channel, and what differs -- the
contrast window, the colour -- travels as the values of its controls. A window
measured from the data later is then a control moving, not a new program.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

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

SEPARATOR = " · "  # between acquisition and channel in an engine layer's name


@dataclass(frozen=True)
class Placement:
    """One store inside a layer, and where it goes.

    ``offset`` shifts the store from where its own metadata puts it; ``origin``
    places the store's first voxel at an absolute coordinate instead, ignoring
    the metadata's translation. Both are keyed by axis name and measured in the
    axis's own unit as written in the store (micrometres for a mesoSPIM tile).

    ``id`` names the source for as long as it is shown, whatever address the
    page reads it at: the address changes when the store's shape has (a time
    point appended), and the page then reads that one source again.
    """

    store: Store
    url: str
    offset: dict[str, float] = field(default_factory=dict)
    origin: dict[str, float] | None = None
    # For a store that holds one channel of its acquisition, when a writer saves one
    # store per tile *and* channel: which channel it is, as its own metadata says.
    # Stores of different channels then feed different channel layers.
    channel: Channel | None = None
    id: str = ""

    def shift_voxels(self, index: int) -> float:
        axis = self.store.axes[index]
        shift = self.offset.get(axis.name, 0.0)
        if self.origin is not None and axis.name in self.origin:
            shift += self.origin[axis.name] - self.store.translation[index]
        return shift / self.store.scale[index]


@dataclass(frozen=True)
class Preview:
    """A stack the microscope is acquiring right now, shown from memory.

    One channel of one tile at one time point (see ``live.py``): a source of
    its own in that channel's layer until the stack is on disk.
    """

    id: str
    url: str
    channel: Channel
    index: int = 0  # which channel of the preview's own store it is
    voxel_um: tuple[float, float, float] | None = None  # of the stack itself: z, y, x
    timed: bool = True
    # The stack is on disk now and the tile there is taking over: the page lets
    # the preview go as soon as the tile's picture is up.
    retiring: bool = False


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
    a colour (by wavelength where the label is one, else from the palette) and
    no window, so the contrast is set from the data.
    """
    count = store.channel_count
    declared = list(override if override is not None else store.channels)[:count]
    filled = []
    for index in range(count):
        given = declared[index] if index < len(declared) else Channel(label=f"channel {index}")
        filled.append(replace(given, color=given.color or default_colour(given.label, index, count)))
    return filled


def default_colour(label: str, index: int, count: int) -> str:
    by_wavelength = WAVELENGTH_COLOURS.get(label.split()[0]) if label.split() else None
    if by_wavelength:
        return by_wavelength
    return PALETTE[-1] if count == 1 else PALETTE[index % (len(PALETTE) - 1)]


# One program for every channel. The colour is emitted already scaled by the
# brightness, and the page's engine mixes what it draws by taking the brighter
# of the two, colour by colour (scripts/neuroglancer.mjs): a structure lit in
# two channels shows in both colours at once instead of the upper channel
# hiding the lower, the mix never clips to white, and two tiles of one
# acquisition that overlap do not add up to a bright seam along the join. The
# alpha follows the brightness and never quite reaches zero inside a tile, so
# on a transparent ground a tile is never wholly clear.
SHADER = "\n".join(
    [
        "#uicontrol invlerp contrast",
        '#uicontrol vec3 color color(default="#ffffff")',
        "void main() {",
        "  float value = contrast();",
        "  emitRGBA(vec4(color * value, max(value, 1.0 / 255.0)));",
        "}",
        "",
    ]
)


def channel_shader(channel: Channel | None = None) -> str:
    """The channel program: the same for every channel (see :func:`channel_controls`)."""
    return SHADER


def channel_controls(channel: Channel) -> dict:
    """The starting values of the program's controls for one channel.

    ``range`` is the contrast window (black and white point), ``window`` the
    span the histogram shows. A channel without a window says nothing about
    its contrast, and the page then sets it from what is on screen.
    """
    controls: dict = {"color": channel.color or PALETTE[-1]}
    contrast = {}
    if channel.window:
        low, high = float(channel.window[0]), float(channel.window[1])
        contrast["range"] = [low, high]
        # The span the histogram shows: the store's own limits where it gives
        # them, else the window with room on both sides -- on the whole range of
        # the data type a camera's histogram is a sliver at the left edge.
        across = high - low
        contrast["window"] = [max(0.0, low - across * 0.5), high + across]
    if channel.limits and channel.limits != (0.0, 65535.0):
        contrast["window"] = [float(channel.limits[0]), float(channel.limits[1])]
    if contrast:
        controls["contrast"] = contrast
    return controls


def channel_layer_name(layer: str, channel: Channel) -> str:
    return f"{layer}{SEPARATOR}{channel.label}"


@dataclass
class Layer:
    """One acquisition: a name, its placed stores and its channels.

    It becomes one engine layer per channel.

    ``measured`` holds, by channel label, the contrast window measured from the
    data for a channel that was given none (see :func:`omezarr.sample_window`).
    A window given by the store or by the caller always comes first.

    ``previews`` are stacks being acquired right now, shown from memory.
    """

    name: str
    placements: list[Placement] = field(default_factory=list)
    channels: list[Channel] | None = None
    visible: bool = True
    measured: dict[str, tuple[float, float]] = field(default_factory=dict)
    previews: list[Preview] = field(default_factory=list)
    # Whether the page keeps setting the contrast from what is on screen, until
    # the operator sets it themselves: for an acquisition that is being written,
    # whose brightness nobody knows yet.
    auto: bool = False

    @property
    def split(self) -> bool:
        """Whether the acquisition is saved as one store per tile *and* channel."""
        return any(placement.channel is not None for placement in self.placements)

    def unwindowed(self, placement: Placement) -> list[tuple[str, int | None]]:
        """The channels of this layer that ``placement``'s store holds and that have no
        contrast window yet: each as its label and its index along the store's channel
        axis (None for a store without one)."""
        store = placement.store
        if placement.channel is not None:
            label = placement.channel.label
            shown = next(p.channel for p in self.placements if p.channel and p.channel.label == label)
            if shown.window is not None or label in self.measured:
                return []
            return [(label, 0 if store.channel_axis is not None else None)]
        wanting = []
        for index, channel in enumerate(channels_for(self.placements[0].store, self.channels)):
            if index >= store.channel_count or channel.window is not None:
                continue
            if channel.label not in self.measured:
                wanting.append((channel.label, index if store.channel_axis is not None else None))
        return wanting

    def _windowed(self, channel: Channel) -> Channel:
        if channel.window is not None or channel.label not in self.measured:
            return channel
        return replace(channel, window=self.measured[channel.label])

    def shown_channels(self) -> list[tuple[Channel, list[Placement], int | None]]:
        """Each channel with the stores that feed it and the index it reads of them.

        Channels in the order the stores declare them; for one store per tile
        and channel, in the order they were first seen. A channel that only a
        preview has brought so far is listed too, without stores.
        """
        found: list[tuple[Channel, list[Placement], int | None]] = []
        if self.split:
            groups: dict[str, tuple[Channel, list[Placement]]] = {}
            for placement in self.placements:
                channel = placement.channel or Channel(label="channel 0")
                groups.setdefault(channel.label, (channel, []))[1].append(placement)
            for index, (channel, placements) in enumerate(groups.values()):
                shown = replace(
                    channel, color=channel.color or default_colour(channel.label, index, len(groups))
                )
                # A store that has a channel axis of its own holds this channel at index 0.
                pinned = 0 if placements[0].store.channel_axis is not None else None
                found.append((shown, placements, pinned))
        elif self.placements:
            first = self.placements[0].store
            for index, channel in enumerate(channels_for(first, self.channels)):
                pinned = index if first.channel_axis is not None else None
                found.append((channel, list(self.placements), pinned))
        known = {channel.label for channel, _, _ in found}
        for preview in self.previews:
            if preview.channel.label in known:
                continue
            known.add(preview.channel.label)
            index = len(found)
            colour = preview.channel.color or default_colour(preview.channel.label, index, index + 1)
            found.append((replace(preview.channel, color=colour), [], None))
        return found

    def to_json(self) -> list[dict]:
        if not self.placements and not self.previews:
            raise ValueError(f"layer {self.name!r} has no stores")
        layers = []
        for channel, placements, pinned in self.shown_channels():
            channel = self._windowed(channel)
            sources = [source_json(placement) for placement in placements]
            ids = [placement.id for placement in placements]
            retiring = []
            for preview in self.previews:
                if preview.channel.label == channel.label:
                    sources.append({"url": preview.url})
                    ids.append(preview.id)
                    if preview.retiring:
                        retiring.append(preview.id)
                    if pinned is None:
                        # A preview has a channel axis of its own (live.py); a layer
                        # whose stores have none reads the preview at its index.
                        pinned = preview.index
            layer = {
                "type": "image",
                "name": channel_layer_name(self.name, channel),
                "source": sources,
                "shader": SHADER,
                "shaderControls": channel_controls(channel),
                # Composited over one another by their brightness (see SHADER).
                "blend": "default",
                "opacity": 1.0,
                "visible": self.visible and channel.active,
                "_auto": self.auto or channel.window is None,
                "_acquisition": self.name,
                "_channel": channel.label,
                "_sources": ids,
                "_retiring": retiring,
            }
            if pinned is not None:
                # Which channel of the store this layer reads: the engine keeps the c
                # axis as a per-layer dimension, pinned here. A store without a c axis
                # has nothing to pin.
                layer["localPosition"] = [pinned]
            layers.append(layer)
        return layers


def state_json(layers: list[Layer], *, layout: str = "xy") -> dict:
    """The whole scene as the page takes it: neuroglancer layers, each with the page's
    three additions (see the module's description)."""
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, not {layout!r}")
    return {
        "layers": [
            engine_layer
            for layer in layers
            if layer.placements or layer.previews
            for engine_layer in layer.to_json()
        ],
        "layout": layout,
        # Left to itself the engine draws the first three axes it meets, which
        # with ``t`` in front is time against depth. The picture is x, y, z.
        "displayDimensions": ["x", "y", "z"],
        "dimensions": dimensions(layers),
    }


def dimensions(layers: list[Layer]) -> dict[str, list]:
    """The space the picture is drawn in: x, y, z at the finest voxel size shown, and t.

    Left to itself the engine takes the voxel size of whichever source it
    loads first, and the depth slider then steps in that source's planes. Said
    here, a step is one plane of the finest stack whatever arrived first.
    """
    finest: dict[str, float] = {}
    timed = False
    for layer in layers:
        for placement in layer.placements:
            store = placement.store
            for index, axis in enumerate(store.axes):
                if axis.name == "t":
                    timed = True
                    continue
                unit, factor = axis.si
                if axis.is_channel or unit != "m":
                    continue
                size = store.scale[index] * factor
                if size > 0 and (axis.name not in finest or size < finest[axis.name]):
                    finest[axis.name] = size
        for preview in layer.previews:
            if preview.voxel_um is None:
                continue
            timed = timed or preview.timed
            for name, size in zip(("z", "y", "x"), preview.voxel_um):
                size *= 1e-6
                if size > 0 and (name not in finest or size < finest[name]):
                    finest[name] = size
    if not {"x", "y", "z"} <= set(finest):
        return {}
    space: dict[str, list] = {name: [finest[name], "m"] for name in ("x", "y", "z")}
    if timed:
        space["t"] = [1, ""]
    return space


def engine_state(scene: dict) -> dict:
    """The scene as stock neuroglancer restores it: the page's additions taken out."""
    plain = {key: value for key, value in scene.items() if key != "dimensions" or value}
    plain["layers"] = [
        {key: value for key, value in layer.items() if not key.startswith("_")}
        for layer in scene.get("layers", [])
    ]
    return plain
