"""The one object a control application holds: a viewer it can put stores in.

    from mesoSPIM.src.mesospim_viewer import Viewer

    view = Viewer()
    view.start()                                   # a local address
    view.add("run/tile_0.ome.zarr", layer="overview", offset={"x": 0})
    view.add("run/tile_1.ome.zarr", layer="overview", offset={"x": 1800})
    widget = view.qt_widget()                      # or view.open_in_browser()

Every call that changes what is shown publishes the scene to the page, and the
page brings its layers into line in place: a tile that lands is one source
added, nothing else is touched, so the picture never blanks and whatever the
operator has adjusted stays as they left it.

A store the microscope is still writing is not read again as a whole. The
caller says which files have landed (:meth:`Viewer.landed`, which ``watch.py``
does from a look at the disk), and the page reads exactly those.
"""

from __future__ import annotations

import threading
import webbrowser
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .omezarr import Channel, Store, read_store, sample_window
from .server import ViewServer
from .state import LAYOUTS, Layer, Placement, Preview, engine_state, state_json


def _measure(layer: Layer, placement: Placement) -> None:
    """Measure a contrast window, from this store's data, for each channel of the
    layer it holds that has none yet."""
    for label, index in layer.unwindowed(placement):
        window = sample_window(placement.store, index)
        if window is not None:
            layer.measured[label] = window


# The built page lives inside the package (source/ builds into it), so an
# installed copy of the package carries its page.
PAGE_DIR = Path(__file__).resolve().parent / "build"

# How the page dresses the engine: with neuroglancer's own panels ("full"),
# with our panel on the right and the sliders on the picture ("simple"), or as
# nothing but the picture for a host that draws its own controls ("bare").
UI = ("full", "simple", "bare")


def _si_factor(unit: str) -> float:
    """From the SI base unit to the unit the API speaks: micrometres and seconds."""
    return 1e6 if unit == "m" else 1.0


class Viewer:
    """A neuroglancer page served locally, driven from Python."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        page_dir: str | Path | None = None,
        transparent: bool = False,
        ui: str = "full",
        layout: str = "xy",
    ) -> None:
        if ui not in UI:
            raise ValueError(f"ui must be one of {UI}")
        if layout not in LAYOUTS:
            raise ValueError(f"layout must be one of {LAYOUTS}")
        self._host = host
        self._port = port
        self._page_dir = Path(page_dir) if page_dir else PAGE_DIR
        self._layers: dict[str, Layer] = {}
        # How often each store's shape has changed while shown: the count is part
        # of the address the page reads the store at (see _url_for).
        self._revisions: dict[Path, int] = {}
        self._previews = 0
        self._layout = layout
        self._ui = {"transparent": transparent, "chrome": ui}
        self._lock = threading.RLock()
        self._stopped = False
        self._server: ViewServer | None = None
        self._thread: threading.Thread | None = None

    # -- lifetime --------------------------------------------------------------

    def start(self) -> str:
        """Start serving and return the page's address."""
        with self._lock:
            if self._server is None and self._stopped:
                raise RuntimeError("the viewer was stopped")
            if self._server is None:
                page = self._page_dir if (self._page_dir / "index.html").is_file() else None
                self._server = ViewServer(self._host, self._port, page)
                self._server.scene.ui = dict(self._ui)
                self._thread = threading.Thread(
                    target=self._server.serve_forever, name="mesospim-view", daemon=True
                )
                self._thread.start()
                self._publish()
            return self._server.url

    def stop(self) -> None:
        """Stop serving, for good: a stopped viewer is not started again."""
        with self._lock:
            self._stopped = True
            server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()

    @property
    def url(self) -> str:
        return self.start()

    @property
    def page_built(self) -> bool:
        return (self._page_dir / "index.html").is_file()

    # -- what is shown ---------------------------------------------------------

    def add(
        self,
        path: str | Path,
        *,
        layer: str | None = None,
        offset: dict[str, float] | None = None,
        origin: dict[str, float] | None = None,
        channels: list[str] | list[Channel] | None = None,
        colours: list[str] | None = None,
        window: tuple[float, float] | None = None,
        visible: bool = True,
        channel: str | Channel | None = None,
        measure: bool = True,
    ) -> str:
        """Show an OME-Zarr store, and return the name of the layer it joined.

        A store joins the layer called ``layer``; several positions of one
        acquisition share a layer and a set of channel controls, and each is
        placed by its own metadata plus ``offset`` (or at ``origin``), in the
        store's own units. ``channels``, ``colours`` and ``window`` override what
        the store declares about its channels; the first store in a layer
        decides these for the layer.

        ``channel`` is for a store that holds just one channel of its acquisition,
        when a writer saves one store per tile and channel: it names that channel
        (``"488"``, or a :class:`Channel`). The layer then shows one channel row
        per name, each made of the stores given that name.

        A channel that is given no contrast window, by the store or here, gets
        one from its data: from the first store of the layer that holds any
        data yet (see :func:`~.omezarr.sample_window`). It is set once and then
        left alone, so the picture does not change its brightness while tiles
        land.

        ``measure=False`` leaves that to the page, which sets the contrast of
        such a channel from what is on screen: for a store that is being written.

        Showing a store that is already shown reads its description again. If
        its shape has changed the page reads that one source afresh; if not,
        nothing reaches the page at all.
        """
        store = read_store(path)
        name = layer or store.name
        if isinstance(channel, str):
            channel = Channel(label=channel)
        declared = self._channels(store, channels, colours, window)
        key = self._register(store)  # starts the server, before the layer is half-made
        with self._lock:
            held = self._layers.get(name)
            if held is None:
                held = Layer(name=name, channels=declared, visible=visible)
                self._layers[name] = held
            elif declared is not None and held.channels is None:
                held.channels = declared
            at = next(
                (i for i, p in enumerate(held.placements) if p.store.path == store.path), None
            )
            if at is not None and held.placements[at].store.shape != store.shape:
                # The same store with another shape -- a time point was appended,
                # or a stack was cut short -- so the page must read its
                # description afresh: under a new address, since the engine keeps
                # what it read under the old one. Only this source is read again;
                # it keeps its place among the others. Chunks that land in a
                # store of the same shape need none of this: see landed().
                self._revisions[store.path] = self._revisions.get(store.path, 0) + 1
            placement = Placement(
                store=store,
                url=self._store_url(key, store, self._revisions.get(store.path, 0)),
                offset=dict(offset or {}),
                origin=origin,
                channel=channel,
                id=f"store-{key}",
            )
            if at is None:
                held.placements.append(placement)
            else:
                held.placements[at] = placement
            if measure:
                _measure(held, placement)
            self._publish()
        return name

    def refresh(self, layer: str | None = None) -> None:
        """Read the stores of one layer, or of all, from disk again.

        For stores written by something that does not say what it wrote: every
        store's description is read again (a changed shape is taken in as in
        :meth:`add`), and the page reads again every chunk it found missing.
        Adjustments the operator made are kept.
        """
        with self._lock:
            for name, held in list(self._layers.items()):
                if layer is not None and name != layer:
                    continue
                for placement in list(held.placements):
                    self.add(
                        placement.store.path,
                        layer=name,
                        offset=placement.offset,
                        origin=placement.origin,
                        channel=placement.channel,
                    )
                    self.landed(placement.store.path)

    def landed(self, path: str | Path, files: list[str] | None = None) -> None:
        """Say that chunk files of a store that is shown have landed on disk.

        ``files`` are paths below the store's folder, with ``/`` (``"0/c/0/1/5/3/2"``);
        the page reads again exactly the chunks that come from them, and leaves
        every chunk it already drew where it is. Without ``files``, every chunk the
        page found missing is asked for again.
        """
        server = self._server
        if server is None:
            return
        key = server.stores.key_of(Path(path).expanduser())
        if key is None:
            return
        event: dict = {"type": "landed", "store": f"data/{key}"}
        if files is not None:
            if not files:
                return
            event["files"] = list(files)
        server.scene.emit(event)

    def guard(self, path: str | Path, held_back: Callable[[str], bool] | None) -> None:
        """Hold some files of a store back from the page, or with None none of them.

        ``held_back`` is asked for a file's path below the store's folder and
        says whether the page may not read it yet (see ``Stores.guard``).
        """
        self.start()
        assert self._server is not None
        self._server.stores.guard(Path(path).expanduser(), held_back)

    def remove_store(self, layer: str, path: str | Path) -> bool:
        """Take one store out of a layer; the layer goes with its last store."""
        wanted = Path(path).expanduser().resolve()
        with self._lock:
            held = self._layers.get(layer)
            if held is None:
                return False
            kept = [p for p in held.placements if p.store.path != wanted]
            if len(kept) == len(held.placements):
                return False
            held.placements = kept
            if not kept and not held.previews:
                del self._layers[layer]
            self._publish()
            return True

    # -- stacks shown from memory while they are acquired --------------------------

    def add_preview(self, layer: str, source, channel: Channel, *, visible: bool = True) -> str:
        """Show a stack that is being acquired, from memory, and return the preview's name.

        ``source`` answers ``read(path)`` with the bytes of a small zarr store
        (``live.PreviewStack``); it joins the layer's channel called
        ``channel.label`` as one more source. Planes are announced with
        :meth:`preview_landed` as they arrive.
        """
        self.start()
        assert self._server is not None
        with self._lock:
            self._previews += 1
            name = f"live-{self._previews}"
            self._server.live[name] = source
            held = self._layers.get(layer)
            if held is None:
                held = self._layers[layer] = Layer(name=layer, visible=visible)
            stack = getattr(source, "stack", None)
            held.previews.append(
                Preview(
                    id=name,
                    url=f"{self._server.url}live/{name}/|zarr2:",
                    channel=channel,
                    index=getattr(stack, "channel_index", 0),
                    voxel_um=getattr(stack, "voxel_um", None),
                )
            )
            self._publish()
        return name

    def preview_landed(self, name: str, files: list[str]) -> None:
        """Say that planes of a preview have arrived (their chunk files inside its store)."""
        if self._server is not None and files:
            self._server.scene.emit({"type": "landed", "store": f"live/{name}", "files": list(files)})

    def retire_preview(self, name: str) -> None:
        """Say that the stack a preview shows is on disk now: the page takes the
        preview off as soon as the tile's own picture is up. :meth:`remove_preview`
        still has to follow, to let its memory go."""
        with self._lock:
            for held in self._layers.values():
                for at, preview in enumerate(held.previews):
                    if preview.id == name and not preview.retiring:
                        held.previews[at] = replace(preview, retiring=True)
                        self._publish()
                        return

    def remove_preview(self, name: str) -> bool:
        with self._lock:
            found = False
            for layer_name, held in list(self._layers.items()):
                kept = [preview for preview in held.previews if preview.id != name]
                if len(kept) != len(held.previews):
                    held.previews = kept
                    found = True
                    if not held.placements and not kept:
                        del self._layers[layer_name]
            if found:
                self._publish()
            if self._server is not None:
                self._server.live.pop(name, None)
            return found

    def look_at_newest(self, *, preview: str | None = None, chunk: list[int] | None = None, **axes: float) -> None:
        """Where the newest data of a running acquisition is, by axis name in micrometres
        (the time point for ``t``). A page that follows the acquisition goes there;
        one the operator has moved stays where it is. Without axes: nothing is running.

        ``preview`` and ``chunk`` name the chunk of a preview that holds that plane
        (its place in the preview's grid of chunks, as x, y, z, c, t): the page
        loads it first and steps once it can be drawn, so following never shows
        an empty picture between two planes.
        """
        self.start()
        assert self._server is not None
        where: dict | None = dict(axes) or None
        if where is not None and preview and chunk is not None:
            where["await"] = {"store": f"live/{preview}", "chunk": list(chunk)}
        self._server.scene.look_at_newest(where)

    def remove(self, layer: str) -> bool:
        with self._lock:
            gone = self._layers.pop(layer, None) is not None
            if gone:
                self._publish()
            return gone

    def clear(self) -> None:
        with self._lock:
            self._layers.clear()
            self._publish()

    def measure(self, layer: str, path: str | Path | None = None) -> bool:
        """Set the contrast of the layer's channels that have none yet, from the data
        of one of its stores (or of each); True when a window was found.

        For a store that held nothing when it was first shown: asked again once
        files have landed in it.
        """
        wanted = Path(path).expanduser().resolve() if path is not None else None
        with self._lock:
            held = self._layers.get(layer)
            if held is None:
                return False
            before = dict(held.measured)
            for placement in held.placements:
                if wanted is None or placement.store.path == wanted:
                    _measure(held, placement)
            if held.measured == before:
                return False
            self._publish()
            return True

    def set_window(
        self, layer: str, channel: str, window: tuple[float, float], *, only_if_unset: bool = False
    ) -> None:
        """Give one channel of a layer its starting contrast window, by its label."""
        with self._lock:
            held = self._layers.get(layer)
            if held is None or (only_if_unset and channel in held.measured):
                return
            held.measured[channel] = (float(window[0]), float(window[1]))
            self._publish()

    def set_auto(self, layer: str, auto: bool) -> None:
        """Whether the page keeps setting the layer's contrast from what is on screen
        (until the operator sets it): for an acquisition that is being written."""
        with self._lock:
            held = self._layers.get(layer)
            if held is not None and held.auto != auto:
                held.auto = auto
                self._publish()

    def set_visible(self, layer: str, visible: bool) -> None:
        with self._lock:
            self._layers[layer].visible = visible
            self._publish()

    def set_layout(self, layout: str) -> None:
        if layout not in LAYOUTS:
            raise ValueError(f"layout must be one of {LAYOUTS}")
        with self._lock:
            self._layout = layout
            self._publish()

    @property
    def layers(self) -> list[str]:
        with self._lock:
            return list(self._layers)

    def stores(self, layer: str) -> list[Store]:
        with self._lock:
            return [p.store for p in self._layers[layer].placements]

    @property
    def scene(self) -> dict:
        """What the page is being asked to show: neuroglancer layers with the page's
        additions (see ``state.py``)."""
        with self._lock:
            return state_json(
                list(self._layers.values()), layout=self._layout, transparent=self._ui["transparent"]
            )

    @property
    def state(self) -> dict:
        """The same as a state stock neuroglancer restores."""
        return engine_state(self.scene)

    # -- the camera ------------------------------------------------------------

    def look_at(self, **axes: float) -> None:
        """Centre the view on a point, given by axis name in micrometres (seconds for time)."""
        self._camera({"position": axes})

    def fit(self) -> None:
        """Zoom so that everything shown fits the window."""
        self._camera({"fit": True})

    @property
    def position(self) -> dict[str, float] | None:
        """Where the page's camera is, by axis name, in micrometres and seconds."""
        server = self._server
        if server is None or not server.last_view:
            return None
        return self._to_units(server.last_view)

    def on_view(self, listener: Callable[[dict[str, float]], None]) -> None:
        """Hear every camera move, as the same axis-named dictionary ``position`` gives."""
        self.start()
        assert self._server is not None
        self._server.view_listeners.append(lambda raw: listener(self._to_units(raw)))

    def on_pick(self, listener: Callable[[dict[str, float]], None]) -> None:
        """Hear a double-click on the picture, as an axis-named point in micrometres."""
        self.start()
        assert self._server is not None
        self._server.pick_listeners.append(lambda raw: listener(self._to_units(raw)))

    # -- the panel's list of acquisitions ---------------------------------------------

    def offer(self, acquisitions: list[dict]) -> None:
        """Fill the panel's list of acquisitions, shown or not.

        Each entry is a dictionary with a ``name`` and what the panel says about
        it: ``shown``, ``live`` (the microscope is writing it), ``tiles``,
        ``removable`` and a ``note`` such as how far the running stack has got.
        An empty list hides the list.
        """
        self.start()
        assert self._server is not None
        self._server.scene.offer([dict(entry) for entry in acquisitions])

    def on_show(self, listener: Callable[[str, bool, bool], None]) -> None:
        """Hear the operator tick an acquisition of that list on or off:
        ``listener(name, visible, only)``, ``only`` when they asked for it alone."""
        self.start()
        assert self._server is not None
        self._server.show_listeners.append(listener)

    def on_open(self, listener: Callable[[], None]) -> None:
        """Hear the operator press Open in the panel. The panel shows the button
        only once something listens."""
        self.start()
        assert self._server is not None
        self._server.open_listeners.append(listener)
        self._server.scene.dress(openable=True)

    def on_collect(self, listener: Callable[[bool], None]) -> None:
        """Hear the operator switch Live on or off: ``listener(on)``. The panel shows the
        switch only once something listens."""
        self.start()
        assert self._server is not None
        self._server.collect_listeners.append(listener)

    def collecting(self, on: bool) -> None:
        """Say whether runs the microscope acquires are collected: the Live switch shows it."""
        self.start()
        assert self._server is not None
        self._server.scene.dress(collecting=on)

    def on_remove(self, listener: Callable[[str], None]) -> None:
        """Hear the operator ask to take an acquisition off the view, by its layer name.

        The panel gives each acquisition a remove button only once something
        listens, so a window that cannot take acquisitions away offers none.
        """
        self.start()
        assert self._server is not None
        self._server.remove_listeners.append(listener)
        self._server.scene.dress(removable=True)

    def say(self, text: str) -> None:
        """Show a message on the picture, such as why a folder could not be opened.

        An empty text takes the message away.
        """
        self.start()
        assert self._server is not None
        self._server.scene.say(text)

    # -- windows ---------------------------------------------------------------

    def open_in_browser(self) -> str:
        url = self.start()
        webbrowser.open(url)
        return url

    def qt_widget(self, parent=None):
        """A ``QWebEngineView`` showing the viewer, for a PyQt/PySide window.

        Qt is imported lazily, so the package has no Qt dependency of its own:
        whichever of PyQt5, PyQt6, PySide6 or PySide2 the host already uses is
        picked up. With ``transparent=True`` the page's ground is clear, so the
        host's own widgets show through wherever nothing was imaged.
        """
        url = self.start()
        qt = _qt()
        widget = qt.QWebEngineView(parent)
        if self._ui["transparent"]:
            widget.page().setBackgroundColor(qt.QColor(0, 0, 0, 0))
            widget.setAttribute(qt.WA_TranslucentBackground, True)
            widget.setStyleSheet("background: transparent")
        widget.setUrl(qt.QUrl(url))
        return widget

    # -- inside ----------------------------------------------------------------

    def _register(self, store: Store) -> str:
        """The key the server serves the store's folder under; the server is started for it."""
        self.start()
        assert self._server is not None
        return self._server.stores.register(store.path)

    def _store_url(self, key: str, store: Store, revision: int) -> str:
        """The address the page reads the store at.

        A store whose shape has changed gets a new address, ``<key>.<revision>``,
        which the server resolves to the same folder: the engine keeps a store's
        description for as long as the page lives, so under the old address it
        would go on drawing the store with the extent it first had.
        """
        assert self._server is not None
        if revision:
            key = f"{key}.{revision}"
        return f"{self._server.url}data/{key}/|{store.format}:"

    @staticmethod
    def _channels(store, channels, colours, window) -> list[Channel] | None:
        if channels is None and colours is None and window is None:
            return None
        count = store.channel_count
        base = list(store.channels)[:count]
        while len(base) < count:
            base.append(Channel(label=f"channel {len(base)}"))
        result = []
        for index, held in enumerate(base):
            label = held.label
            color = held.color
            if channels is not None and index < len(channels):
                given = channels[index]
                if isinstance(given, Channel):
                    held = given
                    label, color = given.label, given.color
                else:
                    label = str(given)
            if colours is not None and index < len(colours):
                color = colours[index]
            result.append(
                Channel(
                    label=label,
                    color=color,
                    window=window or held.window,
                    limits=held.limits,
                    active=held.active,
                )
            )
        return result

    def _publish(self) -> None:
        if self._server is not None:
            self._server.scene.publish(self.scene)

    def _camera(self, camera: dict) -> None:
        self.start()
        assert self._server is not None
        self._server.scene.move_camera(camera)

    @staticmethod
    def _to_units(raw: dict) -> dict[str, float]:
        """Voxel coordinates in the page's global space, turned into micrometres."""
        names = raw.get("names") or []
        scales = raw.get("scales") or []
        units = raw.get("units") or []
        position = raw.get("position") or []
        out = {}
        for i, name in enumerate(names):
            if i >= len(position) or i >= len(scales):
                continue
            unit = units[i] if i < len(units) else ""
            out[name] = float(position[i]) * float(scales[i]) * _si_factor(unit)
        return out


class _Qt:
    """The Qt names the viewer's widgets need, from whichever binding is installed.

    PyQt5 first, because that is what mesoSPIM-control uses; the others for a host
    that has moved on. The window in ``window.py`` uses the same helper.
    """

    BINDINGS = ("PyQt5", "PyQt6", "PySide6", "PySide2")

    def __init__(self, binding: str) -> None:
        self.binding = binding
        self.QtCore = __import__(f"{binding}.QtCore", fromlist=["Qt", "QUrl", "QTimer"])
        self.QtGui = __import__(f"{binding}.QtGui", fromlist=["QColor"])
        self.QtWidgets = __import__(f"{binding}.QtWidgets", fromlist=["QWidget"])
        web = __import__(f"{binding}.QtWebEngineWidgets", fromlist=["QWebEngineView"])
        self.QUrl = self.QtCore.QUrl
        self.QColor = self.QtGui.QColor
        self.QWebEngineView = web.QWebEngineView
        attributes = getattr(self.QtCore.Qt, "WidgetAttribute", self.QtCore.Qt)
        self.WA_TranslucentBackground = attributes.WA_TranslucentBackground


def _qt() -> _Qt:
    errors = []
    for binding in _Qt.BINDINGS:
        try:
            return _Qt(binding)
        except ImportError as error:  # pragma: no cover - depends on the host
            errors.append(f"{binding}: {error}")
    raise ImportError("no Qt WebEngine binding found (" + "; ".join(errors) + ")")
