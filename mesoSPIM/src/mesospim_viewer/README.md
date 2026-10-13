# mesoSPIM viewer

A small neuroglancer viewer for the mesoSPIM control software: Python decides
which OME-Zarr stores are shown and where, a native neuroglancer page draws
them, and the camera comes back to Python. The package is standard-library
Python; the page is neuroglancer with a few hundred lines of glue.

```python
from mesoSPIM.src.mesospim_viewer import Viewer

view = Viewer()                                     # serves on a free local port
view.add("run/Tile0.ome.zarr", layer="overview")    # placed by its own metadata
view.add("run/Tile1.ome.zarr", layer="overview", offset={"x": 1800.0})
view.fit()
widget = view.qt_widget()                           # a QWebEngineView, or:
view.open_in_browser()
```

And the **Data viewer window**, one window for data that is being acquired and
for data that was:

```
python -m mesoSPIM.src.mesospim_viewer.window /path/to/data              # a folder the microscope writes into: watched
python -m mesoSPIM.src.mesospim_viewer.window /path/to/Sample.ome.zarr   # a dataset from disk
python -m mesoSPIM.src.mesospim_viewer.demo --live --window              # a rehearsal of a run, without the microscope
```

In mesoSPIM-control it is `View > Open Data Viewer`, and `View > Open Dataset
in Data Viewer...` puts a dataset from disk into the same window.

## What the window does

**A list of acquisitions** at the top of the panel. The folder the microscope
writes into is watched: its acquisitions are listed, newest first, and the
newest is shown. Datasets opened from disk -- the folder button in the list, a
folder dropped onto the window, or the command line -- are listed beside them.
The eye of an entry shows or hides it, so several can be looked at together,
each tile where its own metadata puts it; a click on a name shows that one
alone. An acquisition that starts is shown in place of the one that was on
screen for being the newest; one the operator ticked themselves stays.

**A running acquisition is on screen plane by plane.** mesoSPIM-control hands
the window the frame its camera window shows, and the stack that is being
acquired is drawn from those frames, held in memory (`live.py`): the first
plane is on screen as the camera delivers it, whatever the run is saved as.
When the stack is complete on disk the tile there takes its place. (What is on
disk *during* a stack is not a picture yet: the writers save 64 planes at a
time, and the small copies of the image that a view of the whole specimen is
drawn from only after several such slabs or when the stack closes. Without the
camera's frames -- the window started on its own, watching a folder another
program writes -- a tile fills in slab by slab, and zoomed far out about when
it is finished. `demo --live --from-disk` shows the difference.)

**Live.** While the microscope acquires, the view sits on the newest plane,
and the *Live* button at the top left says so. Stepping through depth or time
by hand leaves the view where the operator put it and turns the button into
*Back to live*.

**Fit.** Until the operator pans or zooms, the view frames everything shown,
again after every tile that lands. After that it is theirs, and a *Fit* button
appears beside the 2D/3D switch. The two are independent: zooming into the
tile being acquired does not stop the planes from coming.

**Contrast that sets itself.** A channel whose contrast nobody has set -- not
the store, not the operator -- is on *Auto*: its window follows the histogram
of what is on screen, from the camera's background to just under the brightest
structure (`contrast.js`). That is every channel of a running acquisition,
whose brightness nobody knows yet. Moving a channel's contrast by hand ends
Auto for it; the Auto button in its row brings it back.

**Never a silent black picture.** With nothing to draw, the picture says what
it is waiting for: no acquisition yet, nothing ticked, the first planes of a
run. A thin bar along the top shows while chunks are still loading, a line at
the bottom right gives the position and the value of each channel under the
pointer, and a folder that cannot be opened is named with the reason, such as
"notes isn't an OME-Zarr folder the viewer can open." or "newer.ome.zarr can't
be shown: it is OME-NGFF 0.6, which the viewer does not read yet."

**The mouse** is an image viewer's: drag moves the picture, the wheel zooms,
Shift and the wheel (or `,` and `.`) step through the planes, `[` and `]`
through the time points. In 3D, drag turns the specimen. The `?` at the top
right says so on screen. The flat view cannot be tilted by accident.

Three dresses, chosen with `Viewer(ui=...)`: `"simple"` (the Data viewer
window's) is the interface described here over a bare engine; `"full"` is
neuroglancer's own interface, panels and all; `"bare"` is nothing but the
picture, for a host that draws its own controls. In every dress what Python
adds is only what neuroglancer cannot know: which stores belong together,
where each one sits, and how its channels should first look.

## Why a tile landing never blanks the picture

Stock practice with neuroglancer is to describe the scene as a state and
restore it, and a layer whose description changed is built anew. A rebuilt
layer forgets every chunk it had drawn. For a running acquisition that is
ruinous: each tile that lands, each slab that is read again, blanks the
picture and fetches all of it once more, and the panel's controls are torn
down and put back. Measured on a run of four tiles and two channels written
by the microscope's own writer: 70 rebuilds in five minutes, 437 MB fetched
for a picture of a few megabytes, and a black screen for the first half of
every stack, because the view sat on the middle plane while planes land from
the first.

So nothing is rebuilt:

- **A layer is built once and then changed in place** (`source/src/layers.js`).
  A tile that lands is one source added to it. A tile whose shape changed -- a
  time point appended -- is that one source read again under a new address.
  A contrast window measured later is that control moved, unless the operator
  has moved it since.
- **A store that is being written is not read again as a whole.** Python
  looks at its folder once a second and names the files that have landed
  (`landing.py`); the page reads exactly the chunks that come from those files
  and leaves every chunk already drawn on the graphics card
  (`source/src/engine/worker_landed.js`). Nothing that is still missing is
  asked for twice.
- **A step to a new plane waits for the plane.** The engine drops the plane it
  was on the moment it is moved, so a view that follows an acquisition would
  blink black with every plane. The chunk of the next plane is loaded first,
  as if it were on screen, and the view steps once it can be drawn.
- **A finished stack is handed over, not swapped.** The tile on disk is kept
  from the page while its stack is shown from memory, so the two are never
  drawn on top of each other; once the stack is whole on disk its files are
  named as landed, and the preview goes only when the tile's own picture is up.

## What it keeps from the ZMART viewer, and what it leaves out

It began beside the [ZMART viewer](https://github.com/thomdehoog/ZMART-viewer),
which grew to follow a running
acquisition of tens of thousands of positions: a replaced interface, paced
source hand-over, server-side composition of many stores into one, baked
pyramids, publication records and live refresh patches to the engine. None of
that is needed for a view that shows at most a few dozen stores, so
this package starts again from native neuroglancer and takes three things
across:

- **A layer is one acquisition, its positions are its sources.** The engine
  places each source by a transform and composites them; nothing is stitched.
- **A channel is an engine layer.** One layer per channel is neuroglancer's own
  multichannel arrangement; see below why.
- **The transparent 2D ground**, as the engine's opt-in `transparentBackground`
  option of google/neuroglancer#1128, applied to the pinned engine.

Left out, on purpose: the composed `.zmartview.zarr` picture, baking,
publication and revision bookkeeping, the React interface, and every server
route that is not needed here.

What the build does to the pinned engine is in `source/scripts/neuroglancer.mjs`,
applied while the page is built, never to the installed engine, so building
twice makes the same page: the transparent ground, how channels and tiles are
mixed (next section), a source read again keeping its chunks on screen until
each is replaced (google/neuroglancer#1126), and the two background workers
compiled for the old browser of the Data viewer window, the chunk worker with
`worker_landed.js` added to it.

## How channels and tiles are mixed

Each channel is drawn in its colour scaled by its brightness, and what is laid
over the picture replaces, for each of red, green and blue, only what is
darker than itself. So a structure lit in two channels shows in both colours
at once, rather than the upper channel hiding the lower; two tiles of one
acquisition that overlap look like either tile alone along the join, rather
than twice as bright; and the mix never clips to white. Stock neuroglancer
offers laying a layer over the ones beneath, or adding them; this third way is
one edit to the pinned engine.

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

How the arrays are chunked and sharded is the writer's choice. **One chunk
(and one shard) per time point and channel** is the layout the viewer reads
best: the engine fetches whole chunks for the plane it shows, and a chunk
spanning other time points or channels is bytes downloaded for nothing. Shards
are read through byte-range requests, which the server answers. The depth of a
chunk is what one step through the planes costs: a chunk 64 planes deep is
read whole to show one of them, and the next 63 are then free.

A store may grow while it is shown. Files that land in it are picked up as
described above. A time point appended to it changes its shape, and the page
then reads that one store's description again, without touching the other
stores or the operator's adjustments.

Placement reads the store's own `scale` and `translation` (per-dataset and
multiscale-level transformations composed the way the format says). The
`omero` block, when present, names and colours the channels and sets their
starting window; `add()` can override all three. A channel left without a
window -- the acquisition software's writers leave it out -- would otherwise
start on the whole 0..65535 range, where a camera's few thousand counts look
black. For a dataset that is not being written, such a channel's window is
measured once from its data: from the background (the 1st percentile) to just
under the brightest voxels of the coarsest copy that holds data
(`sample_window()`, with the `zarr` package mesoSPIM-control already installs).
For one that is being written, the page sets it from what is on screen.

`read_store()` raises `NotAStore` with a plain reason for anything else.

## Why one engine layer per channel

The engine reads every channel of a voxel from a single chunk, so a *channel
dimension* -- the arrangement that lets one shader read all channels -- works
only when every chunk spans the whole `c` axis (measured: split it across
chunks and the source draws nothing, with "Channel dimension ... has extent N
but corresponding chunk dimension has extent 1"). Chunks per channel are the
right layout for writing and reading, so `c` stays a per-layer dimension and
each channel is a layer that pins it (`localPosition`). The panel lists them
as `488`, `561` under their acquisition; the Python API still speaks of one layer.

## Known limits

- **Nothing is stitched.** Tiles are placed by their stage positions; where
  two overlap, the brighter of the two is seen. A stitched store is the way to
  a registered overlap.
- **The live preview is a thinned-out copy**: at most 512 voxels across and
  256 planes deep. It is for watching the run; the tile on disk replaces it.
- **Following from disk alone is as coarse as the writer's slabs** (see "What
  the window does").
- **The engine needs WebGL 2** and a canvas with a size: the page fills its
  window, so give the widget one.

## How it works

```
Python                                    the page (source/)
------                                    ------------------
Viewer.add / remove / set_layout  --->    GET /api/state?since=N&events=M&follow=K   (waits)
  describes each channel as a               brings the layers into line in place
  neuroglancer layer (state.py)             (layers.js)
Viewer.landed / preview_landed    --->      events: files that landed; exactly their
                                            chunks are read again (engine/)
Viewer.look_at_newest             --->      where the newest plane is (camera.js)
Viewer.look_at / fit              --->      camera, applied once the sources settled
Viewer.offer                      --->      the panel's list of acquisitions
Viewer.say                        --->      a message on the picture
Viewer.position, on_view          <---    POST /api/view   (camera, debounced)
Viewer.on_pick                    <---    POST /api/pick   (a double-click)
Viewer.on_show, on_remove         <---    POST /api/show, /api/remove (the list)
Viewer.on_open                    <---    POST /api/open   (the list's folder button)
                                          GET  /data/<key>/...   (store bytes)
                                          GET  /live/<name>/...  (a stack held in memory)
```

Python:

- `omezarr.py` reads the metadata above.
- `state.py` turns placed stores into what the page shows: one engine layer per
  channel over the same sources, written the way neuroglancer writes a layer,
  plus a lasting name for every source so the page can change a layer in place.
  The shader's text is the same for every channel; window and colour travel as
  the values of its controls.
- `server.py` is a `ThreadingHTTPServer`: the built page, store bytes with
  byte ranges and ETags (sharded zarr v3 needs ranges), stacks held in memory,
  and the scene. The scene is state with a version; files that landed are
  events in a short numbered log; where the newest plane is travels beside
  both, so a new plane costs a few bytes.
- `viewer.py` is the API.
- `landing.py` answers "which files of this store are new?" cheaply, once a
  second, and turns the answer into how many planes of each stack are complete.
- `live.py` is the stack being acquired, held in memory and read by the page
  as a small zarr store.
- `watch.py` is the window without the window: `Library` holds the list of
  acquisitions and keeps a viewer in line with it and with the disk. Tested
  without Qt.
- `window.py` gives the `Library` a window, a timer, a file dialog and drops.
  Everything that touches the disk, and everything the microscope feeds in,
  runs off the GUI thread.
- `mesoSPIM_DataViewer.py`, one folder up, is all mesoSPIM-control holds of
  it: the two menu entries, and four signals turned into calls on the window.

The page:

- `main.js` builds a stock viewer and keeps up with Python.
- `layers.js` changes layers in place; `engine/landed.js` and
  `engine/worker_landed.js` read again only what landed, and load a plane
  before the view steps to it.
- `camera.js` is framing and following; `contrast.js` is Auto.
- `panel.js` is the simple interface. The window-with-histogram and colour
  controls are the engine's own widgets, mounted in its rows; the panel is
  registered as one of the engine's side panels, because the engine draws a
  histogram only for a panel that lies within its own canvas.

Positions and picks are spoken in **micrometres** (seconds for `t`) by axis
name, whatever unit a store was written in.

## Embedding in mesoSPIM-control

mesoSPIM-control is PyQt5, its main window owns the core thread and opens its
child windows. The Data viewer is one more:

```python
# the Data viewer window, as mesoSPIM_DataViewer.open_window opens it
from mesoSPIM.src.mesospim_viewer.window import make_window_class
window = make_window_class()(acq_list[0]["folder"])    # the folder is watched
window.show()
window.open("/data/earlier/Sample.ome.zarr")           # a dataset from disk, beside it

# what mesoSPIM_DataViewer.Feed tells it while a stack is acquired
window.begin_stack(stack)          # a mesospim_viewer.Stack: where, how big, which channel
window.add_plane(index, frame)     # returns at once: the frame is thinned out and queued
window.end_stack()
window.end_run()

# or the plain widget inside a window of your own
self.view = Viewer(transparent=False)
layout.addWidget(self.view.qt_widget(self))
self.view.add(store_path, layer=acq["filename"], window=(100, 4000))
self.view.on_pick(lambda point: self.core.sig_move_absolute.emit(point))
```

Nothing in the acquisition waits for the viewer. The frame is the one the
camera window already shows (`frame_queue_display`), taken on the signal that
window listens to; the viewer copies every few pixels of it and returns.

`transparent=True` clears the ground outside the acquired pixels, so a host
widget under the view shows through (`QWebEngineView` is given a clear page
background). The engine's in-picture axis lines are switched off in that mode:
they blend against destination alpha and would wipe the transparency.

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

Then, in mesoSPIM-control, `View > Open Data Viewer`. Before the first real
run, two quick checks from a Python prompt in that environment:

```python
from mesoSPIM.src import mesospim_viewer; import PyQt5.QtWebEngineWidgets      # both import
mesospim_viewer.Viewer().page_built                   # True: the page came along
```

and `python -m mesoSPIM.src.mesospim_viewer.demo --live --window` rehearses a
run in the Data viewer window without the microscope: it writes with the
microscope's own writer at a camera's pace and feeds the window the frames. If
that window says nothing and stays black, WebGL is the first suspect: set
`QTWEBENGINE_CHROMIUM_FLAGS=--ignore-gpu-blocklist` before starting, and try
`--disable-gpu-driver-bug-workarounds` after that. The same rehearsal in a
browser (`python -m mesoSPIM.src.mesospim_viewer.demo --live`) tells the two
apart: if the browser draws and Qt does not, it is Qt's GPU path.

## Building and testing

```
cd mesoSPIM/src/mesospim_viewer/source && npm ci && npm run build   # the page lands in ../build/
python -m mesoSPIM.src.mesospim_viewer.demo                              # four tiles in a browser
python -m pytest mesoSPIM/test/mesospim_viewer
```

Only changing the page needs Node: edit `source/`, build, and commit the
rebuilt `build/` with it. The Python side is developed and tested without Node,
and the microscope PC runs the committed page.

The tests come in three kinds. Most are Python alone. The page tests drive a
headless Chromium and assert what is drawn and, as important, what is *not*
done: no layer rebuilt when a tile lands, no chunk asked for twice, no empty
picture between two planes. And one test runs the microscope's own writer --
zarr v3, zstd, slabs of 64 planes, the pyramid built as it goes -- with the
viewer following, once from disk alone and once fed the frames: the viewer is
tested on what the microscope writes while it is writing, not on tiles written
in one go. The page tests skip, saying so, when the page is not built or no
browser is found (`MESOSPIM_VIEWER_CHROMIUM` names one). The Qt window itself
is only driven with `MESOSPIM_VIEWER_QT_TESTS=1` on a machine with OpenGL:
QtWebEngine aborts the process, rather than raising, where it cannot create a
context.
