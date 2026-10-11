/**
 * Where the picture looks: framing everything shown, and following a running
 * acquisition to its newest plane.
 *
 * Two things the page does on its own, each until the operator takes over and
 * each given back with one button:
 *
 * - **Framing.** The view frames every picture shown, again after each tile
 *   that lands, until the operator pans or zooms: then it is theirs, until
 *   Fit is pressed (or Python's fit(), or the 2D/3D switch).
 * - **Following.** While the microscope is acquiring, the view sits on the
 *   newest plane that has arrived, until the operator steps through depth or
 *   time themselves: then it stays where they put it, until Live is pressed.
 *
 * The volume view (3D) shows every plane at once and turns about the point it
 * is centred on, so there it is centred on the middle of the stack, and
 * following goes to the newest time point only. Back in 2D the view is on the
 * plane it showed before, or on the newest one while it follows a run.
 *
 * They are independent: zooming into the tile being acquired does not stop the
 * planes from coming, and stepping back through a stack does not stop the view
 * from taking in new tiles.
 */
import { isLoaded, want } from "./engine/landed.js";

const FIT_MARGIN = 1.08;
// The volume is framed with more room: turned, it is wider than from the top.
const VOLUME_MARGIN = 1.35;
// How long the view waits for the plane it is about to step to.
const AWAIT_MS = 600;
// What the simple interface draws over the picture, in pixels (panel.css).
export const KEEP_CLEAR = { top: 0, bottom: 0 };

/** The layout the picture is drawn in, by name: "xy", "3d"... */
export function layoutOf(viewer) {
  const layout = viewer.layout.toJSON();
  return typeof layout === "string" ? layout : layout?.type;
}

// The plane the 2D view showed when the volume view took over.
let planeBefore3d = null;

/** Change the layout, by name. Leaving the volume view goes back to a plane:
 * the newest while following a run, or the one shown before. */
export function setLayout(viewer, name) {
  const was = layoutOf(viewer);
  const depth = axisIndex(viewer, "z");
  if (name === "3d" && was !== "3d" && depth !== -1) planeBefore3d = viewer.navigationState.position.value[depth];
  viewer.layout.restoreState(name);
  if (name === "3d" || was !== "3d") return;
  if (following.value && newest !== null) goToNewest(viewer);
  else if (planeBefore3d !== null && depth !== -1) moveQuietly(viewer, depth, planeBefore3d);
  planeBefore3d = null;
}

/** Put one axis of the view somewhere without it counting as the operator stepping away. */
function moveQuietly(viewer, axis, value) {
  const { position } = viewer.navigationState;
  following.moving = true;
  try {
    const moved = Float32Array.from(position.value);
    moved[axis] = value;
    position.value = moved;
    if (following.placed) following.placed = placedNow(viewer);
  } finally {
    following.moving = false;
  }
}

export function globalSpace(viewer) {
  return viewer.navigationState.position.coordinateSpace.value;
}

function axisIndex(viewer, name) {
  return globalSpace(viewer)?.names?.indexOf(name) ?? -1;
}

/** One listener list with a current value. */
function watched(initial) {
  return {
    value: initial,
    listeners: [],
    set(next) {
      if (next === this.value) return;
      this.value = next;
      for (const listener of this.listeners) listener(next);
    },
  };
}

// Whether the view is still framing everything shown.
// `busy` counts the scenes being put on screen: while layers come and go the
// engine moves the view itself, and that is not the operator.
export const framing = { ...watched(true), fitting: false, fitted: null, busy: 0 };
// Whether the view goes to the newest plane, and whether there is one to go to.
export const following = { ...watched(true), moving: false, placed: null };
export const acquiring = watched(false);

// -- framing ------------------------------------------------------------------------

// What the operator moves when they pan or zoom: the two axes across the
// screen and the zoom of both views. Depth and time are left out.
function framed(viewer) {
  const { position, pose, zoomFactor } = viewer.navigationState;
  const drawn = Array.from(pose.displayDimensionRenderInfo.value?.displayDimensionIndices ?? []);
  return [
    ...drawn.slice(0, 2).filter((axis) => axis >= 0).map((axis) => position.value[axis]),
    zoomFactor.value,
    viewer.perspectiveNavigationState.zoomFactor.value,
  ];
}

const differs = (now, was) =>
  now.length !== was.length ||
  now.some((value, i) => Math.abs(value - was[i]) > 1e-6 * Math.max(1, Math.abs(was[i])));

export function fitEverything(viewer) {
  framing.fitting = true;
  let done = false;
  try {
    done = fitCamera(viewer);
  } finally {
    framing.fitting = false;
  }
  if (done) framing.fitted = framed(viewer);
  framing.set(true);
  return done;
}

function fitCamera(viewer) {
  const { position, pose, zoomFactor } = viewer.navigationState;
  const space = globalSpace(viewer);
  if (!space?.rank) return false;
  const render = pose.displayDimensionRenderInfo.value;
  const drawn = Array.from(render?.displayDimensionIndices ?? []).filter((axis) => axis >= 0);
  const { lowerBounds, upperBounds } = space.bounds;
  const extent = (axis) => {
    const low = lowerBounds[axis];
    const high = upperBounds[axis];
    return Number.isFinite(low) && Number.isFinite(high) ? high - low : null;
  };
  if (drawn.slice(0, 2).some((axis) => extent(axis) === null)) return false;
  const middle = Float32Array.from(position.value);
  for (const axis of drawn.slice(0, 2)) {
    middle[axis] = (lowerBounds[axis] + upperBounds[axis]) / 2;
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
    // Upright, the picture keeps clear of the controls drawn over it: the
    // buttons along the top and the sliders along the bottom.
    const pixels = slot === 0 ? flat?.logicalWidth : (flat?.logicalHeight ?? 0) - (KEEP_CLEAR.top + KEEP_CLEAR.bottom);
    if (across === null || !(pixels > 0)) return;
    fit = Math.max(fit, (across * render.canonicalVoxelFactors[slot]) / pixels);
  });
  if (fit > 0) {
    zoomFactor.value = fit * FIT_MARGIN;
    const upright = drawn[1];
    if (upright !== undefined && flat) {
      // Moved up by half the difference, so the picture sits in the clear part.
      const shifted = Float32Array.from(position.value);
      const pixelsToVoxels = zoomFactor.value / render.canonicalVoxelFactors[1];
      shifted[upright] += ((KEEP_CLEAR.bottom - KEEP_CLEAR.top) / 2) * pixelsToVoxels;
      position.value = shifted;
    }
  }
  let boxFit = 0;
  const smaller = Math.min(volume?.logicalWidth ?? 0, volume?.logicalHeight ?? 0);
  drawn.slice(0, 3).forEach((axis, slot) => {
    const across = extent(axis);
    if (across === null || !smaller) return;
    boxFit = Math.max(boxFit, (across * render.canonicalVoxelFactors[slot] * volume.logicalHeight) / smaller);
  });
  if (boxFit > 0) viewer.perspectiveNavigationState.zoomFactor.value = boxFit * VOLUME_MARGIN;
  // The volume turns about the point it is centred on: the middle of the stack.
  const depth = drawn[2];
  if (layoutOf(viewer) === "3d" && depth !== undefined && extent(depth) !== null) {
    moveQuietly(viewer, depth, (lowerBounds[depth] + upperBounds[depth]) / 2);
  }
  return fit > 0 || boxFit > 0;
}

/**
 * Go to a box given in micrometres -- `{ x: [low, high], y: [...], z: [...] }`,
 * a position of an acquisition or all of them -- and fit it in the view, as Fit
 * does for everything. The view is then the operator's: Fit is offered, and
 * tiles that land do not take it away again.
 */
export function frameBounds(viewer, um) {
  const { position, pose, zoomFactor } = viewer.navigationState;
  const space = globalSpace(viewer);
  const render = pose.displayDimensionRenderInfo.value;
  if (!space?.rank || !render || !um) return false;
  const toVoxels = (index, value) => (value * (space.units[index] === "m" ? 1e-6 : 1)) / space.scales[index];
  const drawn = Array.from(render.displayDimensionIndices).filter((axis) => axis >= 0).slice(0, 3);
  const spans = drawn.map((axis) => {
    const range = um[space.names[axis]];
    return Array.isArray(range) ? [toVoxels(axis, range[0]), toVoxels(axis, range[1])] : null;
  });
  if (spans.slice(0, 2).some((span) => span === null)) return false;
  const middle = Float32Array.from(position.value);
  const flatOnly = layoutOf(viewer) !== "3d";
  spans.forEach((span, slot) => {
    // In 2D the plane stays where it is: going to a tile is going across, not in depth.
    if (span && !(flatOnly && slot === 2)) middle[drawn[slot]] = (span[0] + span[1]) / 2;
  });
  let flat = null;
  let volume = null;
  for (const panel of viewer.display.panels) {
    if ("sliceView" in panel) flat = panel.renderViewport;
    else if ("sliceViews" in panel) volume = panel.renderViewport;
  }
  framing.fitting = true;
  following.moving = true;
  try {
    position.value = middle;
    let fit = 0;
    spans.slice(0, 2).forEach((span, slot) => {
      const pixels = slot === 0 ? flat?.logicalWidth : (flat?.logicalHeight ?? 0) - (KEEP_CLEAR.top + KEEP_CLEAR.bottom);
      if (span && pixels > 0) fit = Math.max(fit, (Math.abs(span[1] - span[0]) * render.canonicalVoxelFactors[slot]) / pixels);
    });
    if (fit > 0) zoomFactor.value = fit * FIT_MARGIN;
    const smaller = Math.min(volume?.logicalWidth ?? 0, volume?.logicalHeight ?? 0);
    let boxFit = 0;
    spans.forEach((span, slot) => {
      if (span && smaller) boxFit = Math.max(boxFit, (Math.abs(span[1] - span[0]) * render.canonicalVoxelFactors[slot] * volume.logicalHeight) / smaller);
    });
    if (boxFit > 0) viewer.perspectiveNavigationState.zoomFactor.value = boxFit * VOLUME_MARGIN;
    if (following.placed) following.placed = placedNow(viewer);
  } finally {
    framing.fitting = false;
    following.moving = false;
  }
  framing.fitted = null;
  framing.set(false);
  return true;
}

// -- how finely the volume is drawn -------------------------------------------------------

// The engine's perspective: a vertical field of view of 45 degrees.
const FOCAL = 1 / Math.tan(Math.PI / 8);
// The box keeps a little room around the farthest corner.
const BOX_MARGIN = 1.05;
// More steps than this would stall the picture on any card.
const MOST_STEPS = 16384;

/**
 * The volume view's box and the number of steps along each line of sight, for
 * one voxel of the copy drawn to cover about `pixelsPerVoxel` pixels of the
 * screen where the view turns.
 *
 * The engine draws from the copy whose voxels are about the size of one step,
 * and a step is the depth of its box divided by the steps. Its own box is fifty
 * times the zoom deep: for a light-sheet stack nearly all of it is empty space,
 * so it kept to its coarsest copy until the steps were so many the picture
 * stalled. Here the box just holds every corner of what is shown, wherever the
 * view turns, and the steps follow from the zoom and the size of the panel:
 * zooming in draws from finer copies, down to the finest, by itself.
 *
 * Returns `{ depth, samples }` (the box in the engine's units), or null while
 * there is nothing to draw or no volume view on screen.
 */
export function volumeDrawing(viewer, pixelsPerVoxel) {
  const space = globalSpace(viewer);
  const render = viewer.navigationState.pose.displayDimensionRenderInfo.value;
  if (!space?.rank || !render) return null;
  let volume = null;
  for (const panel of viewer.display.panels) if ("sliceViews" in panel) volume = panel.renderViewport;
  const height = volume?.logicalHeight ?? 0;
  if (!(height > 0)) return null;
  const drawn = Array.from(render.displayDimensionIndices).filter((axis) => axis >= 0).slice(0, 3);
  const { lowerBounds, upperBounds } = space.bounds;
  if (drawn.some((axis) => !Number.isFinite(lowerBounds[axis]) || !Number.isFinite(upperBounds[axis]))) return null;
  const at = viewer.navigationState.position.value;
  let farthest = 0;
  for (let corner = 0; corner < 1 << drawn.length; ++corner) {
    let squared = 0;
    drawn.forEach((axis, slot) => {
      const end = (corner >> slot) & 1 ? upperBounds[axis] : lowerBounds[axis];
      squared += ((end - at[axis]) * render.canonicalVoxelFactors[slot]) ** 2;
    });
    farthest = Math.max(farthest, Math.sqrt(squared));
  }
  const zoom = viewer.perspectiveNavigationState.zoomFactor.value; // the height of the view where it turns
  if (!(farthest > 0) || !(zoom > 0)) return null;
  const depth = 2 * farthest * BOX_MARGIN;
  // The engine's own sums (perspective_view/panel.js): a box of `depth` reaches this
  // far before and behind the point the view turns about, in units of the distance
  // to that point; nearer than a tenth of it is cut off.
  const reach = depth / zoom / FOCAL;
  const span = 1 + reach - Math.max(0.1, 1 - reach);
  // One pixel where the view turns is 2 / (FOCAL * height) of those units.
  const samples = (span * FOCAL * height) / (2 * pixelsPerVoxel);
  return { depth, samples: Math.min(MOST_STEPS, Math.max(1, Math.round(samples))) };
}

// -- following the newest plane --------------------------------------------------------

function placedNow(viewer) {
  const { position } = viewer.navigationState;
  return ["z", "t"].map((name) => {
    const at = axisIndex(viewer, name);
    return at === -1 ? null : position.value[at];
  });
}

/** Go to a point given by axis name: micrometres for x, y, z; the time point for t. */
export function moveTo(viewer, named) {
  const { position } = viewer.navigationState;
  const space = globalSpace(viewer);
  if (!space?.rank) return false;
  const target = Float32Array.from(position.value);
  let moved = false;
  space.names.forEach((name, index) => {
    const wanted = named[name];
    if (typeof wanted !== "number") return;
    // Python speaks micrometres and seconds; the engine counts voxels of a
    // space whose scales are in metres and seconds.
    const factor = space.units[index] === "m" ? 1e-6 : 1;
    target[index] = (wanted * factor) / space.scales[index];
    moved = true;
  });
  if (moved) position.value = target;
  return moved;
}

let newest = null; // where Python last said the newest data is
let awaited = null; // the plane the view is about to step to, once its chunk is loaded
let ticking = null;

/**
 * Python says where the newest plane is (or, with nothing in it, that none is coming).
 *
 * `where.await` names the chunk that holds that plane, as `{ store, chunk }`:
 * the view steps there only once the chunk is loaded, so the plane it leaves is
 * on screen until the next one can be drawn. Planes may arrive faster than
 * they load; the view then steps at the pace of the loading, always to the
 * newest plane announced by the time it is free.
 */
export function setNewest(viewer, where) {
  const named = {};
  for (const name of ["z", "t"]) if (typeof where?.[name] === "number") named[name] = where[name];
  newest = Object.keys(named).length ? { named, awaiting: where?.await ?? null } : null;
  acquiring.set(newest !== null);
  if (newest !== null && following.value) goToNewest(viewer);
}

function stepTo(viewer, target) {
  // The volume view shows every plane already: there only the time point is followed.
  const named = layoutOf(viewer) === "3d" ? { t: target.named.t } : target.named;
  following.moving = true;
  try {
    if (moveTo(viewer, named)) following.placed = placedNow(viewer);
  } finally {
    following.moving = false;
  }
}

let wantedOf = null; // the store a chunk is wanted of, for the step that is awaited

function tick(viewer) {
  ticking = null;
  if (awaited === null) return;
  const { target, since } = awaited;
  const { store, chunk } = target.awaiting;
  const ready = isLoaded(viewer, store, chunk);
  if (!ready && performance.now() - since < AWAIT_MS) {
    ticking = setTimeout(() => tick(viewer), 30);
    return;
  }
  awaited = null;
  if (following.value) stepTo(viewer, target);
  // Announced meanwhile: the newest plane is next.
  if (following.value && newest !== null && newest !== target) goToNewest(viewer);
  else {
    want(viewer, store, []);
    if (wantedOf === store) wantedOf = null;
  }
}

export function goToNewest(viewer) {
  if (newest === null) return;
  if (newest.awaiting?.store && Array.isArray(newest.awaiting.chunk)) {
    if (awaited !== null) return; // one step at a time: tick() takes the newest when it is free
    awaited = { target: newest, since: performance.now() };
    // The stack before this one is let go of: what was wanted of it stays
    // wanted in the worker until it is told otherwise.
    if (wantedOf !== null && wantedOf !== newest.awaiting.store) want(viewer, wantedOf, []);
    wantedOf = newest.awaiting.store;
    want(viewer, newest.awaiting.store, [newest.awaiting.chunk]);
    if (ticking === null) ticking = setTimeout(() => tick(viewer), 0);
    return;
  }
  stepTo(viewer, newest);
}

/** Follow again, as the Live button asks. */
export function followAgain(viewer) {
  following.set(true);
  goToNewest(viewer);
}

// -- hearing the operator ---------------------------------------------------------------

export function watchOperator(viewer) {
  const moved = () => {
    if (!framing.fitting && framing.busy === 0 && framing.fitted && differs(framed(viewer), framing.fitted)) {
      framing.set(false);
    }
    if (!following.moving && following.placed && acquiring.value) {
      const now = placedNow(viewer);
      const stepped = now.some((value, i) => {
        const was = following.placed[i];
        return value !== null && was !== null && Math.abs(value - was) > 1e-3;
      });
      if (stepped) following.set(false);
    }
  };
  viewer.navigationState.changed.add(moved);
  viewer.perspectiveNavigationState.changed.add(moved);
  // A new run is followed from its start, whatever was done during the last.
  acquiring.listeners.push((running) => {
    if (running) following.set(true);
    else following.placed = null;
    // The engine reads ahead of a view that moves through the planes. Ahead of
    // a view that follows a run there is nothing yet: every such request would
    // come back empty, and be asked again once the plane exists.
    const ahead = viewer.chunkQueueManager?.enablePrefetch;
    if (ahead) ahead.value = !running;
  });
}

// An acquisition opens on its first time point. Left to itself the engine
// starts in the middle of every axis it does not draw, which for a time-lapse
// is a time point in the middle of the run.
export function toFirstTimePoint(viewer) {
  const { position } = viewer.navigationState;
  const space = globalSpace(viewer);
  const axis = space?.names?.indexOf("t") ?? -1;
  if (axis === -1 || !Number.isFinite(space.bounds.lowerBounds[axis])) return;
  const start = Float32Array.from(position.value);
  // Time point i is drawn over i - 0.5 .. i + 0.5; the first starts at the lower bound.
  start[axis] = space.bounds.lowerBounds[axis] + 0.5;
  position.value = start;
}
