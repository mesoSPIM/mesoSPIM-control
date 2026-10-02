"""The one object a control application holds: a viewer it can put stores in.

    from mesoSPIM.src.mesospim_viewer import Viewer

    view = Viewer()
    view.start()                                   # a local address
    view.add("run/tile_0.ome.zarr", layer="overview", offset={"x": 0})
    view.add("run/tile_1.ome.zarr", layer="overview", offset={"x": 1800})
    widget = view.qt_widget()                      # or view.open_in_browser()

Every call that changes what is shown publishes a fresh neuroglancer state to
the page. The page keeps whatever the operator has adjusted on layers that did
not change, so adding a tile does not reset the contrast of the others.
"""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Callable

from .omezarr import Channel, Store, read_store, sample_window
from .server import ViewServer
from .state import LAYOUTS, Layer, Placement, state_json


def read_again(placement: Placement) -> Placement:
    """The same placement over the store as it is on disk now."""
    return Placement(
        store=read_store(placement.store.path),
        url=placement.url,
        offset=placement.offset,
        origin=placement.origin,
        channel=placement.channel,
    )


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
        self._layout = layout
        self._ui = {"transparent": transparent, "chrome": ui}
        self._lock = threading.RLock()
        self._server: ViewServer | None = None
        self._thread: threading.Thread | None = None

    # -- lifetime --------------------------------------------------------------

    def start(self) -> str:
        """Start serving and return the page's address."""
        with self._lock:
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
        with self._lock:
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
        one from its data, as the Min-Max button would set it: from the first
        store of the layer that holds any data yet (see
        :func:`~.omezarr.sample_window`). It is set once and then left alone,
        so the picture does not change its brightness while tiles land.
        """
        store = read_store(path)
        name = layer or store.name
        url = self._url_for(store)
        if isinstance(channel, str):
            channel = Channel(label=channel)
        placement = Placement(
            store=store, url=url, offset=dict(offset or {}), origin=origin, channel=channel
        )
        declared = self._channels(store, channels, colours, window)
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
            if at is None:
                held.placements.append(placement)
            else:
                # The same store again means it has changed on disk -- a time
                # point appended -- so the page must read it afresh. It keeps
                # its place among the layer's sources.
                held.placements[at] = placement
                held.revision += 1
            _measure(held, placement)
            self._publish()
        return name

    def refresh(self, layer: str | None = None) -> None:
        """Re-read the stores of one layer, or of all, from disk.

        For a store that has grown while shown: a time-lapse appends time
        points to the stores already there, and the engine believes the extent
        it read first until told otherwise. Adjustments the operator made are
        kept.
        """
        with self._lock:
            for name, held in self._layers.items():
                if layer is None or name == layer:
                    held.placements = [read_again(p) for p in held.placements]
                    held.revision += 1
                    for placement in held.placements:
                        _measure(held, placement)
            self._publish()

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
    def state(self) -> dict:
        """The neuroglancer state the page is being asked to show."""
        with self._lock:
            return state_json(list(self._layers.values()), layout=self._layout)

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

    # -- the acquisition dropdown ------------------------------------------------

    def offer_acquisitions(self, names: list[str], current: int = 0, *, live: bool = True) -> None:
        """Fill the panel's dropdown: the acquisitions of the session, newest first,
        and which of them is shown. An empty list hides the dropdown.

        ``live`` says the folder is being acquired into, so the newest entry is
        marked as the current acquisition; for a folder opened from disk it is not.
        """
        self.start()
        assert self._server is not None
        self._server.scene.offer(names, current, live)

    def on_choice(self, listener: Callable[[int], None]) -> None:
        """Hear the operator pick an entry of that dropdown, by index."""
        self.start()
        assert self._server is not None
        self._server.choice_listeners.append(listener)

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

    def _url_for(self, store: Store) -> str:
        self.start()
        assert self._server is not None
        key = self._server.stores.register(store.path)
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
            self._server.scene.publish(state_json(list(self._layers.values()), layout=self._layout))

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
