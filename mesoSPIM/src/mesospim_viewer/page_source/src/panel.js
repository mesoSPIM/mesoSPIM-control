/**
 * The simple interface: our own control panel over a bare engine.
 *
 * Nothing here holds state of its own. Every control reads and writes the
 * engine's layer state -- visibility, the window and colour controls of the
 * layer's shader, the layout, the position -- which is exactly what the
 * engine's native panel edits, so an operator's adjustments survive Python's
 * updates by the same rule as in the full interface (see carryAdjustments in
 * main.js). The window-with-histogram and colour controls ARE the engine's
 * own widgets, mounted inside our rows; only their dress is ours.
 *
 * The panel is registered as one of the engine's side panels rather than laid
 * beside it: the engine draws a histogram only for a panel that lies within
 * its own canvas, which is how its native side panels are arranged too.
 */
import { ShaderControls } from "neuroglancer/unstable/widget/shader_controls.js";
import { WatchableVisibilityPriority } from "neuroglancer/unstable/visibility_priority/frontend.js";
import { SidePanel } from "neuroglancer/unstable/ui/side_panel.js";
import { TrackableSidePanelLocation } from "neuroglancer/unstable/ui/side_panel_location.js";
import "./panel.css";

const SEPARATOR = " · "; // between acquisition and channel in a layer's name (state.py)

const ICONS = {
  eye: '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeOff: '<svg viewBox="0 0 24 24"><path d="M3 3l18 18"/><path d="M10.6 5.3A11 11 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.2 3.7"/><path d="M6.6 6.6A16 16 0 0 0 2 12s3.5 6 10 6a10 10 0 0 0 4.2-.9"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>',
  fold: '<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/></svg>',
};

function iconButton(icon, title) {
  const button = element("button", "icon");
  button.type = "button";
  button.title = title;
  button.innerHTML = ICONS[icon];
  return button;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function splitName(name) {
  const at = name.indexOf(SEPARATOR);
  return at === -1 ? [name, name] : [name.slice(0, at), name.slice(at + SEPARATOR.length)];
}

// -- the acquisition: the session's runs, newest first --------------------------

function acquisitionCard() {
  const card = element("section", "card acquisition");
  card.hidden = true;
  card.appendChild(element("h2", null, "Acquisition"));
  const select = document.createElement("select");
  select.className = "chooser";
  select.title = "The acquisition shown: the current one, or an earlier one of this session";
  select.addEventListener("change", () => {
    fetch("/api/choose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: Number(select.value) }),
    }).catch(() => undefined);
  });
  card.appendChild(select);
  let offered = "";
  card.setChoices = (choices) => {
    const names = choices?.names ?? [];
    const key = JSON.stringify(choices);
    card.hidden = names.length === 0;
    if (key === offered) return;
    offered = key;
    select.replaceChildren();
    names.forEach((name, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = index === 0 ? `${name}  (current)` : name;
      select.appendChild(option);
    });
    select.value = String(choices.current ?? 0);
  };
  return card;
}

// -- the view: 2D or 3D ---------------------------------------------------------

function viewSwitch(viewer, fit) {
  const row = element("div", "segmented view");
  const buttons = new Map();
  for (const [layout, label] of [["xy", "2D"], ["3d", "3D"]]) {
    const button = element("button", null, label);
    button.type = "button";
    button.dataset.layout = layout;
    button.addEventListener("click", () => {
      viewer.layout.restoreState(layout);
      // The volume view draws a maximum projection of every channel; the flat
      // view leaves volume rendering off, as the engine does by default.
      for (const managed of viewer.layerManager.managedLayers) {
        managed.layer?.volumeRenderingMode?.restoreState(layout === "3d" ? "max" : "off");
      }
      // The new panel exists a moment later; frame the picture in it then.
      setTimeout(() => fit?.(), 50);
    });
    buttons.set(layout, button);
    row.appendChild(button);
  }
  const reflect = () => {
    const current = viewer.layout.toJSON();
    for (const [layout, button] of buttons) button.classList.toggle("on", current === layout);
  };
  viewer.layout.changed.add(reflect);
  reflect();
  return row;
}

// -- the volume view: how the specimen is projected, how finely, from where ------

const LOOK_FROM = [
  ["Top", [0, 0, 0, 1]],
  ["Front", [-Math.SQRT1_2, 0, 0, Math.SQRT1_2]],
  ["Side", [0, Math.SQRT1_2, 0, Math.SQRT1_2]],
];
const DETAIL_STEPS = [32, 64, 128, 256, 512, 1024];

function imageLayers(viewer) {
  return viewer.layerManager.managedLayers
    .map((managed) => managed.layer)
    .filter((layer) => layer && layer.type === "image");
}

function volumeCard(viewer, fit) {
  const card = element("section", "card volume");
  card.appendChild(element("h2", null, "3D"));

  // Projection: the brightest voxel along each ray (a microscopist's projection),
  // every voxel accumulated with a gain, or the darkest voxel.
  const projection = element("div", "segmented");
  const projections = new Map();
  for (const [mode, label] of [["max", "Max"], ["on", "Accumulate"], ["min", "Min"]]) {
    const button = element("button", null, label);
    button.type = "button";
    button.dataset.mode = mode;
    button.addEventListener("click", () => {
      for (const layer of imageLayers(viewer)) layer.volumeRenderingMode.restoreState(mode);
    });
    projections.set(mode, button);
    projection.appendChild(button);
  }
  card.appendChild(labelled("Projection", projection));

  // Detail: how many steps a ray takes, which is what decides how fine a copy of
  // the image the engine may draw from. More is sharper and slower.
  const detail = document.createElement("input");
  detail.type = "range";
  detail.min = "0";
  detail.max = String(DETAIL_STEPS.length - 1);
  detail.step = "1";
  detail.className = "detail";
  const detailReading = element("span", "reading", "");
  detail.addEventListener("input", () => {
    const samples = DETAIL_STEPS[Number(detail.value)];
    for (const layer of imageLayers(viewer)) layer.volumeRenderingDepthSamplesTarget.value = samples;
  });
  card.appendChild(labelled("Detail", detail, detailReading));

  // Gain, for the accumulated projection only: how strongly each voxel adds up.
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
    const button = element("button", null, label);
    button.type = "button";
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
  card.appendChild(labelled("Slice planes", slices));

  const reflect = () => {
    const layers = imageLayers(viewer);
    const mode = layers[0]?.volumeRenderingMode.toJSON() ?? "off";
    for (const [name, button] of projections) button.classList.toggle("on", mode === name);
    const samples = layers[0]?.volumeRenderingDepthSamplesTarget.value ?? 64;
    let nearest = 0;
    DETAIL_STEPS.forEach((step, i) => {
      if (Math.abs(step - samples) < Math.abs(DETAIL_STEPS[nearest] - samples)) nearest = i;
    });
    if (document.activeElement !== detail) detail.value = String(nearest);
    detailReading.textContent = `${Math.round(samples)} steps`;
    const g = layers[0]?.volumeRenderingGain.value ?? 0;
    if (document.activeElement !== gain) gain.value = String(g);
    gainReading.textContent = g.toFixed(1);
    gainRow.classList.toggle("disabled", mode !== "on");
    slices.checked = viewer.showPerspectiveSliceViews.value;
  };
  const watched = new WeakSet();
  const watch = () => {
    for (const layer of imageLayers(viewer)) {
      if (watched.has(layer)) continue;
      watched.add(layer);
      layer.volumeRenderingMode.changed.add(reflect);
      layer.volumeRenderingDepthSamplesTarget.changed.add(reflect);
      layer.volumeRenderingGain.changed.add(reflect);
    }
    reflect();
  };
  viewer.layerManager.layersChanged.add(watch);
  viewer.showPerspectiveSliceViews.changed.add(reflect);
  watch();
  const show = () => {
    card.hidden = viewer.layout.toJSON() !== "3d";
  };
  viewer.layout.changed.add(show);
  show();
  return card;
}

function labelled(text, control, reading) {
  const row = element("div", "row labelled");
  row.appendChild(element("span", "label", text));
  row.appendChild(control);
  if (reading) row.appendChild(reading);
  return row;
}

// -- the channels: one row per engine layer, gathered by acquisition ------------

function channelRow(viewer, managed) {
  const [, channel] = splitName(managed.name);
  const row = element("div", "channel");
  row.dataset.layer = managed.name;
  const head = element("div", "row");
  const eye = iconButton("eye", "Show or hide this channel");
  eye.classList.add("eye");
  eye.addEventListener("click", () => managed.setVisible(!managed.visible));
  const swatch = element("span", "swatch");
  swatch.title = "Change the colour";
  const label = element("span", "label", channel);
  head.append(eye, swatch, label);
  row.appendChild(head);

  const layer = managed.layer;
  const controls = element("div", "controls");
  row.appendChild(controls);
  let mounted = null;
  const reflect = () => {
    row.classList.toggle("hidden", !managed.visible);
    eye.classList.toggle("off", !managed.visible);
    eye.innerHTML = managed.visible ? ICONS.eye : ICONS.eyeOff;
    // The live value, not its JSON: the JSON is empty while the colour equals
    // the shader's default, which is exactly the colour the store declared.
    const colour = layer?.shaderControlState?.state?.get("color")?.trackable?.value;
    swatch.style.background = colour?.length === 3
      ? `rgb(${Array.from(colour, (v) => Math.round(v * 255)).join(", ")})`
      : "#ffffff";
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
    // The colour control's own input is hidden; the swatch opens it.
    swatch.addEventListener("click", () => controls.querySelector('input[type="color"]')?.click());
  }
  managed.layerChanged.add(reflect);
  reflect();
  return { row, dispose: () => mounted?.dispose() };
}

function channelsCard(viewer) {
  const card = element("section", "card channels");
  card.appendChild(element("h2", null, "Channels"));
  const body = element("div", "groups");
  card.appendChild(body);
  let rows = [];
  const rebuild = () => {
    for (const { dispose } of rows) dispose();
    rows = [];
    body.replaceChildren();
    const groups = new Map();
    for (const managed of viewer.layerManager.managedLayers) {
      if (!managed.layer || managed.layer.type !== "image") continue;
      const [group] = splitName(managed.name);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(managed);
    }
    for (const [group, layers] of groups) {
      const section = element("div", "group");
      section.dataset.group = group;
      const head = element("div", "row head");
      const eye = iconButton("eye", "Show or hide every channel of this acquisition");
      eye.classList.add("eye");
      eye.addEventListener("click", () => {
        const anyShown = layers.some((m) => m.visible);
        for (const managed of layers) managed.setVisible(!anyShown);
      });
      const tiles = layers[0]?.layer?.dataSources?.length ?? 0;
      head.append(eye, element("span", "name", group), element("span", "count", tiles === 1 ? "1 tile" : `${tiles} tiles`));
      const reflectGroup = () => {
        const anyShown = layers.some((m) => m.visible);
        eye.classList.toggle("off", !anyShown);
        eye.innerHTML = anyShown ? ICONS.eye : ICONS.eyeOff;
      };
      for (const managed of layers) managed.layerChanged.add(reflectGroup);
      reflectGroup();
      section.appendChild(head);
      for (const managed of layers) {
        const made = channelRow(viewer, managed);
        rows.push(made);
        section.appendChild(made.row);
      }
      body.appendChild(section);
    }
  };
  let pending = null;
  const later = () => {
    clearTimeout(pending);
    pending = setTimeout(rebuild, 0);
  };
  viewer.layerManager.layersChanged.add(later);
  // A layer's sources arrive after the layer: the tile count follows them.
  const followed = new WeakSet();
  viewer.layerManager.layersChanged.add(() => {
    for (const managed of viewer.layerManager.managedLayers) {
      const layer = managed.layer;
      if (!layer?.dataSourcesChanged || followed.has(layer)) continue;
      followed.add(layer);
      layer.dataSourcesChanged.add(later);
    }
  });
  rebuild();
  return card;
}

// -- the sliders: depth and time, on the picture ---------------------------------

function axisSlider(viewer, stage, axis, id) {
  const box = element("div", "axis-slider");
  box.id = id;
  box.hidden = true;
  const name = element("span", "name", axis.toUpperCase());
  const input = document.createElement("input");
  input.type = "range";
  input.step = "1";
  const reading = element("span", "reading", "");
  box.append(name, input, reading);
  stage.appendChild(box);

  const { position } = viewer.navigationState;
  const where = () => {
    const space = position.coordinateSpace.value;
    const index = space?.names?.indexOf(axis) ?? -1;
    if (index === -1 || !space.bounds) return null;
    const low = space.bounds.lowerBounds[index];
    const high = space.bounds.upperBounds[index];
    if (!Number.isFinite(low) || !Number.isFinite(high) || high - low <= 1) return null;
    // Bounds run from the first voxel's near edge to the last one's far edge
    // (-0.5 .. n - 0.5); the slider steps through the voxel indices 0 .. n - 1.
    return { index, low: Math.round(low + 0.5), high: Math.round(high - 0.5) };
  };
  const reflect = () => {
    const found = where();
    box.hidden = found === null;
    if (found === null) return;
    input.min = String(found.low);
    input.max = String(found.high);
    const value = Math.round(position.value[found.index] - 0.5);
    if (document.activeElement !== input) input.value = String(value);
    reading.textContent = `${value + 1} / ${found.high - found.low + 1}`;
  };
  input.addEventListener("input", () => {
    const found = where();
    if (found === null) return;
    const next = Float32Array.from(position.value);
    next[found.index] = Number(input.value) + 0.5;
    position.value = next;
  });
  position.changed.add(reflect);
  position.coordinateSpace.changed.add(reflect);
  reflect();
  return box;
}

// -- the panel, as one of the engine's own side panels ---------------------------

class ControlPanel extends SidePanel {
  constructor(manager, location, viewer, fit) {
    super(manager, location);
    this.element.classList.add("mesospim-panel");
    this.element.draggable = false;
    const body = element("div", "panel-body");
    const head = element("div", "panel-head");
    const title = element("span", "title", "mesoSPIM");
    const fold = iconButton("fold", "Hide the controls");
    fold.classList.add("fold");
    fold.addEventListener("click", () => this.close());
    head.append(title, fold);
    this.acquisitions = acquisitionCard();
    body.append(head, this.acquisitions, volumeCard(viewer, fit), channelsCard(viewer));
    this.addBody(body);
  }
}

export function mountPanel(viewer, { fit }) {
  const manager = viewer.sidePanelManager;
  const location = new TrackableSidePanelLocation(
    { side: "right", col: 0, row: 0, flex: 1, size: 330, minSize: 260, visible: true },
  );
  let panel = null;
  let choices = null;
  manager.registerPanel({
    location,
    makePanel: () => {
      panel = new ControlPanel(manager, location, viewer, fit);
      panel.acquisitions.setChoices(choices);
      return panel;
    },
  });
  // A pure volume: no cross-section planes drawn inside it unless asked for.
  viewer.showPerspectiveSliceViews.value = false;

  // The picture's column carries the sliders and, while the panel is folded
  // away, the button that brings it back. The manager rewrites that column's
  // children whenever it lays the panels out, so ours are put back after
  // every frame that dropped them.
  const stage = manager.centerColumn;
  stage.style.position = "relative";
  // The volume view would grow the panel row past the window and clip its
  // bottom strip, sliders and scale bar included: the row is a flex child
  // that will not shrink below its content unless told, so it is told.
  manager.element.style.minHeight = "0";
  stage.style.minHeight = "0";
  stage.style.overflow = "hidden";
  const overlay = element("div", "stage-overlay");
  const unfold = iconButton("fold", "Show the controls");
  unfold.id = "fold";
  unfold.addEventListener("click", () => {
    location.visible = true;
  });
  overlay.appendChild(unfold);
  // The 2D/3D switch sits on the picture, top left, where the eye goes first.
  overlay.appendChild(viewSwitch(viewer, fit));
  const reflect = () => {
    unfold.style.display = location.visible ? "none" : "flex";
  };
  location.locationChanged.add(reflect);
  reflect();
  axisSlider(viewer, overlay, "z", "slider-z");
  axisSlider(viewer, overlay, "t", "slider-t");
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
    setChoices(offered) {
      choices = offered;
      panel?.acquisitions.setChoices(offered);
    },
  };
}
