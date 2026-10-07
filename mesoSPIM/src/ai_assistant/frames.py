"""The frames the assistant has seen, and what code reads from them.

The frame history keeps a small copy of every frame a look, a snap or live delivered, numbered,
with its time, source, position, settings and an optional label, and with code's measures:
brightness, saturation, focus, where the signal sits and how far that is from the centre, in
pixels and micrometres, and the stage move that would centre it. The scale comes from the
pixel size and the coordinate system ("nominal") until `calibrate` has measured it for the zoom
("calibrated"). Drift between two frames is measured by phase correlation of their copies. The
map is one readout line derived from the history; it has no store of its own.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import json
import re
import threading
import time
from pathlib import Path

import numpy as np

from . import config

AXES = ("x", "y", "z", "f")


def hms(seconds):
    return time.strftime("%H:%M:%S", time.localtime(seconds))


def field_um(readout):
    """The field of view (width, height) in um: the sensor's pixels times their size."""
    camera = (readout or {}).get("camera") or {}
    pixels, size = camera.get("pixels") or (None, None), camera.get("pixel_size_um")
    if not size or not pixels[0]:
        return None
    return float(pixels[0]) * float(size), float(pixels[1]) * float(size)


def nominal_scale(readout, axes):
    """How a stage move shows in the image, as the fraction of the field the sample moves right
    and up per um on x and y: from the field of view and the coordinate system."""
    field = field_um(readout)
    if field is None:
        return None
    right = 1.0 if axes.get("x", "right") == "right" else -1.0
    up = 1.0 if axes.get("y", "up") == "up" else -1.0
    return [[right / field[0], 0.0], [0.0, up / field[1]]]


def centre_move(offset, scale):
    """The x and y move (um) that would bring a signal `offset` (fraction of the field right of
    and above the centre) to the centre, under `scale` (see nominal_scale)."""
    matrix = np.array(scale, dtype=float).T          # columns: the image shift per um of x and of y
    try:
        move = np.linalg.solve(matrix, -np.array(offset, dtype=float))
    except np.linalg.LinAlgError:
        return None
    return {"x": round(float(move[0]), 1), "y": round(float(move[1]), 1)}


def shift(before, after):
    """How far the content moved from `before` to `after`, in pixels (right, down), by phase
    correlation; with the peak's share of the correlation, a confidence from 0 to 1."""
    a = np.asarray(before, dtype=float)
    b = np.asarray(after, dtype=float)
    if a.shape != b.shape:
        return None
    a, b = a - a.mean(), b - b.mean()
    cross = np.fft.fft2(b) * np.conj(np.fft.fft2(a))
    correlation = np.fft.ifft2(cross / (np.abs(cross) + 1e-9)).real
    row, col = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    peak = float(correlation[row, col])

    def centred(index, size):
        return index - size if index > size // 2 else index

    def refine(values, index):                        # a parabola through the peak and its neighbours
        left, mid, right = values[index - 1], values[index], values[(index + 1) % len(values)]
        bend = left - 2 * mid + right
        return 0.0 if bend == 0 else 0.5 * (left - right) / bend

    down = centred(row, a.shape[0]) + refine(correlation[:, col], row)
    across = centred(col, a.shape[1]) + refine(correlation[row, :], col)
    return {"right": round(float(across), 2), "down": round(float(down), 2), "confidence": round(peak, 3)}


class Calibration:
    """The measured scale per zoom (see nominal_scale), kept in a JSON file beside the
    microscope's configuration, so it survives the session."""

    def __init__(self, path=None):
        self.path = Path(path) if path else config.CALIBRATION_FILE
        self._lock = threading.Lock()

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def scale(self, zoom):
        entry = self.load().get(str(zoom))
        return entry["scale"] if entry else None

    def store(self, zoom, scale, when, step_um):
        with self._lock:
            data = self.load()
            data[str(zoom)] = {"scale": scale, "measured": when, "step_um": step_um}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")


class FrameHistory:
    """The frames of the session, newest last, capped at FRAME_HISTORY_BYTES of copies; numbers
    keep counting when the oldest go. Thread-safe: a look runs on its own thread."""

    def __init__(self, clock=time.time, calibration=None, max_bytes=None):
        self.clock = clock
        self.calibration = calibration
        self.max_bytes = config.FRAME_HISTORY_BYTES if max_bytes is None else max_bytes
        self.frames = []
        self._count = 0
        self._lock = threading.Lock()

    def add(self, image, stats, source, readout, axes, label=None):
        """Keep a frame: `image` is its small copy, `stats` get_frame's numbers for the full frame,
        `readout` the snapshot it was taken in. Returns the entry."""
        readout = readout or {}
        optics, camera = readout.get("optics") or {}, readout.get("camera") or {}
        zoom = optics.get("zoom")
        calibrated = self.calibration.scale(zoom) if self.calibration is not None and zoom else None
        scale = calibrated or nominal_scale(readout, axes)
        with self._lock:
            self._count += 1
            entry = {"n": self._count, "t": self.clock(), "source": source,
                     "position": {a: (readout.get("position") or {}).get(a) for a in AXES},
                     "settings": {"zoom": zoom, "laser": optics.get("laser"), "filter": optics.get("filter"),
                                  "intensity": optics.get("intensity"), "exposure_s": camera.get("exposure_time_s")},
                     "measures": _measures(stats, readout, scale, "calibrated" if calibrated else "nominal"),
                     "image": np.asarray(image) if image is not None else None, "field_um": field_um(readout)}
            if label:
                entry["label"] = str(label)
            self.frames.append(entry)
            while len(self.frames) > 1 and sum(_bytes(f) for f in self.frames) > self.max_bytes:
                self.frames.pop(0)
            return entry

    def pick(self, chosen):
        """The frames `chosen` names: n (the last n), a list of numbers, or "a-b"; at most
        LOOK_FRAMES_MAX. Raises ValueError for a number the history does not hold."""
        with self._lock:
            frames = list(self.frames)
        by_number = {f["n"]: f for f in frames}
        if isinstance(chosen, bool):
            raise ValueError("frames is a count, a list of frame numbers or a range like '3-10'")
        if isinstance(chosen, int):
            picked = frames[-chosen:] if chosen > 0 else []
        elif isinstance(chosen, str) and re.fullmatch(r"\s*\d+\s*-\s*\d+\s*", chosen):
            low, high = (int(part) for part in chosen.split("-"))
            picked = [f for f in frames if low <= f["n"] <= high]
        elif isinstance(chosen, list) and all(isinstance(n, int) and not isinstance(n, bool) for n in chosen):
            missing = [n for n in chosen if n not in by_number]
            if missing:
                held = f"{frames[0]['n']} to {frames[-1]['n']}" if frames else "none"
                raise ValueError(f"no frame {', '.join(map(str, missing))}; the history holds {held}")
            picked = [by_number[n] for n in chosen]
        else:
            raise ValueError("frames is a count, a list of frame numbers or a range like '3-10'")
        if len(picked) > config.LOOK_FRAMES_MAX:
            raise ValueError(f"at most {config.LOOK_FRAMES_MAX} frames in one look")
        return picked

    def brief(self, entry):
        """A frame for the model: its number, time, source, label, position, settings and measures."""
        out = {"n": entry["n"], "time": hms(entry["t"]), "source": entry["source"]}
        if entry.get("label"):
            out["label"] = entry["label"]
        out["position"] = entry["position"]
        out["settings"] = entry["settings"]
        out.update(entry["measures"])
        return out

    def compare(self, picked):
        """Drift against the first frame shown and the change against the previous one, for each
        frame after the first: the image shift (um, by phase correlation, when the zoom matches)
        and the changes in focus measure and peak."""
        out = []
        for index, entry in enumerate(picked[1:], 1):
            row = {"n": entry["n"]}
            for name, other in (("since_first", picked[0]), ("since_previous", picked[index - 1])):
                row[name] = _change(other, entry)
            out.append(row)
        return out

    def listing(self):
        """For the readout: the count, the labels and the last three frames, briefly."""
        with self._lock:
            frames = list(self.frames)
        if not frames:
            return None
        labels = {f["label"]: f["n"] for f in frames if f.get("label")}
        last = [{"n": f["n"], "time": hms(f["t"]), "source": f["source"],
                 **{k: f["measures"].get(k) for k in ("peak", "saturated", "focus", "centre_move_um")}}
                for f in frames[-3:]]
        return {"count": len(frames), "numbers": f"{frames[0]['n']}-{frames[-1]['n']}", "labels": labels, "last": last}

    def clear(self):
        with self._lock:
            self.frames, self._count = [], 0


def _bytes(entry):
    image = entry.get("image")
    return image.nbytes if image is not None else 0


def _measures(stats, readout, scale, scale_kind):
    full = float(stats.get("full_scale") or 65535.0)
    centroid = stats.get("signal_centroid")
    out = {"peak": round(float(stats.get("max", 0.0)) / full, 3),
           "contrast": round((float(stats.get("max", 0.0)) - float(stats.get("background", 0.0))) / full, 4),
           "mean": round(float(stats.get("mean", 0.0)) / full, 4),
           "saturated": round(float(stats.get("saturated_fraction", 0.0)), 4),
           "focus": round(float(stats.get("focus_measure", 0.0)), 4)}
    if centroid is None:
        return dict(out, signal="none")
    offset = (centroid["col"] - 0.5, 0.5 - centroid["row"])            # fraction of the field right, up
    shape = stats.get("shape") or [0, 0]
    out["offset_px"] = {"right": round(offset[0] * shape[1], 1), "up": round(offset[1] * shape[0], 1)}
    field = field_um(readout)
    if field is not None:
        out["offset_um"] = {"right": round(offset[0] * field[0], 1), "up": round(offset[1] * field[1], 1)}
    if scale is not None:
        out["centre_move_um"] = centre_move(offset, scale)
        out["scale"] = scale_kind
    return out


def _change(before, after):
    change = {"seconds": round(after["t"] - before["t"], 1),
              "focus": round(after["measures"]["focus"] - before["measures"]["focus"], 4),
              "peak": round(after["measures"]["peak"] - before["measures"]["peak"], 3)}
    a, b, field = before.get("image"), after.get("image"), after.get("field_um")
    if (a is not None and b is not None and field and a.shape == b.shape
            and before["settings"]["zoom"] == after["settings"]["zoom"]):
        moved = shift(a, b)
        if moved is not None:
            change["image_shift_um"] = {"right": round(moved["right"] * field[0] / b.shape[1], 1),
                                        "up": round(-moved["down"] * field[1] / b.shape[0], 1)}
            change["shift_confidence"] = moved["confidence"]
    return change


def flag(entry):
    """Why a frame cannot be measured from, or None."""
    measures = entry["measures"]
    if measures.get("signal") == "none" or measures["contrast"] < config.MAP_SIGNAL_MIN:
        return "no signal"
    if measures["saturated"] > config.MAP_SATURATED_MAX:
        return "saturated"
    return None


def sample_map(history):
    """The map: per zoom and light (laser, filter), newest first, where the sample would be
    centred in stage coordinates, the best focus from the focus curve with its uncertainty, the
    last good light, and the labelled places; frames that cannot be measured from are left out
    and named. None while the history is empty."""
    with history._lock:
        frames = list(history.frames)
    if not frames:
        return None
    now = history.clock()
    groups = {}
    for entry in frames:
        settings = entry["settings"]
        groups.setdefault((settings["zoom"], settings["laser"], settings["filter"]), []).append(entry)
    out = []
    for (zoom, laser, filter_name), group in sorted(groups.items(), key=lambda g: -g[1][-1]["t"])[:config.MAP_GROUPS]:
        usable = [f for f in group if flag(f) is None]
        row = {"zoom": zoom, "laser": laser, "filter": filter_name}
        place = _place(usable, now)
        if place:
            row["sample_at"] = place
        focus = _focus(usable, now)
        if focus:
            row["best_focus"] = focus
        good = [f for f in usable if f["measures"]["peak"] <= config.MAP_PEAK_GOOD_MAX]
        if good:
            row["good_light"] = {"intensity": good[-1]["settings"]["intensity"],
                                 "exposure_s": good[-1]["settings"]["exposure_s"], "frame": good[-1]["n"]}
        left_out = {f["n"]: flag(f) for f in group if flag(f)}
        if left_out:
            row["left_out"] = left_out
        out.append(row)
    labels = {f["label"]: dict({a: f["position"][a] for a in AXES}, frame=f["n"], age_s=int(now - f["t"]))
              for f in frames if f.get("label")}
    return {"groups": out, **({"labels": labels} if labels else {})}


def _place(usable, now):
    """Where the stage would centre the sample: each frame's position plus its centring move, the
    median over the last few frames."""
    found = [(f["position"]["x"] + f["measures"]["centre_move_um"]["x"],
              f["position"]["y"] + f["measures"]["centre_move_um"]["y"], f)
             for f in usable[-config.MAP_PLACE_FRAMES:]
             if f["measures"].get("centre_move_um") and f["position"]["x"] is not None]
    if not found:
        return None
    return {"x": round(float(np.median([p[0] for p in found])), 1), "y": round(float(np.median([p[1] for p in found])), 1),
            "frames": [p[2]["n"] for p in found], "scale": found[-1][2]["measures"].get("scale"),
            "age_s": int(now - found[-1][2]["t"])}


def _focus(usable, now):
    """The best focus position from the frames at the newest frame's place (within MAP_SAME_PLACE_UM
    on x, y and z): the vertex of a parabola through the sharpest frame and its neighbours on f,
    with half their spacing as the uncertainty. At the edge of the frames' range, the edge, and
    which way to search."""
    if not usable or usable[-1]["position"]["f"] is None:
        return None
    here = usable[-1]["position"]
    curve = {}
    for f in usable:
        p = f["position"]
        if all(p[a] is not None and abs(p[a] - here[a]) <= config.MAP_SAME_PLACE_UM for a in ("x", "y", "z")):
            curve[p["f"]] = max(curve.get(p["f"], 0.0), f["measures"]["focus"])
    if len(curve) < 2:
        return None
    positions = sorted(curve)
    index = max(range(len(positions)), key=lambda i: curve[positions[i]])
    best = positions[index]
    out = {"f": round(best, 1), "frames_used": len(positions), "age_s": int(now - usable[-1]["t"])}
    if index in (0, len(positions) - 1):
        out["edge"] = "search lower f" if index == 0 else "search higher f"
        out["plus_minus"] = round(abs(positions[1] - positions[0]) if index == 0 else
                                  abs(positions[-1] - positions[-2]), 1)
        return out
    (f0, f1, f2), (v0, v1, v2) = positions[index - 1:index + 2], [curve[p] for p in positions[index - 1:index + 2]]
    denominator = (f0 - f1) * (f0 - f2) * (f1 - f2)
    a = (f2 * (v1 - v0) + f1 * (v0 - v2) + f0 * (v2 - v1)) / denominator if denominator else 0.0
    b = (f2 ** 2 * (v0 - v1) + f1 ** 2 * (v2 - v0) + f0 ** 2 * (v1 - v2)) / denominator if denominator else 0.0
    if a < 0:
        out["f"] = round(float(np.clip(-b / (2 * a), f0, f2)), 1)
    out["plus_minus"] = round(min(f1 - f0, f2 - f1) / 2, 1)
    return out
