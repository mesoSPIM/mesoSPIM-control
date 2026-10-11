/**
 * The simple interface: our own controls over a bare engine.
 *
 * On the picture: the 2D/3D switch, Fit, the Live button of a running
 * acquisition, the depth and time sliders along the bottom, a line that says
 * what is under the pointer, and -- instead of a silent black picture -- a few
 * words whenever there is nothing to draw yet. Down the right-hand edge: the
 * list of acquisitions, and one row per channel.
 *
 * Nothing here holds state of its own. The list of acquisitions is Python's
 * and is only drawn here; every other control reads and writes the engine's
 * own state -- visibility, the window and colour controls of a layer's shader,
 * the layout, the position -- so what the operator adjusts survives Python's
 * updates (layers.js). The window-with-histogram and colour controls ARE the
 * engine's own widgets, mounted inside our rows; only their dress is ours.
 *
 * The panel is registered as one of the engine's side panels rather than laid
 * beside it: the engine draws a histogram only for a panel that lies within
 * its own canvas, which is how its native side panels are arranged too.
 *
 * Written for Qt WebEngine 5.15 (Chromium 83) as much as for a current
 * browser: no flex gaps, no :has(), no accent-color (panel.css).
 */
import { ShaderControls } from "neuroglancer/unstable/widget/shader_controls.js";
import { WatchableVisibilityPriority } from "neuroglancer/unstable/visibility_priority/frontend.js";
import { SidePanel } from "neuroglancer/unstable/ui/side_panel.js";
import { TrackableSidePanelLocation } from "neuroglancer/unstable/ui/side_panel_location.js";
import { frameBounds, framing, layoutOf, setLayout, volumeDrawing } from "./camera.js";
import { about } from "./layers.js";
import { onAutoChanged } from "./contrast.js";
import "./panel.css";

export const SEPARATOR = " · "; // between acquisition and channel in a layer's name (state.py)

const ICONS = {
  eye: '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeOff: '<svg viewBox="0 0 24 24"><path d="M3 3l18 18"/><path d="M10.6 5.3A11 11 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.2 3.7"/><path d="M6.6 6.6A16 16 0 0 0 2 12s3.5 6 10 6a10 10 0 0 0 4.2-.9"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>',
  panel: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  arrow: '<svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>',
  pin: '<svg viewBox="0 0 12 12"><path d="M6 11.2S2 7.4 2 4.8a4 4 0 0 1 8 0c0 2.6-4 6.4-4 6.4z"/><circle cx="6" cy="4.8" r="1.3"/></svg>',
  open: '<svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  help: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7"/><path d="M12 17h.01"/></svg>',
  fit: '<svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function iconButton(icon, title) {
  const button = element("button", "icon");
  button.type = "button";
  button.title = title;
  button.innerHTML = ICONS[icon];
  return button;
}

function textButton(text, className, title) {
  const button = element("button", className, text);
  button.type = "button";
  if (title) button.title = title;
  return button;
}

function splitName(name) {
  const at = name.indexOf(SEPARATOR);
  return at === -1 ? [name, name] : [name.slice(0, at), name.slice(at + SEPARATOR.length)];
}

function imageLayers(viewer) {
  return viewer.layerManager.managedLayers
    .map((managed) => managed.layer)
    .filter((layer) => layer && layer.type === "image");
}

// -- which acquisition the operator is looking at -----------------------------------------

// The selected acquisition: its channels are the ones shown, and its positions
// are folded out (one acquisition's at a time, `open`), unless folded away.
export const selection = { name: null, open: null, listeners: [] };

function select(name, open = name) {
  if (selection.name === name && selection.open === open) return;
  selection.name = name;
  selection.open = open;
  for (const listener of selection.listeners) listener();
}

function cardHead(step, text) {
  const head = element("div", "row card-head");
  const title = element("h2", null, "");
  title.appendChild(element("span", "step", String(step)));
  title.appendChild(document.createTextNode(text));
  head.appendChild(title);
  return head;
}

// -- 1: load data: from a folder, or live from the microscope -------------------------------

function loadCard(post) {
  const card = element("section", "card load");
  card.appendChild(cardHead(1, "Load data"));
  const row = element("div", "load-row");
  const open = element("button", "open");
  open.type = "button";
  open.title = "Open a dataset from disk: an acquisition's folder, or a folder of acquisitions";
  open.innerHTML = ICONS.open;
  open.appendChild(element("span", null, "Open from folder…"));
  open.addEventListener("click", () => post("/api/open"));
  const live = element("button", "live-toggle");
  live.type = "button";
  live.setAttribute("role", "switch");
  live.title = "Live: collect what the microscope acquires. A run that starts comes in at the top of the list.";
  live.append(element("span", "live-dot"), element("span", "live-word", "Live"));
  let collecting = true;
  live.addEventListener("click", () => post("/api/collect", { on: !collecting }));
  row.append(open, live);
  card.appendChild(row);
  card.setUi = (ui) => {
    open.hidden = ui.openable !== true;
    live.hidden = typeof ui.collecting !== "boolean";
    collecting = ui.collecting !== false;
    live.classList.toggle("on", collecting);
    live.setAttribute("aria-checked", String(collecting));
    card.hidden = open.hidden && live.hidden;
  };
  card.setUi({});
  return card;
}

// -- 2: the acquisitions: Python's list, drawn as boxes with their positions --------------------

/** What the line under an acquisition's name says. */
function lineOf(entry) {
  if (entry.live) {
    // Between two stacks the microscope says nothing: how many positions are done, then.
    let where = entry.note ?? "";
    if (!where && Array.isArray(entry.positions) && entry.positions.length) {
      const done = entry.positions.filter((one) => one.state === "done").length;
      where = `${done} of ${entry.positions.length} positions acquired`;
    }
    return entry.paused ? `Paused${SEPARATOR}${where}` : where;
  }
  const positions = Array.isArray(entry.positions) ? entry.positions.length : null;
  const parts = [];
  if (positions) parts.push(positions === 1 ? "1 position" : `${positions} positions`);
  else if (typeof entry.tiles === "number" && entry.tiles > 0) parts.push(entry.tiles === 1 ? "1 tile" : `${entry.tiles} tiles`);
  if (Array.isArray(entry.channels) && entry.channels.length) parts.push(entry.channels.join(", "));
  return parts.join(SEPARATOR);
}

/** Every position's place together, in micrometres, or null while none is known. */
function boundsOf(places) {
  const box = {};
  for (const um of places) {
    if (!um) continue;
    for (const [axis, [low, high]] of Object.entries(um)) {
      const was = box[axis];
      box[axis] = was ? [Math.min(was[0], low), Math.max(was[1], high)] : [low, high];
    }
  }
  return box.x && box.y ? box : null;
}

function acquisitionsCard(viewer, post) {
  const card = element("section", "card acquisitions");
  const head = cardHead(2, "Acquisitions");
  const count = element("span", "count", "");
  head.appendChild(count);
  card.appendChild(head);
  const list = element("div", "list");
  card.appendChild(list);
  const empty = element("p", "hint", "");
  card.appendChild(empty);
  let entries = [];
  let wasLive = new Set();
  let wanted = null; // where to go once Python says where it is: { name, position }
  let framedAt = null; // the position the view went to, marked until Fit frames everything again
  const go = () => {
    if (wanted === null) return;
    const entry = entries.find((one) => one.name === wanted.name);
    if (!entry) {
      wanted = null;
      return;
    }
    const positions = entry.positions ?? [];
    const target = wanted.position === null ? boundsOf(positions.map((one) => one.um))
      : positions.find((one) => one.name === wanted.position)?.um ?? null;
    if (target && frameBounds(viewer, target)) {
      framedAt = wanted.position === null ? null : { name: wanted.name, position: wanted.position };
      wanted = null;
      draw();
    }
  };
  framing.listeners.push((framingAll) => {
    if (framingAll && framedAt !== null) {
      framedAt = null;
      draw();
    }
  });
  const pick = (entry, position = null) => {
    select(entry.name);
    if (!entry.shown) post("/api/show", { name: entry.name, visible: true });
    wanted = { name: entry.name, position };
    go();
  };
  const draw = () => {
    count.textContent = entries.length ? String(entries.length) : "";
    list.replaceChildren();
    empty.hidden = entries.length > 0;
    for (const entry of entries) {
      const box = element("div", "acquisition");
      box.dataset.name = entry.name;
      box.classList.toggle("shown", entry.shown === true);
      box.classList.toggle("live", entry.live === true);
      box.classList.toggle("selected", selection.name === entry.name);
      const open = selection.open === entry.name;
      box.classList.toggle("open", open);
      const bar = element("div", "bar");
      const eye = iconButton(entry.shown ? "eye" : "eyeOff", entry.shown ? "Hide this acquisition" : "Show this acquisition");
      eye.classList.add("eye");
      eye.classList.toggle("off", !entry.shown);
      eye.addEventListener("click", (event) => {
        event.stopPropagation();
        post("/api/show", { name: entry.name, visible: !entry.shown });
      });
      const text = element("div", "text");
      text.append(element("span", "name", entry.name), element("span", "sub", lineOf(entry)));
      const badge = entry.paused ? element("span", "badge paused", "Paused")
        : entry.live ? element("span", "badge live", "Live") : element("span", "badge saved", "Saved");
      bar.append(eye, text, badge);
      if (entry.removable) {
        const remove = iconButton("close", "Take off the list (the files stay on disk)");
        remove.classList.add("remove");
        remove.addEventListener("click", (event) => {
          event.stopPropagation();
          post("/api/remove", { name: entry.name });
        });
        bar.appendChild(remove);
      }
      const positions = Array.isArray(entry.positions) ? entry.positions : [];
      const fold = iconButton("arrow", open ? "Fold its positions away" : `Show its ${positions.length} positions`);
      fold.classList.add("fold");
      fold.classList.toggle("unfolded", open);
      fold.addEventListener("click", (event) => {
        event.stopPropagation();
        select(entry.name, open ? null : entry.name);
      });
      bar.appendChild(fold);
      bar.addEventListener("click", () => pick(entry));
      box.appendChild(bar);
      if (open && positions.length) {
        const rows = element("div", "positions");
        for (const position of positions) {
          const row = element("button", "position");
          row.type = "button";
          row.dataset.name = position.name;
          if (position.state) row.dataset.state = position.state;
          row.classList.toggle("framed", framedAt?.name === entry.name && framedAt?.position === position.name);
          const pin = element("span", "pin");
          pin.innerHTML = ICONS.pin;
          row.append(pin, element("span", "label", position.name));
          if (position.state) {
            const channels = Array.isArray(entry.channels) ? entry.channels.length : 0;
            const words = {
              done: "acquired", now: "acquiring", next: "next",
              part: `${position.acquired ?? 0} of ${channels || "?"} channels`,
            };
            row.appendChild(element("span", "state", words[position.state] ?? position.state));
          }
          row.addEventListener("click", (event) => {
            event.stopPropagation();
            pick(entry, position.name);
          });
          rows.appendChild(row);
        }
        box.appendChild(rows);
      }
      list.appendChild(box);
    }
  };
  card.setAcquisitions = (next) => {
    entries = next;
    const names = entries.map((entry) => entry.name);
    // A run that starts is the one to look at: it is selected, and opened.
    const started = entries.find((entry) => entry.live && !entry.paused && !wasLive.has(entry.name));
    wasLive = new Set(entries.filter((entry) => entry.live).map((entry) => entry.name));
    if (started) select(started.name);
    else if (!names.includes(selection.name)) {
      const first = entries.find((entry) => entry.live) ?? entries.find((entry) => entry.shown) ?? entries[0];
      select(first ? first.name : null);
    }
    draw();
    go();
  };
  selection.listeners.push(draw);
  card.setUi = (ui) => {
    empty.textContent = ui.openable === true
      ? "Nothing here yet. Start an acquisition, or open a dataset from disk."
      : "Nothing here yet.";
  };
  card.setUi({});
  card.setAcquisitions([]);
  return card;
}

// -- the view: 2D or 3D ---------------------------------------------------------

function viewSwitch(viewer, fit) {
  const row = element("div", "segmented view");
  const buttons = new Map();
  for (const [layout, label, title] of [
    ["xy", "2D", "One plane at a time"],
    ["3d", "3D", "The whole stack as a volume"],
  ]) {
    const button = textButton(label, null, title);
    button.dataset.layout = layout;
    button.addEventListener("click", () => {
      setLayout(viewer, layout);
      applyVolumeMode(viewer);
      // The new panel exists a moment later; frame the picture in it then.
      setTimeout(() => fit?.(), 50);
    });
    buttons.set(layout, button);
    row.appendChild(button);
  }
  const reflect = () => {
    const current = layoutOf(viewer);
    for (const [layout, button] of buttons) button.classList.toggle("on", current === layout);
  };
  viewer.layout.changed.add(reflect);
  reflect();
  return row;
}

// The projection the volume view draws with: one choice for every channel,
// kept here so that a layer that arrives later is drawn the same way.
let volumeMode = "max";

/** The volume view draws a projection of every channel; the flat view leaves it off, as the engine does. */
function applyVolumeMode(viewer) {
  const wanted = layoutOf(viewer) === "3d" ? volumeMode : "off";
  for (const layer of imageLayers(viewer)) {
    if (layer.volumeRenderingMode?.toJSON() !== wanted) layer.volumeRenderingMode?.restoreState(wanted);
  }
}

// -- the volume view: how the specimen is projected, how finely, from where ------

const LOOK_FROM = [
  ["Top", [0, 0, 0, 1]],
  ["Front", [-Math.SQRT1_2, 0, 0, Math.SQRT1_2]],
  ["Side", [0, Math.SQRT1_2, 0, Math.SQRT1_2]],
];
// How many pixels of the screen one voxel of the copy drawn covers at least,
// from fast to sharp: the engine takes the finest copy whose voxels are no
// smaller, so in practice between this and twice it. Halving, because each copy
// of the image has voxels twice the size of the one before: each step of the
// slider is one finer copy, and the sharpest is as fine as the screen.
const DETAIL_PIXELS = [8, 4, 2, 1, 0.5];
let detail = 2;
// While the operator turns, zooms or pans the volume: two copies coarser, and
// never finer than a voxel to 8 pixels, so it keeps up at any detail; at the
// detail chosen once it has been still this long.
const WHILE_MOVING = 4;
const MOVING_PIXELS = 8;
const STILL_MS = 300;

function labelled(text, control, reading) {
  const row = element("div", "row labelled");
  row.appendChild(element("span", "label", text));
  row.appendChild(control);
  if (reading) row.appendChild(reading);
  return row;
}

function volumeCard(viewer, fit) {
  const card = element("section", "card volume");
  card.appendChild(element("h2", null, "3D view"));

  // Projection: the brightest voxel along each ray (a microscopist's projection),
  // every voxel accumulated with a gain, or the darkest voxel.
  const projection = element("div", "segmented");
  const projections = new Map();
  for (const [mode, label, title] of [
    ["max", "Max", "Maximum projection: the brightest voxel along each line of sight"],
    ["on", "Blend", "Every voxel adds to the picture, as far as the gain lets it"],
    ["min", "Min", "Minimum projection: the darkest voxel along each line of sight"],
  ]) {
    const button = textButton(label, null, title);
    button.dataset.mode = mode;
    button.addEventListener("click", () => {
      volumeMode = mode;
      applyVolumeMode(viewer);
    });
    projections.set(mode, button);
    projection.appendChild(button);
  }
  card.appendChild(labelled("Projection", projection));

  // Detail: how finely the volume is drawn for what is on screen. The copy of the
  // image follows the zoom: zoomed in, a finer one, down to the finest.
  const detailInput = document.createElement("input");
  detailInput.type = "range";
  detailInput.min = "0";
  detailInput.max = String(DETAIL_PIXELS.length - 1);
  detailInput.step = "1";
  detailInput.className = "detail";
  detailInput.title = "Sharper or faster to draw; zooming in sharpens it too";
  const detailReading = element("span", "reading", "");
  detailReading.title = "The size of a voxel of the copy of the image drawn now";
  detailInput.addEventListener("input", () => {
    detail = Number(detailInput.value);
    drawFinely(viewer);
  });
  card.appendChild(labelled("Detail", detailInput, detailReading));

  // Gain, for the blended projection only: how strongly each voxel adds up.
  const gain = document.createElement("input");
  gain.type = "range";
  gain.min = "-10";
  gain.max = "10";
  gain.step = "0.1";
  gain.className = "gain";
  const gainReading = element("span", "reading", "");
  gain.addEventListener("input", () => {
    for (const layer of imageLayers(viewer)) layer.volumeRenderingGain.value = Number(gain.value);
  });
  const gainRow = labelled("Gain", gain, gainReading);
  card.appendChild(gainRow);

  // Where the specimen is looked at from; the mouse turns it from there.
  const looks = element("div", "segmented");
  for (const [label, orientation] of LOOK_FROM) {
    const button = textButton(label, null, `Look at the specimen from the ${label.toLowerCase()}`);
    button.dataset.look = label.toLowerCase();
    button.addEventListener("click", () => {
      viewer.projectionOrientation.restoreState(orientation);
      fit?.();
    });
    looks.appendChild(button);
  }
  card.appendChild(labelled("Look from", looks));

  // The cross-section planes inside the volume: off for a pure volume.
  const slices = document.createElement("input");
  slices.type = "checkbox";
  slices.className = "slices";
  slices.addEventListener("change", () => {
    viewer.showPerspectiveSliceViews.value = slices.checked;
  });
  card.appendChild(labelled("Show plane", slices));

  const reflect = () => {
    const layers = imageLayers(viewer);
    const mode = layoutOf(viewer) === "3d" ? layers[0]?.volumeRenderingMode.toJSON() ?? volumeMode : volumeMode;
    for (const [name, button] of projections) button.classList.toggle("on", mode === name);
    if (document.activeElement !== detailInput) detailInput.value = String(detail);
    detailReading.textContent = drawnVoxel(viewer);
    const g = layers[0]?.volumeRenderingGain.value ?? 0;
    if (document.activeElement !== gain) gain.value = String(g);
    gainReading.textContent = g.toFixed(1);
    gainRow.classList.toggle("disabled", mode !== "on");
    slices.checked = viewer.showPerspectiveSliceViews.value;
  };
  const watchedLayers = new WeakSet();
  const watch = () => {
    // A layer that arrives while the volume view is open is drawn like the others.
    applyVolumeMode(viewer);
    const first = imageLayers(viewer).find((layer) => watchedLayers.has(layer));
    for (const layer of imageLayers(viewer)) {
      if (watchedLayers.has(layer)) continue;
      watchedLayers.add(layer);
      if (first) {
        layer.volumeRenderingDepthSamplesTarget.value = first.volumeRenderingDepthSamplesTarget.value;
        layer.volumeRenderingGain.value = first.volumeRenderingGain.value;
      }
      layer.volumeRenderingMode.changed.add(reflect);
      layer.volumeRenderingDepthSamplesTarget.changed.add(reflect);
      layer.volumeRenderingGain.changed.add(reflect);
    }
    reflect();
  };
  viewer.layerManager.layersChanged.add(watch);
  viewer.showPerspectiveSliceViews.changed.add(reflect);
  watch();
  // The box and the steps follow the zoom, the point the view turns about, the
  // data shown and the size of the panel.
  const again = () => drawFinely(viewer);
  const moved = () => {
    noteMoving(viewer);
    drawFinely(viewer);
  };
  viewer.perspectiveNavigationState.changed.add(moved);
  viewer.navigationState.changed.add(moved);
  viewer.layerManager.layersChanged.add(again);
  window.addEventListener("resize", again);
  // The copy drawn is the engine's choice, made as it draws: read it now and then.
  setInterval(() => {
    if (!card.hidden) detailReading.textContent = drawnVoxel(viewer);
  }, 500);
  const show = () => {
    card.hidden = layoutOf(viewer) !== "3d";
    drawFinely(viewer);
    reflect();
  };
  viewer.layout.changed.add(show);
  show();
  return card;
}

let drawing = 0;
let moving = false;
let still = null;
let pose = null;

/** Whether the operator is turning, zooming or panning the volume: the page's own
 * changes to the box are not a move, and nor is the same view set again. */
function noteMoving(viewer) {
  const now = [
    ...viewer.projectionOrientation.orientation,
    viewer.perspectiveNavigationState.zoomFactor.value,
    ...viewer.navigationState.position.value,
  ].join();
  const changed = pose !== null && now !== pose;
  pose = now;
  if (!changed || layoutOf(viewer) !== "3d") return;
  moving = true;
  clearTimeout(still);
  still = setTimeout(() => {
    moving = false;
    drawFinely(viewer);
  }, STILL_MS);
}

/** Set the volume view's box and steps for the detail chosen (camera.js), once per frame at most. */
function drawFinely(viewer) {
  if (drawing) return;
  drawing = requestAnimationFrame(() => {
    drawing = 0;
    if (layoutOf(viewer) !== "3d") return;
    const pixels = moving ? Math.max(DETAIL_PIXELS[detail] * WHILE_MOVING, MOVING_PIXELS) : DETAIL_PIXELS[detail];
    const wanted = volumeDrawing(viewer, pixels);
    if (wanted === null) return;
    const box = viewer.perspectiveNavigationState.depthRange;
    if (!(box.value > 0) || Math.abs(box.value - wanted.depth) > 1e-3 * wanted.depth) box.value = wanted.depth;
    for (const layer of imageLayers(viewer)) {
      if (layer.volumeRenderingDepthSamplesTarget.value !== wanted.samples) {
        layer.volumeRenderingDepthSamplesTarget.value = wanted.samples;
      }
    }
  });
}

/** The size of a voxel of the copy the volume view draws from now, in micrometres across. */
function drawnVoxel(viewer) {
  for (const layer of imageLayers(viewer)) {
    const volume = layer.renderLayers.find((render) => "depthSamplesTarget" in render);
    const size = volume?.highestResolutionLoadedVoxelSize;
    if (size) return `${Number((size[0] * 1e6).toPrecision(2))} µm`;
  }
  return "";
}

// -- the channels: one row per engine layer, gathered by acquisition ------------

function channelRow(viewer, managed, contrast) {
  const [, channel] = splitName(managed.name);
  const row = element("div", "channel");
  row.dataset.layer = managed.name;
  const head = element("div", "row");
  const eye = iconButton("eye", "Show or hide this channel");
  eye.classList.add("eye");
  eye.addEventListener("click", () => managed.setVisible(!managed.visible));
  const swatch = element("button", "swatch");
  swatch.type = "button";
  swatch.title = "Change the colour";
  const label = element("span", "label", channel);
  const auto = textButton("Auto", "auto", "Keep setting the contrast from what is on screen");
  auto.addEventListener("click", () => contrast.setAuto(managed.name, !contrast.isAuto(managed.name)));
  head.append(eye, swatch, label, auto);
  row.appendChild(head);

  const layer = managed.layer;
  const controls = element("div", "controls");
  row.appendChild(controls);
  let mounted = null;
  const reflect = () => {
    row.classList.toggle("hidden", !managed.visible);
    eye.classList.toggle("off", !managed.visible);
    eye.innerHTML = managed.visible ? ICONS.eye : ICONS.eyeOff;
    auto.classList.toggle("on", contrast.isAuto(managed.name));
    // The live value, not its JSON: the JSON is empty while the colour equals
    // the shader's default.
    const colour = layer?.shaderControlState?.state?.get("color")?.trackable?.value;
    swatch.style.background = colour?.length === 3
      ? `rgb(${Array.from(colour, (v) => Math.round(v * 255)).join(", ")})`
      : "#ffffff";
    // The colour control's own input is driven by the swatch and not shown.
    // Marked here: the old browser of the Data viewer window knows no :has().
    for (const input of controls.querySelectorAll('input[type="color"]')) {
      input.closest(".neuroglancer-layer-control-container")?.classList.add("colour-control");
    }
  };
  if (layer?.shaderControlState) {
    // The engine's own controls for this layer's shader: the window with its
    // histogram (computed on the GPU once this widget is visible) and the colour.
    mounted = new ShaderControls(layer.shaderControlState, viewer.display, layer, {
      visibility: new WatchableVisibilityPriority(WatchableVisibilityPriority.VISIBLE),
      legendShaderOptions: layer.getLegendShaderOptions?.(),
    });
    controls.appendChild(mounted.element);
    layer.shaderControlState.changed.add(reflect);
    // The controls exist only once the shader has been parsed, a moment later.
    layer.shaderControlState.controls.changed.add(reflect);
    swatch.addEventListener("click", () => controls.querySelector('input[type="color"]')?.click());
    // The engine builds its controls a moment after the shader is read.
    new MutationObserver(reflect).observe(controls, { childList: true, subtree: true });
    // The operator moving the contrast themselves ends Auto for this channel:
    // a press or a key inside the engine's window control, nothing else.
    const moved = (event) => {
      if (event.target.closest?.(".neuroglancer-invlerp-widget")) contrast.moved(managed.name);
    };
    for (const kind of ["pointerdown", "mousedown", "keydown", "wheel"]) {
      controls.addEventListener(kind, moved, true);
    }
  }
  managed.layerChanged.add(reflect);
  reflect();
  return { row, reflect, dispose: () => mounted?.dispose() };
}

function channelsCard(viewer, contrast) {
  const card = element("section", "card channels");
  card.appendChild(cardHead(3, "Channels"));
  const of = element("div", "of", "");
  card.appendChild(of);
  const body = element("div", "groups");
  card.appendChild(body);
  // Of the acquisitions Python lists, the channels of the one selected; with no list, all.
  let listed = false;
  // The rows are kept across updates, one per layer: a layer that stays keeps
  // its row, and with it the engine's controls and whatever is being dragged.
  const rows = new Map();
  const sections = new Map();
  const rebuild = () => {
    const groups = new Map();
    for (const managed of viewer.layerManager.managedLayers) {
      if (!managed.layer || managed.layer.type !== "image") continue;
      const group = about(managed.name)?._acquisition ?? splitName(managed.name)[0];
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(managed);
    }
    const wanted = new Set([...groups.values()].flat().map((managed) => managed.layer));
    for (const [layer, made] of rows) {
      if (wanted.has(layer)) continue;
      made.dispose();
      made.row.remove();
      rows.delete(layer);
    }
    for (const [group, section] of sections) {
      if (groups.has(group)) continue;
      section.remove();
      sections.delete(group);
    }
    const only = listed ? selection.name : null;
    of.textContent = only ?? "";
    of.hidden = only === null;
    card.hidden = groups.size === 0 && only === null;
    card.classList.toggle("several", only === null && groups.size > 1);
    for (const [group, layers] of groups) {
      let section = sections.get(group);
      if (!section) {
        section = element("div", "group");
        section.dataset.group = group;
        section.appendChild(element("div", "group-name", group));
        sections.set(group, section);
      }
      section.hidden = only !== null && group !== only;
      body.appendChild(section); // in Python's order
      for (const managed of layers) {
        let made = rows.get(managed.layer);
        if (!made) {
          made = channelRow(viewer, managed, contrast);
          rows.set(managed.layer, made);
        }
        section.appendChild(made.row);
      }
    }
  };
  let pending = null;
  const later = () => {
    clearTimeout(pending);
    pending = setTimeout(rebuild, 0);
  };
  viewer.layerManager.layersChanged.add(later);
  selection.listeners.push(later);
  card.setListed = (next) => {
    if (listed !== next) {
      listed = next;
      later();
    }
  };
  onAutoChanged(() => {
    for (const made of rows.values()) made.reflect();
  });
  rebuild();
  return card;
}

// -- the sliders: depth and time, along the bottom of the picture -----------------

function axisSlider(viewer, axis, id, describe, changed) {
  const box = element("div", "axis-slider");
  box.id = id;
  box.hidden = true;
  const name = element("span", "name", axis === "z" ? "Z" : "T");
  const input = document.createElement("input");
  input.type = "range";
  input.step = "1";
  input.title = axis === "z" ? "Step through the planes" : "Step through the time points";
  const reading = element("span", "reading", "");
  box.append(name, input, reading);

  const { position } = viewer.navigationState;
  const where = () => {
    const space = position.coordinateSpace.value;
    const index = space?.names?.indexOf(axis) ?? -1;
    if (index === -1 || !space.bounds) return null;
    const low = space.bounds.lowerBounds[index];
    const high = space.bounds.upperBounds[index];
    if (!Number.isFinite(low) || !Number.isFinite(high) || high - low <= 1) return null;
    // Bounds run from the first voxel's near edge to the last one's far edge
    // (-0.5 .. n - 0.5), so voxel i is centred on i and the slider steps
    // through the voxel indices 0 .. n - 1.
    return { index, low: Math.round(low + 0.5), high: Math.round(high - 0.5), scale: space.scales[index], unit: space.units[index] };
  };
  const reflect = () => {
    const found = where();
    box.hidden = found === null;
    changed();
    if (found === null) return;
    input.min = String(found.low);
    input.max = String(found.high);
    // The voxel the engine draws: the one whose span holds the position.
    const value = Math.min(found.high, Math.max(found.low, Math.floor(position.value[found.index] + 0.5)));
    if (document.activeElement !== input) input.value = String(value);
    reading.textContent = describe(value, found);
  };
  input.addEventListener("input", () => {
    const found = where();
    if (found === null) return;
    const next = Float32Array.from(position.value);
    next[found.index] = Number(input.value);
    position.value = next;
  });
  // Dragging done: the keyboard goes back to the picture.
  input.addEventListener("change", () => input.blur());
  position.changed.add(reflect);
  position.coordinateSpace.changed.add(reflect);
  reflect();
  return box;
}

const micrometres = (metres) => {
  const um = metres * 1e6;
  return Math.abs(um) >= 1000 ? `${(um / 1000).toFixed(2)} mm` : `${um.toFixed(Math.abs(um) < 100 ? 1 : 0)} µm`;
};

function sliders(viewer) {
  const bar = element("div", "bottom-bar none");
  // With neither a stack nor a time lapse on screen there is no bar at all. The
  // volume view shows every plane at once: the depth slider is there only
  // while the plane it moves is drawn inside the volume.
  const changed = () => {
    const whole = layoutOf(viewer) === "3d" && !viewer.showPerspectiveSliceViews.value;
    bar.classList.toggle("whole", whole);
    bar.classList.toggle("none", Array.from(bar.children).every((slider) => slider.hidden || (whole && slider.id === "slider-z")));
  };
  viewer.layout.changed.add(changed);
  viewer.showPerspectiveSliceViews.changed.add(changed);
  bar.appendChild(
    axisSlider(viewer, "t", "slider-t", (value, found) => `${value - found.low + 1} / ${found.high - found.low + 1}`, changed),
  );
  bar.appendChild(
    axisSlider(viewer, "z", "slider-z", (value, found) => {
      const count = found.high - found.low + 1;
      const depth = found.unit === "m" ? `${micrometres((value - found.low) * found.scale)}${SEPARATOR}` : "";
      return `${depth}${value - found.low + 1} / ${count}`;
    }, changed),
  );
  changed();
  return bar;
}

// -- what is under the pointer ---------------------------------------------------------

function readout(viewer) {
  const box = element("div", "readout");
  box.id = "readout";
  box.hidden = true;
  let pending = null;
  const draw = () => {
    pending = null;
    const mouse = viewer.mouseState;
    const space = viewer.navigationState.position.coordinateSpace.value;
    if (!mouse.active || !space?.rank) {
      box.hidden = true;
      return;
    }
    const parts = [];
    for (const name of ["x", "y", "z"]) {
      const at = space.names.indexOf(name);
      if (at === -1 || space.units[at] !== "m") continue;
      parts.push(`${name} ${(mouse.position[at] * space.scales[at] * 1e6).toFixed(0)}`);
    }
    box.replaceChildren(element("span", "where", parts.length ? `${parts.join("  ")} µm` : ""));
    for (const managed of viewer.layerManager.managedLayers) {
      if (!managed.visible || managed.layer?.type !== "image") continue;
      let value;
      try {
        value = viewer.layerSelectedValues.get(managed.layer)?.value;
      } catch {
        value = undefined;
      }
      if (Array.isArray(value) || ArrayBuffer.isView(value)) value = value[0];
      if (value === undefined || value === null || typeof value === "object") continue;
      const [, channel] = splitName(managed.name);
      box.appendChild(element("span", "value", `${channel}: ${typeof value === "number" ? Math.round(value) : value}`));
    }
    box.hidden = false;
  };
  const later = () => {
    if (pending === null) pending = setTimeout(draw, 80);
  };
  viewer.mouseState.changed.add(later);
  viewer.layerSelectedValues.changed.add(later);
  return box;
}

// -- Fit, and the Live button of a running acquisition -----------------------------------

function fitButton(fit, framing) {
  const button = element("button", "tool fit");
  button.type = "button";
  button.id = "fit";
  button.innerHTML = `${ICONS.fit}<span>Fit</span>`;
  button.title = "Zoom out to show every tile, and keep doing so as new ones arrive";
  button.addEventListener("click", () => fit());
  // Offered only while the view is the operator's: otherwise it already shows all.
  const reflect = () => {
    button.hidden = framing.value;
  };
  framing.listeners.push(reflect);
  reflect();
  return button;
}

function liveButton(live, following, acquiring) {
  const button = element("button", "tool live");
  button.type = "button";
  button.id = "live";
  const dot = element("span", "dot");
  const text = element("span", "text", "Live");
  button.append(dot, text);
  button.addEventListener("click", () => live());
  const reflect = () => {
    button.hidden = !acquiring.value;
    button.classList.toggle("following", following.value);
    text.textContent = following.value ? "Live" : "Back to live";
    button.title = following.value
      ? "The view follows the acquisition: it shows the newest plane as it arrives"
      : "The view stays where you put it. Press to follow the newest plane again";
  };
  following.listeners.push(reflect);
  acquiring.listeners.push(reflect);
  reflect();
  return button;
}

// -- a message on the picture, such as why a dropped folder did not open ---------

function noticeBox() {
  const box = element("div", "notice");
  box.id = "notice";
  box.hidden = true;
  const text = element("span", "text", "");
  const close = iconButton("close", "Close this message");
  close.classList.add("close");
  close.addEventListener("click", () => {
    box.hidden = true;
  });
  box.append(text, close);
  let shown = 0;
  box.setNotice = (notice) => {
    // A message is shown once, when it is new; once closed it stays closed.
    if (!notice || notice.count === shown) return;
    shown = notice.count;
    text.textContent = notice.text;
    box.hidden = !notice.text;
  };
  return box;
}

// -- instead of a black picture: what the viewer is waiting for -----------------------------

function emptyState(post) {
  const box = element("div", "empty");
  box.id = "empty";
  const title = element("div", "title", "");
  const text = element("div", "text", "");
  const open = textButton("Open a dataset…", "primary", "Pick a .ome.zarr folder");
  open.addEventListener("click", () => post("/api/open"));
  box.append(title, text, open);
  let ui = {};
  let acquisitions = [];
  let layers = 0;
  const reflect = () => {
    const shown = acquisitions.filter((entry) => entry.shown);
    const waiting = shown.filter((entry) => entry.empty === true);
    let words = null;
    if (acquisitions.length === 0) {
      words = ["No acquisition yet", ui.openable
        ? "The next acquisition appears here as it is acquired. You can also open a dataset from disk, or drop its folder onto this window."
        : "The next acquisition appears here as it is acquired."];
    } else if (shown.length === 0) {
      words = ["Nothing is shown", "Tick an acquisition in the list on the right to show it."];
    } else if (waiting.length === shown.length) {
      const entry = waiting[0];
      words = entry.live
        ? [`Waiting for the first planes of ${entry.name}`, "They are shown as soon as the camera delivers them."]
        : [`${entry.name} holds no image data yet`, "Its tiles are shown as they are written."];
    } else if (layers === 0) {
      words = ["Opening…", ""];
    }
    box.hidden = words === null;
    if (words === null) return;
    [title.textContent, text.textContent] = words;
    text.hidden = !words[1];
    open.hidden = !(ui.openable === true && acquisitions.length === 0);
  };
  box.setUi = (next) => {
    ui = next;
    reflect();
  };
  box.setAcquisitions = (next) => {
    acquisitions = next;
    reflect();
  };
  box.setLayers = (count) => {
    layers = count;
    reflect();
  };
  reflect();
  return box;
}

// -- a thin bar while the picture is still filling in ----------------------------------------

function loadingBar(viewer) {
  const bar = element("div", "loading");
  bar.id = "loading";
  const fill = element("div", "fill");
  bar.appendChild(fill);
  let since = null;
  const reflect = () => {
    let needed = 0;
    let available = 0;
    for (const managed of viewer.layerManager.managedLayers) {
      if (!managed.visible) continue;
      for (const renderLayer of managed.layer?.renderLayers ?? []) {
        const progress = renderLayer.layerChunkProgressInfo;
        if (!progress) continue;
        needed += progress.numVisibleChunksNeeded;
        available += progress.numVisibleChunksAvailable;
      }
    }
    const busy = needed > 0 && available < needed;
    if (!busy) since = null;
    else if (since === null) since = performance.now();
    // Shown only for a wait long enough to be felt, so it does not flicker.
    bar.classList.toggle("busy", busy && performance.now() - since > 250);
    fill.style.width = needed > 0 ? `${Math.round((available / needed) * 100)}%` : "0";
  };
  viewer.chunkManager.layerChunkStatisticsUpdated.add(reflect);
  setInterval(reflect, 300);
  return bar;
}

// -- how to move around: said once, on request ------------------------------------------------

function helpBox() {
  const wrap = element("div", "help");
  const button = iconButton("help", "How to move around");
  button.id = "help";
  const sheet = element("div", "sheet");
  sheet.hidden = true;
  const lines = [
    ["Drag", "move the picture"],
    ["Scroll", "zoom in and out"],
    ["Shift + scroll, or , and .", "step through the planes"],
    ["[ and ]", "step through the time points"],
    ["3D: drag", "turn the specimen; Shift + drag moves it"],
  ];
  for (const [keys, does] of lines) {
    const line = element("div", "line");
    line.append(element("span", "keys", keys), element("span", "does", does));
    sheet.appendChild(line);
  }
  button.addEventListener("click", () => {
    sheet.hidden = !sheet.hidden;
  });
  wrap.append(button, sheet);
  return wrap;
}

// -- the mouse, made the way image viewers have it -------------------------------------------

function bindMouse(viewer) {
  const { sliceView, perspectiveView } = viewer.inputEventBindings;
  // Scrolling zooms, as in every map and image viewer; the planes are stepped
  // through with Shift, the slider or the keys.
  sliceView.set("at:wheel", { action: "zoom-via-wheel", preventDefault: true });
  sliceView.set("at:shift+wheel", { action: "z+1-via-wheel", preventDefault: true });
  // The flat view stays flat: no tilting the plane by accident.
  sliceView.set("at:shift+mousedown0", { action: "translate-via-mouse-drag", stopPropagation: true });
  sliceView.set("at:touchrotate", "mesospim-nothing");
  for (const map of [sliceView, perspectiveView]) {
    for (const event of ["keyr", "keye", "shift+arrowdown", "shift+arrowup", "shift+arrowleft", "shift+arrowright",
      "at:control+mousedown0", "at:alt+mousedown0", "at:control+alt+mousedown2", "at:shift+dblclick0", "at:mousedown2"]) {
      map.set(event, "mesospim-nothing");
    }
  }
}

// -- the panel, as one of the engine's own side panels ---------------------------

class ControlPanel extends SidePanel {
  constructor(manager, location, viewer, parts) {
    super(manager, location);
    this.element.classList.add("mesospim-panel");
    this.element.draggable = false;
    const body = element("div", "panel-body");
    const head = element("div", "panel-head");
    const fold = iconButton("panel", "Hide the controls");
    fold.classList.add("fold");
    fold.addEventListener("click", () => this.close());
    head.append(element("span", "title", "Data viewer"), fold);
    body.append(head, parts.load, parts.acquisitions, parts.channels, parts.volume);
    this.addBody(body);
  }
}

export function mountPanel(viewer, { fit, live, framing, following, acquiring, post, contrast }) {
  const manager = viewer.sidePanelManager;
  const location = new TrackableSidePanelLocation(
    { side: "right", col: 0, row: 0, flex: 1, size: 320, minSize: 260, visible: true },
  );
  // The cards are made once and live as long as the page; the engine's panel
  // that holds them is made anew each time it is unfolded.
  const parts = {
    load: loadCard(post),
    acquisitions: acquisitionsCard(viewer, post),
    channels: channelsCard(viewer, contrast),
    volume: volumeCard(viewer, fit),
  };
  manager.registerPanel({
    location,
    makePanel: () => new ControlPanel(manager, location, viewer, parts),
  });
  // A pure volume: no cross-section planes drawn inside it unless asked for.
  viewer.showPerspectiveSliceViews.value = false;
  bindMouse(viewer);

  // The picture's column carries everything drawn on the picture. The manager
  // rewrites that column's children whenever it lays the panels out, so ours
  // are put back after every frame that dropped them.
  const stage = manager.centerColumn;
  stage.style.position = "relative";
  // The volume view would grow the panel row past the window and clip its
  // bottom strip, sliders and scale bar included: the row is a flex child
  // that will not shrink below its content unless told, so it is told.
  manager.element.style.minHeight = "0";
  stage.style.minHeight = "0";
  stage.style.overflow = "hidden";
  const overlay = element("div", "stage-overlay");

  const tools = element("div", "tools");
  tools.append(viewSwitch(viewer, fit), fitButton(fit, framing), liveButton(live, following, acquiring));
  overlay.appendChild(tools);

  const corner = element("div", "corner");
  const unfold = iconButton("panel", "Show the controls");
  unfold.id = "fold";
  unfold.addEventListener("click", () => {
    location.visible = true;
  });
  corner.append(helpBox(), unfold);
  overlay.appendChild(corner);
  const reflectFold = () => {
    unfold.style.display = location.visible ? "none" : "";
  };
  location.locationChanged.add(reflectFold);
  reflectFold();

  const notice = noticeBox();
  const empty = emptyState(post);
  // Along the bottom, clear of the engine's scale bar at the left: what is
  // under the pointer, and beneath it the sliders.
  const bottom = element("div", "bottom");
  bottom.append(readout(viewer), sliders(viewer));
  overlay.append(loadingBar(viewer), notice, empty, bottom);
  const countLayers = () => empty.setLayers(viewer.layerManager.managedLayers.length);
  viewer.layerManager.layersChanged.add(countLayers);
  countLayers();

  const keep = () => {
    if (!overlay.isConnected) stage.appendChild(overlay);
  };
  keep();
  viewer.display.updateFinished.add(keep);

  // The picture: fluorescence on black, with the engine's scale bar and
  // without its overlays.
  viewer.crossSectionBackgroundColor.restoreState("#000000");
  viewer.showScaleBar.value = true;
  viewer.showAxisLines.value = false;
  viewer.showDefaultAnnotations.value = false;
  return {
    location,
    setAcquisitions(acquisitions) {
      parts.acquisitions.setAcquisitions(acquisitions);
      parts.channels.setListed(acquisitions.length > 0);
      empty.setAcquisitions(acquisitions);
    },
    setUi(ui) {
      parts.load.setUi(ui);
      parts.acquisitions.setUi(ui);
      empty.setUi(ui);
    },
    setNotice: notice.setNotice,
  };
}
