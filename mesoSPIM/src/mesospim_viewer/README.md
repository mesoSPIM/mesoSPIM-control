# mesoSPIM viewer

A small neuroglancer viewer for the mesoSPIM control software: Python decides
which OME-Zarr stores are shown and where, a native neuroglancer page draws
them, and the camera comes back to Python. The package is standard-library
Python; the page is neuroglancer with a hundred lines of glue.

```python
from mesoSPIM.src.mesospim_viewer import Viewer

view = Viewer()                                     # serves on a free local port
view.add("run/Tile0.ome.zarr", layer="overview")    # placed by its own metadata
view.add("run/Tile1.ome.zarr", layer="overview", offset={"x": 1800.0})
view.fit()
widget = view.qt_widget()                           # a QWebEngineView, or:
view.open_in_browser()
```

And for a folder the microscope is writing into, the **Data viewer window**:

```
python -m mesoSPIM.src.mesospim_viewer.window /path/to/data        # or, from mesoSPIM-control: View > Open Live Data Viewer
python -m mesoSPIM.src.mesospim_viewer.window --acquired /path/to/Sample.ome.zarr   # View > Open Acquired Dataset...
python -m mesoSPIM.src.mesospim_viewer.demo --live                 # a pretend run, followed as it lands
```

The viewer, with a dropdown of the acquisitions in the folder, newest first,
at the top of its panel. The newest acquisition is followed on its own: a tile
that starts is on screen within a second and is read again as its chunks land
and once more when they stop, a time point appended to it likewise, and a new
acquisition starting is switched to, unless an older one was picked from the
dropdown. That logic is `Follower` in `watch.py` and is tested without Qt;
`window.py` gives it a window and a timer. While the operator has not panned or
zoomed, the page keeps framing every tile as more land; once they have, the
view is left where they put it, until a fit is asked for again (the 2D/3D
switch, or `Viewer.fit()`, which switching acquisitions calls).

Three dresses, chosen with `Viewer(ui=...)`: `"simple"` (the default of the
Data viewer window) is our own panel down the right-hand edge over a bare
engine, with the 2D/3D switch at the top left of the picture: a dropdown of
the session's acquisitions (fed by `offer_acquisitions`, answered through
`on_choice`; the Data viewer window's follower does both), in 3D a card with
the projection (max, accumulate, min), the
detail (ray steps), the gain, where to look from and whether to draw the slice
planes, one row per channel carrying the engine's own window-with-histogram
and colour controls, and depth and time sliders on the picture; `"full"` is neuroglancer's own interface, panels and all; `"bare"`
is nothing but the picture, for a host that draws its own controls. In every
dress the mouse and keyboard are the engine's, and what Python adds is only
what neuroglancer cannot know: which stores belong together, where each one
sits, and how its channels should first look.

## What it keeps from the ZMART viewer, and what it leaves out

It began beside the [ZMART viewer](https://github.com/thomdehoog/ZMART-viewer),
which grew to follow a running
acquisition of tens of thousands of positions: a replaced interface, paced
source hand-over, server-side composition of many stores into one, baked
pyramids, publication records and live refresh patches to the engine. None of
that is needed for a view that shows at most a few dozen finished stores, so
this package starts again from native neuroglancer and takes three things
across:

- **A layer is one acquisition, its positions are its sources.** The engine
  places each source by a transform and composites them; nothing is stitched.
- **A channel is an engine layer, composited by its brightness.** Each
  channel of an acquisition is its own image layer over the same sources,
  drawn over the ones beneath with its brightness as alpha, with the window
  and colour as `#uicontrol` values rather than shader text. One layer per
  channel is neuroglancer's own multichannel arrangement; compositing rather
  than adding is what keeps overlapping tiles from summing to a bright seam
  and dense channels from clipping to white. For that, one edit to the pinned
  engine lays every tile over the picture the same way: stock neuroglancer
  draws the first tile of a layer without blending, which made it look
  brighter than the others.
- **The transparent 2D ground**, as four small opt-in edits to the pinned
  engine, the same edits the ZMART viewer 0.2.1 carries.

Both live in `source/scripts/neuroglancer.mjs`, and are applied while the
page is built, never to the installed engine, so building twice makes the same
page. Nothing else is patched.

Left out, on purpose: live refresh and growth patches, contrast measured over
the whole dataset (one coarse sample sets the start, the engine's own histogram
does the rest), the composed `.zmartview.zarr`
picture, baking, publication and revision bookkeeping, the React interface,
and every server route but three.

## The data contract

A store is accepted when it is OME-NGFF **0.4 on zarr v2** or **0.5 on zarr
v3**, with the axes **`t, c, z, y, x`**, or some of them in that order, always
with `z, y, x`: so `(z, y, x)`, `(c, z, y, x)` and `(t, z, y, x)` open as well.
An axis that is left out counts as one step long, and `c`, when present, must
be of type `channel`. OME-NGFF 0.6 is not read yet: it describes axes and
transformations differently, and the neuroglancer release the page is built on
(2.41) does not read it either. Such a store is refused with a sentence saying so.

Some writers save one store per tile *and* channel, each without a `c` axis.
Such a store says which channel it holds in its own `omero` block, with one
entry, and stores with the same label are shown as one channel. The channel is
taken only from inside the store, never from its file name. A store without an
`omero` block cannot be told apart from the others, so all of them are then
shown as one channel.

**Which layout is quick to show.** What costs time is the number of stores,
not which axes they have: every store is set up on its own when it is shown.
One store per position with all its channels and time points inside it
(`t, c, z, y, x`, as `MP_OME_Zarr_TCZYX_Writer` writes) stays quick with
hundreds of positions. A dataset split into one store per channel, or per
time point, opens too, but becomes slow as the number of stores grows.

How the arrays are chunked and sharded is the writer's choice, and the viewer
does not look. **One chunk (and one shard) per time point and channel** is the
layout it reads best: the engine fetches whole chunks for the plane it shows,
and a chunk spanning other time points or channels is bytes downloaded for
nothing. Shards are read through byte-range requests, which the server
answers; a shard must be written in one go by the writer for reasons of its
own, and that changes nothing here.

A store may grow along `t` while it is shown: a time-lapse appends time points
to the stores already on disk. Show the store again (`add()` with the same
path) or call `refresh()`, and the page reads its new extent without touching
the other stores or the operator's adjustments.

Placement reads the store's own `scale` and `translation` (per-dataset and
multiscale-level transformations composed the way the format says). The
`omero` block, when present, names and colours the channels and sets their
starting window; `add()` can override all three. A channel left without a
window -- the acquisition software's writers leave it out -- would otherwise
start on the whole 0..65535 range, where a camera's few thousand counts look
black. Such a channel's window is measured once from its data instead, as the
Min-Max button would set it: the darkest and brightest voxel of the coarsest
copy in the first store that holds data, through up to 16 planes of its first
time point (`sample_window()`, with the `zarr` package mesoSPIM-control already
installs). In the live window a store the microscope has only just begun is
measured again as data lands, and a channel that arrives later is measured on
its own. The window is then left alone, so the picture keeps its brightness
while tiles land.

`read_store()` raises `NotAStore` with a plain reason for anything else.

## Why one engine layer per channel

The engine reads every channel of a voxel from a single chunk, so a *channel
dimension* -- the arrangement that lets one shader read all channels -- works
only when every chunk spans the whole `c` axis (measured: split it across
chunks and the source draws nothing, with "Channel dimension ... has extent N
but corresponding chunk dimension has extent 1"). Chunks per channel are the
right layout for writing and reading, so `c` stays a per-layer dimension and
each channel is a layer that pins it (`localPosition`). The engine adds the
layers together on the graphics card. The panel lists them as
`overview · 488`, `overview · 561`; the Python API still speaks of one layer.

## Known limits

- **Where tiles overlap, the tile drawn last covers the other** by its own
  brightness: a bright cell in the top tile hides a dim one beneath it. The
  engine offers no cropping of a source; a stitched store is the way to a
  seamless overlap.
- **The engine needs WebGL 2** and a canvas with a size: the page fills its
  window, so give the widget one.

## How it works

```
Python                                    the page (source/)
------                                    -----------------------
Viewer.add / remove / set_layout  --->    GET /api/state?since=N   (long poll)
  builds neuroglancer layer JSON            brings layers into line, keeping the
  (state.py)                                operator's own adjustments on layers
                                            Python did not change
Viewer.look_at / fit              --->    camera, applied once the sources settled
Viewer.position, on_view          <---    POST /api/view   (camera, debounced)
Viewer.on_pick                    <---    POST /api/pick   (a double-click)
                                          GET  /data/<key>/...   (store bytes)
```

- `omezarr.py` reads the metadata above.
- `watch.py` follows a folder: `Acquisitions` lists the `*.ome.zarr` groups
  in it newest first, `Watcher` polls one of them and adds a new tile, re-reads
  one that is still being written every ten seconds and once it has gone
  quiet, and one whose shape grew at once; `Follower` keeps a viewer on the
  newest.
- `state.py` turns placed stores into neuroglancer state: one engine layer per
  channel, over the same sources. A shifted source carries a `transform` whose
  translation column holds the shift, in voxels. Each layer's shader is the
  engine's own multichannel program with the store's window and colour as the
  controls' starting values; in 3D the brightness drives the opacity.
- `server.py` is a `ThreadingHTTPServer`: the built page, store bytes with
  byte ranges and ETags (sharded zarr v3 needs ranges), and the scene.
- `viewer.py` is the API. Every change publishes a new version; the page waits
  on `/api/state` for it, so a change is on screen within a frame, with no
  polling while nothing happens.
- `source/src/main.js` is the page. It builds a stock viewer
  (`makeDefaultViewer` plus the default bindings), applies states, reports
  back. A layer whose revision moved has its stores forgotten from the
  engine's memo before it is rebuilt, so a grown store is read afresh.
- `source/src/panel.js` is the simple interface: registered as one of
  the engine's own side panels (only a panel inside the engine's canvas gets
  a histogram drawn), with the view switch, the channel rows and the sliders.
  Every control reads and writes engine layer state, the same state the
  native panel edits, so the operator's adjustments survive Python's updates
  by the same rule.

Positions and picks are spoken in **micrometres** (seconds for `t`) by axis
name, whatever unit a store was written in.

## Embedding in mesoSPIM-control

mesoSPIM-control is PyQt5, its main window owns the core thread and opens its
child windows (`mesoSPIM_TileViewWindow` among them), and its `OmeZarrWriter`
plugin writes one OME-Zarr store per tile and channel. That fits the API
directly:

```python
# the Data viewer window, as mesoSPIM_MainWindow.open_data_viewer_window opens it
from mesoSPIM.src.mesospim_viewer.window import make_window_class
self.data_viewer_window = make_window_class()(acq_list[0]["folder"])
self.data_viewer_window.show()

# or the plain widget inside a window of your own
self.view = Viewer(transparent=False)
layout.addWidget(self.view.qt_widget(self))
self.view.add(store_path, layer=acq["filename"], window=(100, 4000))
self.view.on_pick(lambda point: self.core.sig_move_absolute.emit(point))
```

The stores it expects are the ones `MP_OME_Zarr_TCZYX_Writer` writes: one
`<Sample>.ome.zarr` group per acquisition holding one `(t, c, z, y, x)` store
per tile, channels along `c`, time points appended along `t`.

A separate store per channel shows as one engine layer each; a store with
several channels in one array shows as one engine layer per channel under one
name. Either way every position of an acquisition feeds the same layers, and
appended time points reach the screen through `add()` or `refresh()`.

`transparent=True` clears the ground outside the acquired pixels, so a host
widget under the view shows through (`QWebEngineView` is given a clear page
background). The engine's in-picture axis lines are switched off in that mode:
they blend against destination alpha and would wipe the transparency.
`ui="bare"` drops neuroglancer's panels and in-picture buttons, for a host that
draws its own controls; the mouse and keyboard still work.

The engine needs WebGL 2. Qt WebEngine has it; on a machine that blocks the
GPU, set `QTWEBENGINE_CHROMIUM_FLAGS="--ignore-gpu-blocklist"` before Qt starts.

## Installing on the microscope PC

The viewer comes with mesoSPIM-control, its page already built, so no Node
is needed there. The web view for PyQt5 that it draws in, PyQtWebEngine, is not
part of PyQt5 itself, but it is installed together with mesoSPIM-control. An
environment set up before the viewer existed may not have it yet; then, in the
mesoSPIM environment, install it and restart mesoSPIM:

```
pip install PyQtWebEngine==5.15.7
```

Then, in mesoSPIM-control, `View > Open Live Data Viewer`. Before the first real
run, three quick checks from a Python prompt in that environment:

```python
from mesoSPIM.src import mesospim_viewer; import PyQt5.QtWebEngineWidgets      # both import
mesospim_viewer.Viewer().page_built                   # True: the page came along
```

and `python -m mesoSPIM.src.mesospim_viewer.demo --live --window` shows a pretend run in the
Data viewer window without the microscope. If that window stays black, WebGL
is the first suspect: set `QTWEBENGINE_CHROMIUM_FLAGS=--ignore-gpu-blocklist`
before starting, and try `--disable-gpu-driver-bug-workarounds` after that.
The same window in a browser (`python -m mesoSPIM.src.mesospim_viewer.demo --live`) tells
the two apart: if the browser draws and Qt does not, it is Qt's GPU path.

## Building and testing

```
cd mesoSPIM/src/mesospim_viewer/source && npm ci && npm run build   # the page lands in ../build/
python -m mesoSPIM.src.mesospim_viewer.demo                              # four tiles in a browser
python -m pytest mesoSPIM/test/mesospim_viewer
```

Only changing the page needs Node: edit `source/`, build, and commit the
rebuilt `build/` with it. The Python side is developed and tested without Node,
and the microscope PC runs the committed page.

The picture tests drive a headless Chromium and assert what is drawn: four
tiles as two channel layers over the same sources, the axes on screen, a camera
move from Python and a pick from the page, an operator's adjustments surviving a
new tile, a store that gains time points while shown, and a transparent ground
that is clear outside the tile and opaque inside it. They
skip, saying so, when the page is not built or no browser is found
(`MESOSPIM_VIEWER_CHROMIUM` names one). The Qt window itself is only driven with
`MESOSPIM_VIEWER_QT_TESTS=1` on a machine with OpenGL: QtWebEngine aborts the
process, rather than raising, where it cannot create a context.
