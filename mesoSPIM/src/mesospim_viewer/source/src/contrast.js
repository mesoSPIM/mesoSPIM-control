/**
 * Contrast that sets itself from what is on screen.
 *
 * A camera's few thousand counts on the engine's default range of 0..65535
 * are a black picture, and nobody knows the brightness of an acquisition that
 * is still being written. So a channel whose contrast nobody has set -- not
 * the store, not Python, not the operator -- is on *Auto*: its window follows
 * the histogram of the planes being drawn, from the background to just under
 * the brightest structure, a few times a second and without a flicker.
 *
 * The histogram is the engine's own, the one drawn in the panel: 254 bins
 * across the span the panel shows ("window"), with everything below and above
 * in a bin at either end. Only the black and white points ("range") change the
 * picture, so the span can be moved around the data to measure it finely
 * without the operator seeing anything but the result.
 *
 * Voxels at zero are not data. The engine counts every chunk that is not on
 * disk yet as zeros, and a tile being written is mostly that; a camera never
 * reads zero. So the span starts at one, and what lies below it is left out.
 *
 * Auto ends for a channel the moment the operator moves its contrast (the
 * panel says when: operatorMoved), and comes back with the Auto button in
 * its row.
 */
import { WatchableVisibilityPriority } from "neuroglancer/unstable/visibility_priority/frontend.js";
import { copyHistogramToCPU } from "neuroglancer/unstable/webgl/empirical_cdf.js";
import { defaultDataTypeRange } from "neuroglancer/unstable/util/lerp.js";
import { layoutOf } from "./camera.js";
import { about, clearTouched, isTouched, markTouched, onLayersChanged, readControl, writeControl } from "./layers.js";

const EVERY_MS = 300;
const LOW = 0.01; // the black point: the camera's background
const HIGH = 0.998; // the white point: just under the brightest structure
const HEADROOM = 0.1; // ...opened up by this much, so that structure is not clipped
const MIN_SAMPLES = 256;
const FLOOR = 1; // the lowest value that counts as data

// Per layer: whether Auto is on, and the listeners that hear it change.
const autos = new Map();
const listeners = [];

export function onAutoChanged(listener) {
  listeners.push(listener);
}

export function isAuto(name) {
  return autos.get(name)?.on === true;
}

export function setAuto(viewer, name, on) {
  const state = autos.get(name);
  if (!state || state.on === on) return;
  state.on = on;
  if (on) {
    clearTouched(name, "contrast");
    viewer.display.scheduleRedraw();
  }
  for (const listener of listeners) listener(name, on);
}

function percentile(histogram, total, fraction) {
  // Bin 0 holds what lies below the span (left out), bin 255 what lies above it.
  let seen = 0;
  for (let bin = 1; bin < histogram.length; ++bin) {
    const count = histogram[bin];
    if (seen + count >= fraction * total && count > 0) {
      const within = (fraction * total - seen) / count;
      return { bin, within };
    }
    seen += count;
  }
  return { bin: histogram.length - 1, within: 1 };
}

/** One step: from the histogram over `window`, where the range should be and what span to measure next. */
export function autoStep(histogram, window, limits) {
  const [w0, w1] = window;
  const span = w1 - w0;
  if (!(span > 0)) return null;
  // A span that starts at zero would count the chunks that are not there yet.
  if (w0 < FLOOR) return { range: null, window: [FLOOR, Math.max(w1, FLOOR + 1)] };
  let total = 0;
  for (let bin = 1; bin < histogram.length; ++bin) total += histogram[bin];
  if (total < MIN_SAMPLES) return null;
  const bins = histogram.length - 2;
  const size = span / bins;
  const valueAt = ({ bin, within }) => w0 + (bin - 1 + within) * size;
  const low = percentile(histogram, total, LOW);
  const high = percentile(histogram, total, HIGH);
  // Data in the very first bin of the span may reach below it.
  const clippedLow = low.bin === 1 && w0 > FLOOR;
  const clippedHigh = high.bin === histogram.length - 1 && w1 < limits[1];
  const clamp = (value) => Math.min(limits[1], Math.max(FLOOR, value));
  if (clippedLow || clippedHigh) {
    // The data runs out of the span: widen it on that side and measure again.
    return {
      range: null,
      window: [clippedLow ? clamp(w0 - span) : w0, clippedHigh ? clamp(w1 + 2 * span) : w1],
    };
  }
  const black = clamp(Math.max(w0, valueAt(low)));
  const bright = clamp(Math.min(w1, valueAt(high)));
  const across = Math.max(bright - black, 1);
  const white = clamp(bright + across * HEADROOM);
  // The span the panel shows: the range with room on both sides, so the next
  // measurement has bins a hundredth of the range wide.
  const next = [clamp(Math.floor(black - across * 0.5)), clamp(Math.ceil(white + across))];
  return { range: [Math.round(black), Math.max(Math.round(white), Math.round(black) + 1)], window: next };
}

const moved = (a, b, tolerance) => Math.abs(a[0] - b[0]) > tolerance || Math.abs(a[1] - b[1]) > tolerance;

function step(viewer, managed, state) {
  const layer = managed.layer;
  const controls = layer?.shaderControlState;
  const specifications = controls?.histogramSpecifications;
  const now = readControl(layer, "contrast");
  if (!specifications || !now?.range?.length || !now?.window?.length) return;
  if (specifications.bounds.value.length === 0) return;
  const limits = (defaultDataTypeRange[layer.dataType?.value] ?? [0, 65535]).map(Number);
  if (!limits.every(Number.isFinite)) return;
  // Only a histogram drawn over the span the control holds now is measured:
  // one from before the span last moved would be read against the wrong
  // numbers. Two frames after a change the engine has drawn it afresh.
  if (state.frames < 2) return;
  const gl = viewer.display.gl;
  let histogram;
  try {
    specifications.getFramebuffers(gl)[0].bind(256, 1);
    histogram = copyHistogramToCPU(gl);
  } finally {
    gl.bindFramebuffer(WebGL2RenderingContext.FRAMEBUFFER, null);
  }
  const result = autoStep(Array.from(histogram), now.window, limits);
  if (result === null) return;
  const range = result.range ?? now.range;
  const across = Math.abs(now.range[1] - now.range[0]);
  // Small differences are left alone, so the picture does not shimmer.
  const rangeMoved = moved(range, now.range, Math.max(2, across * 0.04));
  // A span that must move before anything can be measured moves by however
  // little; one that only follows the range is left alone for small steps.
  const tolerance = result.range === null ? 0 : Math.max(2, Math.abs(now.window[1] - now.window[0]) * 0.1);
  const windowMoved = moved(result.window, now.window, tolerance);
  if (!rangeMoved && !windowMoved) return;
  writeControl(layer, "contrast", { ...now, range: rangeMoved ? range : now.range, window: result.window });
  state.frames = 0;
}

function hook(viewer, managed) {
  const layer = managed.layer;
  const controls = layer?.shaderControlState;
  if (!controls || autos.has(managed.name)) return;
  const state = { on: about(managed.name)?._auto === true && !isTouched(managed.name, "contrast"), frames: 0 };
  // Frames drawn since the contrast last changed, whoever changed it.
  controls.changed.add(() => {
    state.frames = 0;
  });
  autos.set(managed.name, state);
  // The histogram is computed only for a layer somebody watches: Auto does,
  // whether or not the panel is open.
  const watching = new WatchableVisibilityPriority(WatchableVisibilityPriority.VISIBLE);
  const unwatch = controls.histogramSpecifications.visibility.add(watching);
  layer.registerDisposer(() => {
    unwatch?.();
    autos.delete(managed.name);
  });
}

/** The operator moved a channel's contrast themselves (the panel says so): Auto steps back. */
export function operatorMoved(viewer, name) {
  markTouched(name, "contrast");
  setAuto(viewer, name, false);
}

export function watchContrast(viewer) {
  const hookAll = () => {
    for (const managed of viewer.layerManager.managedLayers) {
      if (managed.layer?.type === "image") hook(viewer, managed);
      // Python may turn Auto on or off for a layer that is shown (a run ending).
      const state = autos.get(managed.name);
      const wanted = about(managed.name)?._auto === true;
      if (state && state.asked !== wanted) {
        state.asked = wanted;
        if (!isTouched(managed.name, "contrast")) setAuto(viewer, managed.name, wanted);
      }
    }
  };
  onLayersChanged(hookAll);
  viewer.layerManager.layersChanged.add(hookAll);
  let last = 0;
  let again = null;
  const drawAgain = (after) => {
    if (again !== null) return;
    again = setTimeout(() => {
      again = null;
      viewer.display.scheduleRedraw();
    }, after);
  };
  viewer.display.updateFinished.add(() => {
    let unsettled = false;
    for (const state of autos.values()) {
      state.frames += 1;
      if (state.on && state.frames < 3) unsettled = true;
    }
    // A picture that stands still is not drawn again on its own, but a contrast
    // that has just moved has to be measured once more, on a fresh histogram:
    // so the picture is drawn again until every channel on Auto has settled.
    if (unsettled) drawAgain(EVERY_MS / 2);
    const time = performance.now();
    if (time - last < EVERY_MS) {
      drawAgain(EVERY_MS - (time - last) + 10);
      return;
    }
    // Measured on the flat view: in the volume view the histogram is of rays.
    if (layoutOf(viewer) === "3d") return;
    last = time;
    for (const managed of viewer.layerManager.managedLayers) {
      const state = autos.get(managed.name);
      if (state?.on && managed.visible) step(viewer, managed, state);
    }
  });
  return { refresh: hookAll };
}
