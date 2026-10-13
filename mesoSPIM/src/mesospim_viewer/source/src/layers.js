/**
 * Bringing the engine's layers into line with what Python asks for, in place.
 *
 * Python describes each channel of each acquisition as one neuroglancer image
 * layer (state.py). Stock practice would be to rebuild a layer whenever its
 * description changes, and that is what made a running acquisition unwatchable:
 * a rebuilt layer forgets every chunk it had drawn, so each tile that landed
 * blanked the picture and fetched all of it again, and the panel's controls
 * were torn down and put back.
 *
 * Here a layer is built once and then changed, never rebuilt:
 *
 * - a tile that lands is one source added to the layer;
 * - a tile whose shape changed (a time point appended) is that one source
 *   given its new address;
 * - a contrast window Python measured later is that control moved, unless the
 *   operator has moved it since: then theirs stays.
 *
 * What the operator adjusted on a layer is also kept when the layer is taken
 * off the view, and given back when it returns.
 */
import { makeLayer, deleteLayer } from "neuroglancer/unstable/layer/index.js";
import { layerDataSourceSpecificationFromJson } from "neuroglancer/unstable/layer/layer_data_source.js";

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Per layer name: what Python last asked for, the lasting names of the layer's
// sources in the engine's own order, and the control values Python last set.
const held = new Map();
// Per layer name: the operator's adjustments of a layer that was taken off.
const remembered = new Map();
// Heard after every scene Python sends: the automatic contrast.
const listeners = [];

export function onLayersChanged(listener) {
  listeners.push(listener);
}

/** What Python says about a layer beyond what the engine holds: `_auto`, `_acquisition`... */
export function about(name) {
  return held.get(name)?.spec ?? null;
}

function forEngine(spec) {
  const plain = {};
  for (const [key, value] of Object.entries(spec)) {
    if (!key.startsWith("_")) plain[key] = value;
  }
  return plain;
}

// -- one control of a layer's shader ---------------------------------------------

function controlState(layer, name) {
  return layer.shaderControlState?.state?.get(name);
}

/** The value of a control as JSON, read live: the engine's own JSON leaves defaults out. */
export function readControl(layer, name) {
  const state = controlState(layer, name);
  if (state === undefined) return layer.shaderControlState?.unparsedJson?.[name];
  const value = state.trackable.value;
  if (name === "color") return Array.from(value ?? []);
  if (value && typeof value === "object" && "range" in value) {
    return { range: Array.from(value.range ?? [], Number), window: Array.from(value.window ?? [], Number) };
  }
  return state.trackable.toJSON();
}

export function writeControl(layer, name, json) {
  const controls = layer.shaderControlState;
  if (!controls) return;
  const state = controlState(layer, name);
  if (state === undefined) {
    // The shader has not been read yet: kept until it has.
    controls.restoreState({ ...(controls.unparsedJson ?? {}), [name]: json });
    return;
  }
  try {
    state.trackable.restoreState(json);
  } catch {
    // A value the control does not take is left out.
  }
}

// -- the sources of one layer ------------------------------------------------------

function dropSource(layer, entry, id) {
  const at = entry.ids.indexOf(id);
  if (at === -1) return;
  const [source] = layer.dataSources.splice(at, 1);
  entry.ids.splice(at, 1);
  source?.dispose();
  layer.dataSourcesChanged.dispatch();
}

function reconcileSources(layer, entry, spec) {
  const wanted = spec._sources ?? [];
  const sources = spec.source ?? [];
  const before = entry.spec.source ?? [];
  const beforeIds = entry.spec._sources ?? [];
  // Gone: taken out of the engine's list.
  for (const id of [...entry.ids]) {
    if (!wanted.includes(id)) dropSource(layer, entry, id);
  }
  for (const id of entry.retired) {
    if (!wanted.includes(id)) entry.retired.delete(id);
  }
  for (const id of spec._retiring ?? []) {
    if (entry.ids.includes(id) && !entry.retiring.has(id)) entry.retiring.set(id, performance.now());
  }
  wanted.forEach((id, at) => {
    if (entry.retired.has(id)) return; // let go already, ahead of Python
    const here = entry.ids.indexOf(id);
    if (here === -1) {
      // New: one more source, and nothing else is touched.
      layer.addDataSource(layerDataSourceSpecificationFromJson(sources[at]));
      entry.ids.push(id);
      return;
    }
    const was = before[beforeIds.indexOf(id)];
    if (!same(was, sources[at])) {
      // Another address or another place: this source alone is read again.
      layer.dataSources[here].spec = layerDataSourceSpecificationFromJson(sources[at]);
    }
  });
}

// -- which channel of its stores a layer reads -----------------------------------------
//
// The engine keeps the channel axis as a dimension of the layer's own, and
// Python pins it ("localPosition"). The dimension exists only while a source
// of the layer has it: when the last one goes and another comes -- a stack's
// preview handed over, the next stack's preview arriving -- the engine makes
// it anew, in the middle of its range. So the pin is put back whenever the
// layer's own space changes.

function pinChannel(layer, name) {
  const wanted = held.get(name)?.spec?.localPosition;
  if (!Array.isArray(wanted) || !layer.localPosition) return;
  const space = layer.localCoordinateSpace?.value;
  if (!space || space.rank !== wanted.length) return;
  const now = Array.from(layer.localPosition.value ?? []);
  if (now.length === wanted.length && now.every((value, i) => Math.abs(value - wanted[i]) < 1e-6)) return;
  layer.localPosition.restoreState(wanted);
}

// -- the controls Python sets ---------------------------------------------------------

function reconcileControls(layer, entry, spec) {
  const asked = spec.shaderControls ?? {};
  for (const [name, value] of Object.entries(asked)) {
    if (same(entry.set[name], value)) continue;
    // Python's value has changed. It is taken unless the operator has moved the
    // control away from what Python set before.
    const untouched = entry.touched?.[name] !== true;
    if (untouched) {
      let next = value;
      if (name === "contrast") {
        // A window Python gives only in part keeps the other part.
        const now = readControl(layer, name) ?? {};
        next = { ...now, ...value };
      }
      writeControl(layer, name, next);
    }
    entry.set[name] = value;
  }
}

/** The operator moved a control themselves: Python's later values no longer replace it. */
export function markTouched(name, control) {
  const entry = held.get(name);
  if (entry) entry.touched = { ...(entry.touched ?? {}), [control]: true };
}

export function isTouched(name, control) {
  return held.get(name)?.touched?.[control] === true;
}

export function clearTouched(name, control) {
  const entry = held.get(name);
  if (entry?.touched) delete entry.touched[control];
}

// -- keeping what the operator adjusted across a layer's absence -------------------------

function remember(managed) {
  const layer = managed.layer;
  const entry = held.get(managed.name);
  if (!layer || !entry) return;
  const kept = { visible: managed.visible, touched: { ...(entry.touched ?? {}) }, controls: {} };
  for (const name of Object.keys(entry.touched ?? {})) kept.controls[name] = readControl(layer, name);
  if (layer.opacity) kept.opacity = layer.opacity.value;
  remembered.set(managed.name, kept);
}

// -- all the layers ------------------------------------------------------------------------

/**
 * `between(left)` is called after the layers that are no longer wanted have
 * gone and before any new one is made, with the number of layers left: the
 * moment to prepare the engine's space for what is coming.
 */
export function applyLayers(viewer, specs, between) {
  const manager = viewer.layerManager;
  const wanted = new Set(specs.map((spec) => spec.name));
  let changed = false;
  for (const managed of [...manager.managedLayers]) {
    if (wanted.has(managed.name)) continue;
    remember(managed);
    deleteLayer(managed);
    held.delete(managed.name);
    changed = true;
  }
  between?.(manager.managedLayers.length);
  specs.forEach((spec, index) => {
    let managed = manager.getLayerByName(spec.name);
    const entry = held.get(spec.name);
    if (managed && entry) {
      if (same(entry.spec, spec)) return;
      const layer = managed.layer;
      reconcileSources(layer, entry, spec);
      reconcileControls(layer, entry, spec);
      // Shown or hidden by Python (the acquisition ticked on or off) only when
      // Python's own word changes; the eye in the panel is the operator's.
      if (entry.spec.visible !== spec.visible) managed.setVisible(spec.visible !== false);
      entry.spec = spec;
      pinChannel(layer, spec.name);
      return;
    }
    if (managed) deleteLayer(managed); // not one of ours: made anew
    const description = forEngine(spec);
    const kept = remembered.get(spec.name);
    remembered.delete(spec.name);
    if (kept) {
      description.shaderControls = { ...(description.shaderControls ?? {}), ...kept.controls };
      if (kept.opacity !== undefined) description.opacity = kept.opacity;
      if (spec.visible !== false) description.visible = kept.visible;
    }
    managed = makeLayer(viewer.layerSpecification, spec.name, description);
    viewer.layerSpecification.add(managed, index);
    held.set(spec.name, {
      spec,
      ids: [...(spec._sources ?? [])],
      set: { ...(spec.shaderControls ?? {}) },
      touched: kept ? { ...kept.touched } : {},
      retiring: new Map(), // previews the tile on disk is taking over from, and since when
      retired: new Set(), // ...and those already let go
    });
    const made = managed.layer;
    made?.localCoordinateSpace?.changed.add(() => pinChannel(made, spec.name));
    changed = true;
  });
  specs.forEach((spec, at) => {
    const here = manager.managedLayers.findIndex((managed) => managed.name === spec.name);
    if (here !== -1 && here !== at) manager.reorderManagedLayer(here, at);
  });
  // Heard after every scene, not only when a layer came or went: what Python
  // says about a layer (whether its contrast sets itself, say) may have changed.
  for (const listener of listeners) listener(changed);
}

// -- handing a finished stack over from its preview to the tile on disk ------------------
//
// Python says when a stack is whole on disk and the page may read it (the
// tile's chunks are named as landed in the same breath). The preview stays
// until the tile's own picture is up -- every chunk the view needs of that
// layer loaded -- so the stack never drops out of the picture in between.

const RETIRE_AFTER_MS = 1200; // at the earliest: the engine's counts lag a little
const RETIRE_BY_MS = 12000; // at the latest, whatever the counts say

function pictureIsUp(managed) {
  let needed = 0;
  let available = 0;
  for (const renderLayer of managed.layer?.renderLayers ?? []) {
    const progress = renderLayer.layerChunkProgressInfo;
    if (!progress) continue;
    needed += progress.numVisibleChunksNeeded;
    available += progress.numVisibleChunksAvailable;
  }
  return needed > 0 && available >= needed;
}

export function watchRetiring(viewer) {
  setInterval(() => {
    const now = performance.now();
    for (const [name, entry] of held) {
      if (entry.retiring.size === 0) continue;
      const managed = viewer.layerManager.getLayerByName(name);
      if (!managed?.layer) continue;
      for (const [id, since] of entry.retiring) {
        const waited = now - since;
        if (waited < RETIRE_AFTER_MS) continue;
        if (!(pictureIsUp(managed) || !managed.visible || waited > RETIRE_BY_MS)) continue;
        entry.retiring.delete(id);
        entry.retired.add(id);
        dropSource(managed.layer, entry, id);
      }
    }
  }, 200);
}
