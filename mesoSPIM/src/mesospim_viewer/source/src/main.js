/**
 * A native neuroglancer page that shows whatever the Python side publishes.
 *
 * The page does three things and nothing else:
 *
 * 1. builds a stock neuroglancer viewer: with its own panels ("full"), with
 *    our own panel beside a bare engine ("simple", panel.js), or as a bare
 *    canvas for a host that draws its own controls ("bare");
 * 2. long-polls `/api/state` and brings the layers into line with it, keeping
 *    the operator's own adjustments on layers that did not change;
 * 3. reports the camera to `/api/view` and a double-click to `/api/pick`.
 *
 * Until the operator pans or zooms, the view keeps framing everything shown,
 * so tiles landing during an acquisition come into view as they arrive.
 *
 * Everything about what is shown -- which stores, where they sit, how their
 * channels mix -- is decided in Python and arrives as ordinary neuroglancer
 * layer JSON.
 */
// First: what Qt WebEngine 5.15 (Chromium 83) lacks; see legacy_browser.js.
import "./legacy_browser.js";
import "neuroglancer/unstable/util/polyfills.js";
import "neuroglancer/unstable/layer/enabled_frontend_modules.js";
import "neuroglancer/unstable/datasource/enabled_frontend_modules.js";
import "neuroglancer/unstable/kvstore/enabled_frontend_modules.js";
import "neuroglancer/unstable/ui/default_viewer.css";
import { makeDefaultViewer } from "neuroglancer/unstable/ui/default_viewer.js";
import { setDefaultInputEventBindings } from "neuroglancer/unstable/ui/default_input_event_bindings.js";
import {
  bindDefaultCopyHandler,
  bindDefaultPasteHandler,
} from "neuroglancer/unstable/ui/default_clipboard_handling.js";
import { makeLayer, deleteLayer } from "neuroglancer/unstable/layer/index.js";
import { registerActionListener } from "neuroglancer/unstable/util/event_action_map.js";
import { mountPanel, SEPARATOR } from "./panel.js";
import "./page.css";

const POLL_WAIT_S = 25;
const RETRY_MS = 1000;
const SETTLE_MS = 100;
const SETTLE_LIMIT_MS = 30_000;
const REPORT_MS = 150;
const FIT_MARGIN = 1.15;

// -- talking to Python ---------------------------------------------------------

async function fetchState(since, wait) {
  const response = await fetch(`/api/state?since=${since}&wait=${wait}`);
  if (!response.ok) throw new Error(`state: ${response.status}`);
  return response.json();
}

function post(route, payload) {
  return fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => undefined);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// -- the viewer ----------------------------------------------------------------

function readUi(first) {
  const params = new URLSearchParams(window.location.search);
  const ui = { chrome: "full", transparent: false, ...(first?.ui ?? {}) };
  if (params.get("ui")) ui.chrome = params.get("ui");
  if (params.has("transparent")) ui.transparent = params.get("transparent") !== "0";
  return ui;
}

function buildViewer(ui) {
  const native = ui.chrome === "full";
  document.documentElement.dataset.chrome = ui.chrome;
  const viewer = makeDefaultViewer({
    target: document.getElementById("engine"),
    showUIControls: native,
    showTopBar: native,
    showLayerPanel: native,
    showLocation: native,
    showPanelBorders: native,
    showLayerDialog: false,
    resetStateWhenEmpty: false,
  });
  setDefaultInputEventBindings(viewer.inputEventBindings);
  bindDefaultCopyHandler(viewer);
  bindDefaultPasteHandler(viewer);
  if (ui.transparent) {
    document.documentElement.dataset.transparent = "";
    viewer.display.transparentBackground = true;
    // The engine's axis-lines overlay blends against destination alpha
    // (axes_lines.js) and leaves the whole picture clear, so a transparent
    // ground does without it. Annotations and the scale bar are unaffected.
    viewer.showAxisLines.value = false;
    viewer.display.scheduleRedraw();
  }
  if (ui.chrome === "simple") {
    viewer.panel = mountPanel(viewer, { fit: () => fitEverything(viewer) });
  }
  window.viewer = viewer;
  return viewer;
}

// -- the camera, by axis name --------------------------------------------------

function globalSpace(viewer) {
  return viewer.navigationState.position.coordinateSpace.value;
}

function describePoint(viewer, coordinates) {
  const space = globalSpace(viewer);
  return {
    names: Array.from(space?.names ?? []),
    scales: Array.from(space?.scales ?? []),
    units: Array.from(space?.units ?? []),
    position: Array.from(coordinates ?? []),
  };
}

function reportView(viewer) {
  const { position, zoomFactor } = viewer.navigationState;
  post("/api/view", {
    ...describePoint(viewer, position.value),
    crossSectionScale: zoomFactor.value,
    layout: viewer.layout.toJSON(),
  });
}

function bindReports(viewer) {
  let pending = null;
  viewer.navigationState.changed.add(() => {
    clearTimeout(pending);
    pending = setTimeout(() => reportView(viewer), REPORT_MS);
  });
  // A double-click names a point: the host may drive its stage there.
  const { sliceView, perspectiveView } = viewer.inputEventBindings;
  sliceView.set("at:dblclick0", "mesospim-pick");
  perspectiveView.set("at:dblclick0", "mesospim-pick");
  registerActionListener(document.getElementById("engine"), "mesospim-pick", () => {
    const mouse = viewer.mouseState;
    if (!mouse.active) return;
    post("/api/pick", describePoint(viewer, mouse.position));
  });
}

function settled(viewer) {
  const space = globalSpace(viewer);
  if (!space?.rank) return false;
  return viewer.layerManager.managedLayers.every((managed) =>
    (managed.layer?.dataSources ?? []).every((source) => source.loadState !== undefined),
  );
}

async function whenSettled(viewer) {
  const until = Date.now() + SETTLE_LIMIT_MS;
  while (!settled(viewer) && Date.now() < until) await sleep(SETTLE_MS);
  return settled(viewer);
}

function moveTo(viewer, named) {
  const { position } = viewer.navigationState;
  const space = globalSpace(viewer);
  if (!space?.rank) return;
  const target = Float32Array.from(position.value);
  space.names.forEach((name, index) => {
    const wanted = named[name];
    if (typeof wanted !== "number") return;
    // Python speaks micrometres and seconds; the engine counts voxels of a
    // space whose scales are in metres and seconds.
    const factor = space.units[index] === "m" ? 1e-6 : 1;
    target[index] = (wanted * factor) / space.scales[index];
  });
  position.value = target;
}

// The view frames everything shown, again after every change, until the
// operator pans or zooms it: then it is theirs, until a fit is asked for
// (Python's fit(), or the 2D/3D switch) and it follows again.
const framing = { following: true, fitting: false, fitted: null };

// What the operator moves when they pan or zoom: the two axes across the
// screen and the zoom of both views. Depth and time are left out, so stepping
// through planes or time points does not stop the view from following.
function framed(viewer) {
  const { position, pose, zoomFactor } = viewer.navigationState;
  const drawn = Array.from(pose.displayDimensionRenderInfo.value?.displayDimensionIndices ?? []);
  return [
    ...drawn.slice(0, 2).filter((axis) => axis >= 0).map((axis) => position.value[axis]),
    zoomFactor.value,
    viewer.perspectiveNavigationState.zoomFactor.value,
  ];
}

function watchOperator(viewer) {
  const moved = () => {
    if (framing.fitting || !framing.fitted) return;
    const now = framed(viewer);
    const held = framing.fitted;
    const changed = now.length !== held.length ||
      now.some((value, i) => Math.abs(value - held[i]) > 1e-6 * Math.max(1, Math.abs(held[i])));
    if (changed) framing.following = false;
  };
  viewer.navigationState.changed.add(moved);
  viewer.perspectiveNavigationState.changed.add(moved);
}

function fitEverything(viewer) {
  framing.fitting = true;
  try {
    fitCamera(viewer);
  } finally {
    framing.fitting = false;
  }
  framing.fitted = framed(viewer);
  framing.following = true;
}

function fitCamera(viewer) {
  const { position, pose, zoomFactor } = viewer.navigationState;
  const space = globalSpace(viewer);
  if (!space?.rank) return;
  const render = pose.displayDimensionRenderInfo.value;
  const drawn = Array.from(render?.displayDimensionIndices ?? []).filter((axis) => axis >= 0);
  const { lowerBounds, upperBounds } = space.bounds;
  const extent = (axis) => {
    const low = lowerBounds[axis];
    const high = upperBounds[axis];
    return Number.isFinite(low) && Number.isFinite(high) ? high - low : null;
  };
  const middle = Float32Array.from(position.value);
  for (const axis of drawn.slice(0, 2)) {
    if (extent(axis) !== null) middle[axis] = (lowerBounds[axis] + upperBounds[axis]) / 2;
  }
  position.value = middle;

  let flat = null;
  let volume = null;
  for (const panel of viewer.display.panels) {
    if ("sliceView" in panel) flat = panel.renderViewport;
    else if ("sliceViews" in panel) volume = panel.renderViewport;
  }
  let fit = 0;
  drawn.slice(0, 2).forEach((axis, slot) => {
    const across = extent(axis);
    const pixels = slot === 0 ? flat?.logicalWidth : flat?.logicalHeight;
    if (across === null || !pixels) return;
    fit = Math.max(fit, (across * render.canonicalVoxelFactors[slot]) / pixels);
  });
  if (fit > 0) zoomFactor.value = fit * FIT_MARGIN;
  let boxFit = 0;
  const smaller = Math.min(volume?.logicalWidth ?? 0, volume?.logicalHeight ?? 0);
  drawn.slice(0, 3).forEach((axis, slot) => {
    const across = extent(axis);
    if (across === null || !smaller) return;
    boxFit = Math.max(boxFit, (across * render.canonicalVoxelFactors[slot] * volume.logicalHeight) / smaller);
  });
  if (boxFit > 0) viewer.perspectiveNavigationState.zoomFactor.value = boxFit * FIT_MARGIN;
}

// An acquisition opens on its first time point. Left to itself the engine
// starts in the middle of every axis it does not draw, which for a time-lapse
// is a time point in the middle of the run. Later, the time point is the
// operator's: a tile landing in an acquisition already shown leaves it alone.
function toFirstTimePoint(viewer) {
  const { position } = viewer.navigationState;
  const space = globalSpace(viewer);
  const axis = space?.names?.indexOf("t") ?? -1;
  if (axis === -1 || !Number.isFinite(space.bounds.lowerBounds[axis])) return;
  const start = Float32Array.from(position.value);
  // Time point i is drawn over i - 0.5 .. i + 0.5; the first starts at the lower bound.
  start[axis] = space.bounds.lowerBounds[axis] + 0.5;
  position.value = start;
}

function acquisitionsOf(layers) {
  return new Set(layers.map((layer) => layer.name.split(SEPARATOR)[0]));
}

// -- the layers ----------------------------------------------------------------

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// What Python last asked for, per layer name. A layer is rebuilt only when
// Python's own description of it changes; what the operator has adjusted on it
// in the meantime is kept.
const lastAsked = new Map();

// Fields the operator may have changed in the engine's panel, carried across a
// rebuild wherever Python did not change them itself.
const OPERATOR_FIELDS = [
  "shaderControls",
  "opacity",
  "blend",
  "visible",
  "volumeRendering",
  "volumeRenderingGain",
  "volumeRenderingDepthSamples",
];

function carryAdjustments(spec, before, held) {
  const merged = { ...spec };
  for (const field of OPERATOR_FIELDS) {
    if (held[field] === undefined) continue;
    if (before && same(before[field], spec[field])) merged[field] = held[field];
  }
  if (held.shaderControls && same(before?.shader, spec.shader)) {
    merged.shaderControls = { ...(spec.shaderControls ?? {}), ...held.shaderControls };
  }
  return merged;
}

// The engine remembers what it read about a store for as long as the page
// lives, so a store that has grown on disk would be rebuilt from the old
// description. Forgetting its entries makes the next layer read it again;
// holders of decoded image (the entries naming a constructor) are left alone.
function forgetStore(viewer, url) {
  const remembered = viewer.chunkManager?.memoize?.map;
  const folder = url.split("|")[0];
  if (!remembered || !folder) return;
  for (const key of [...remembered.keys()]) {
    if (key.includes(folder) && !key.includes('"constructorId"')) remembered.delete(key);
  }
}

function applyLayers(viewer, specs) {
  const manager = viewer.layerManager;
  const wanted = new Set(specs.map((spec) => spec.name));
  for (const managed of [...manager.managedLayers]) {
    if (wanted.has(managed.name)) continue;
    deleteLayer(managed);
    lastAsked.delete(managed.name);
  }
  specs.forEach((spec, index) => {
    const before = lastAsked.get(spec.name);
    let managed = manager.getLayerByName(spec.name);
    if (managed && before && same(before, spec)) return;
    // `_revision` is Python's, not the engine's: it changes when a store has
    // grown, so that an otherwise identical layer is read again.
    const { _revision, ...forEngine } = spec;
    let description = forEngine;
    if (managed) {
      // The engine's JSON leaves out a value that equals its own default, so the
      // opacity is read live: an operator's 0.5 is a choice even if it is the default.
      const held = { ...(managed.toJSON() ?? {}), visible: managed.visible };
      if (managed.layer?.opacity) held.opacity = managed.layer.opacity.value;
      description = carryAdjustments(forEngine, before, held);
      deleteLayer(managed);
      if (before && before._revision !== _revision) {
        for (const source of spec.source ?? []) forgetStore(viewer, source.url ?? source);
      }
    }
    managed = makeLayer(viewer.layerSpecification, spec.name, description);
    viewer.layerSpecification.add(managed, index);
    lastAsked.set(spec.name, spec);
  });
  specs.forEach((spec, wanted) => {
    const here = manager.managedLayers.findIndex((managed) => managed.name === spec.name);
    if (here !== -1 && here !== wanted) manager.reorderManagedLayer(here, wanted);
  });
}

// -- keeping up with Python ----------------------------------------------------

async function follow(viewer, first) {
  let version = -1;
  let cameraVersion = first?.cameraVersion ?? 0;
  let answer = first;
  let shown = new Set();
  for (;;) {
    if (answer && answer.version !== version) {
      version = answer.version;
      viewer.panel?.setChoices(answer.choices);
      const state = answer.state ?? {};
      if (state.layout && viewer.layout.toJSON() !== state.layout) viewer.layout.restoreState(state.layout);
      applyLayers(viewer, state.layers ?? []);
      const camera = answer.cameraVersion !== cameraVersion ? answer.camera ?? {} : null;
      cameraVersion = answer.cameraVersion;
      const acquisitions = acquisitionsOf(state.layers ?? []);
      const opened = [...acquisitions].some((name) => !shown.has(name));
      shown = acquisitions;
      // Axes are named, and the engine can only find a name once a source has
      // said what its axes are: so this waits for the sources, then chooses the
      // axes on screen, and only then moves or fits the camera. A view still
      // following the picture is fitted again, to take in what has just landed.
      whenSettled(viewer).then(() => {
        if (state.displayDimensions) {
          viewer.navigationState.pose.displayDimensions.restoreState(state.displayDimensions);
        }
        if (opened) toFirstTimePoint(viewer);
        if (camera?.position) moveTo(viewer, camera.position);
        if (camera?.fit || (!camera?.position && framing.following)) fitEverything(viewer);
      });
    }
    try {
      answer = await fetchState(version, POLL_WAIT_S);
    } catch {
      answer = null;
      await sleep(RETRY_MS);
    }
  }
}

async function main() {
  let first = null;
  try {
    first = await fetchState(-1, 0);
  } catch {
    // Python is not answering yet; the loop below keeps asking.
  }
  const viewer = buildViewer(readUi(first));
  bindReports(viewer);
  watchOperator(viewer);
  await follow(viewer, first);
}

main();
