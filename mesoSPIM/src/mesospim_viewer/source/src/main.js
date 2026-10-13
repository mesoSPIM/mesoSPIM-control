/**
 * A native neuroglancer page that shows whatever the Python side publishes.
 *
 * The page does four things:
 *
 * 1. builds a stock neuroglancer viewer: with its own panels ("full"), with
 *    our own panel beside a bare engine ("simple", panel.js), or as a bare
 *    canvas for a host that draws its own controls ("bare");
 * 2. waits on `/api/state` and brings the layers into line with the scene, in
 *    place (layers.js): a tile that lands is a source added, never a layer
 *    rebuilt;
 * 3. hears which files have landed in the stores it shows and has the engine
 *    read exactly those (engine/landed.js), and where the newest plane of a
 *    running acquisition is (camera.js);
 * 4. reports the camera to `/api/view` and a double-click to `/api/pick`.
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
import { registerActionListener } from "neuroglancer/unstable/util/event_action_map.js";
import {
  acquiring,
  fitEverything,
  following,
  followAgain,
  framing,
  globalSpace,
  KEEP_CLEAR,
  layoutOf,
  setLayout,
  goToNewest,
  moveTo,
  setNewest,
  toFirstTimePoint,
  watchOperator,
} from "./camera.js";
import { isAuto, operatorMoved, setAuto, watchContrast } from "./contrast.js";
import { landed, landedAnywhere } from "./engine/landed.js";
import { applyLayers, watchRetiring } from "./layers.js";
import { mountPanel } from "./panel.js";
import "./page.css";

const POLL_WAIT_S = 25;
const RETRY_MS = 1000;
const SETTLE_MS = 100;
const SETTLE_LIMIT_MS = 30_000;
const REPORT_MS = 150;

// -- talking to Python ---------------------------------------------------------

async function fetchState(held, wait) {
  const query = `since=${held.version}&events=${held.sequence}&follow=${held.follow}&wait=${wait}`;
  const response = await fetch(`/api/state?${query}`);
  if (!response.ok) throw new Error(`state: ${response.status}`);
  return response.json();
}

export function post(route, payload) {
  return fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
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
    transparentBackground: ui.transparent,
  });
  setDefaultInputEventBindings(viewer.inputEventBindings);
  bindDefaultCopyHandler(viewer);
  bindDefaultPasteHandler(viewer);
  if (ui.transparent) {
    document.documentElement.dataset.transparent = "";
    // The engine's axis-lines overlay blends against destination alpha
    // (axes_lines.js) and leaves the whole picture clear, so a transparent
    // ground does without it. Annotations and the scale bar are unaffected.
    viewer.showAxisLines.value = false;
  }
  window.viewer = viewer;
  return viewer;
}

// -- the camera, by axis name --------------------------------------------------

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
    layout: layoutOf(viewer),
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

// The space the picture is drawn in, as Python gives it: x, y, z at the finest
// voxel size shown. Set before the first source loads, so that a step along z
// is one plane of the finest stack whichever source arrives first.
function setDimensions(viewer, dimensions) {
  const wanted = Object.entries(dimensions ?? {});
  if (wanted.length === 0) return;
  const space = viewer.coordinateSpace.value;
  const held = new Map((space?.names ?? []).map((name, i) => [name, space.scales[i]]));
  const differs = wanted.some(([name, [scale]]) => {
    const now = held.get(name);
    return now === undefined || Math.abs(now - scale) > 1e-9 * Math.max(Math.abs(now), Math.abs(scale));
  });
  if (!differs) return;
  // Where the view is, kept in micrometres across the change of voxel size.
  const { position } = viewer.navigationState;
  const names = Array.from(space?.names ?? []);
  const at = Object.fromEntries(names.map((name, i) => [name, position.value[i] * space.scales[i]]));
  viewer.coordinateSpace.restoreState(dimensions);
  const next = viewer.coordinateSpace.value;
  if (next?.rank && names.length) {
    const moved = Float32Array.from(position.value);
    next.names.forEach((name, i) => {
      if (at[name] !== undefined && next.scales[i]) moved[i] = at[name] / next.scales[i];
    });
    position.value = moved;
  }
}

const acquisitionsOf = (layers) => new Set(layers.map((layer) => layer._acquisition));

// -- keeping up with Python ----------------------------------------------------

function applyScene(viewer, answer, seen) {
  const state = answer.state ?? {};
  viewer.panel?.setUi(answer.ui ?? {});
  viewer.panel?.setAcquisitions(answer.acquisitions ?? []);
  viewer.panel?.setNotice(answer.notice);
  // The layout is Python's to set, not to hold: it is taken when Python changes
  // it, and otherwise the 2D/3D switch is the operator's.
  if (state.layout && state.layout !== seen.layout) {
    if (layoutOf(viewer) !== state.layout) setLayout(viewer, state.layout);
    seen.layout = state.layout;
  }
  framing.busy += 1;
  applyLayers(viewer, state.layers ?? [], (left) => {
    if (left === 0 && (state.layers ?? []).length > 0) {
      // Nothing of the old picture stays: the engine's space is empty now, and
      // the new picture gets a fresh one, with the view in its middle and
      // framing everything. (Left alone, the engine would keep the old
      // position against the new picture's axes.)
      viewer.navigationState.position.reset();
      seen.fresh = true;
    }
    setDimensions(viewer, state.dimensions);
  });
  const camera = answer.cameraVersion !== seen.cameraVersion ? answer.camera ?? {} : null;
  seen.cameraVersion = answer.cameraVersion;
  // A fit Python asked for is kept until it can be done: the sources it is
  // meant for may arrive with a later scene.
  if (camera?.fit) seen.fit = true;
  const acquisitions = acquisitionsOf(state.layers ?? []);
  const opened = [...acquisitions].some((name) => !seen.shown.has(name));
  seen.shown = acquisitions;
  // Axes are named, and the engine can only find a name once a source has
  // said what its axes are: so this waits for the sources, then chooses the
  // axes on screen, and only then moves or fits the camera. A view still
  // framing the picture is fitted again, to take in what has just landed.
  const turn = ++seen.turn;
  whenSettled(viewer).then(() => {
    try {
      if (state.displayDimensions) {
        viewer.navigationState.pose.displayDimensions.restoreState(state.displayDimensions);
      }
      if (opened) toFirstTimePoint(viewer);
      if (camera?.position) moveTo(viewer, camera.position);
      if (turn !== seen.turn) return; // a later scene is on its way: it does the framing
      if (seen.fit || seen.fresh || (!camera?.position && framing.value)) {
        if (fitEverything(viewer)) {
          seen.fit = false;
          seen.fresh = false;
        }
      }
      if (following.value) goToNewest(viewer);
    } finally {
      framing.busy -= 1;
    }
  });
}

async function follow(viewer, first) {
  const held = { version: -1, sequence: -1, follow: -1 };
  const seen = { cameraVersion: first?.cameraVersion ?? 0, shown: new Set(), turn: 0, layout: null, fit: false, fresh: false };
  let answer = first;
  for (;;) {
    if (answer) {
      if (answer.state && answer.version !== held.version) applyScene(viewer, answer, seen);
      held.version = answer.version;
      // A page that fell behind the log of events reads again whatever it found missing.
      if (answer.resync) landedAnywhere(viewer);
      for (const event of answer.events ?? []) {
        if (event.type === "landed") landed(viewer, event.store, event.files);
      }
      held.sequence = answer.sequence ?? held.sequence;
      const count = answer.follow?.count ?? 0;
      if (count !== held.follow) {
        held.follow = count;
        setNewest(viewer, answer.follow);
      }
    }
    try {
      answer = await fetchState(held, POLL_WAIT_S);
    } catch {
      answer = null;
      await sleep(RETRY_MS);
    }
  }
}

async function main() {
  let first = null;
  try {
    first = await fetchState({ version: -1, sequence: -1, follow: -1 }, 0);
  } catch {
    // Python is not answering yet; the loop below keeps asking.
  }
  const ui = readUi(first);
  const viewer = buildViewer(ui);
  const contrast = watchContrast(viewer);
  if (ui.chrome === "simple") {
    Object.assign(KEEP_CLEAR, { top: 48, bottom: 56 });
    viewer.panel = mountPanel(viewer, {
      fit: () => fitEverything(viewer),
      live: () => followAgain(viewer),
      framing,
      following,
      acquiring,
      post,
      contrast: { ...contrast, isAuto, setAuto: (name, on) => setAuto(viewer, name, on), moved: (name) => operatorMoved(viewer, name) },
    });
  }
  bindReports(viewer);
  watchOperator(viewer);
  watchRetiring(viewer);
  // For the tests, and for a look from the browser's console.
  window.mesospim = {
    framing,
    following,
    acquiring,
    isAuto,
    setAuto: (name, on) => setAuto(viewer, name, on),
    fit: () => fitEverything(viewer),
    live: () => followAgain(viewer),
    layout: () => layoutOf(viewer),
  };
  await follow(viewer, first);
}

main();
