"""Virtual camera: zoom and pan over the drawing while it is being made.

Two ways to drive it:
  * auto   - zoom in a little and glide along with the pen, then pull back out
  * manual - keyframes from a JSON file, for exact "zoom to the icons" moves

Camera state is (zoom, cx, cy): zoom >= 1.0 and the view centre in 0..1 image
coordinates.  The view is always kept inside the picture.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def _smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


class Camera:
    def __init__(self, keyframes: list[dict] | None = None, auto_zoom: float | None = None):
        if not keyframes and not auto_zoom:
            raise ValueError("camera needs keyframes or auto_zoom")
        # keyframe times may be seconds, negative seconds (from the end) or "NN%" of the clip
        self.keyframes = [dict(k) for k in (keyframes or [])]
        self.auto_zoom = auto_zoom
        self._total = 0.0
        self._draw_end = 0.0
        self.text_end = None        # set per scene: when the headline is finished
        self._cam = None            # auto mode: current smoothed centre (x, y)

    # ---------------- construction ----------------
    @classmethod
    def from_file(cls, path: str | Path) -> "Camera":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        auto = None
        if isinstance(data, dict):
            auto = data.get("auto")
            if auto is True:
                auto = 1.3
            auto = max(float(auto), 1.0) if auto else None
            data = data.get("keyframes", [])
        if not isinstance(data, list) or (not data and not auto):
            raise ValueError(f"{path}: expected keyframes and/or \"auto\"")
        frames = []
        for k in data:
            if "t" not in k:
                raise ValueError(f"{path}: every keyframe needs a 't' (seconds, negative seconds, or \"NN%\")")
            frames.append({
                "t": k["t"],
                "zoom": max(float(k.get("zoom", 1.0)), 1.0),
                "x": float(k.get("x", 0.5)),
                "y": float(k.get("y", 0.5)),
            })
        return cls(keyframes=frames, auto_zoom=auto)

    @classmethod
    def auto(cls, zoom: float = 1.3) -> "Camera":
        return cls(auto_zoom=max(zoom, 1.0))

    # ---------------- per-scene setup ----------------
    def prepare(self, total_duration: float, draw_end: float) -> None:
        self._total = total_duration
        self._draw_end = draw_end
        self._cam = None
        art = self.text_end if self.text_end is not None else 0.35 * draw_end
        for k in self.keyframes:
            k.setdefault("_t", k["t"])
            k["t"] = self._parse_t(k["_t"], total_duration, draw_end, art)
        self.keyframes.sort(key=lambda k: k["t"])

    @staticmethod
    def _parse_t(t, total, draw_end, art):
        """seconds | -seconds (from end) | "NN%" | "art+N" (after headline done) | "draw-N" (before drawing ends)."""
        if isinstance(t, str):
            t = t.strip().lower().replace(" ", "")
            if t.endswith("%"):
                return float(t[:-1]) / 100.0 * total
            for name, base in (("art", art), ("draw", draw_end), ("end", total)):
                if t.startswith(name):
                    rest = t[len(name):]
                    return max(base + (float(rest) if rest else 0.0), 0.0)
            t = float(t)
        t = float(t)
        return max(total + t, 0.0) if t < 0 else t

    # ---------------- state ----------------
    def state(self, t: float, pen_xy: tuple[float, float] | None, size: tuple[int, int]):
        if self.keyframes and self.auto_zoom:
            # follow the pen until just before the first keyframe, then let the keyframes take over
            za, xa, ya = self._auto(t, pen_xy, size)
            zm, xm, ym = self._manual(t)
            w = _smooth((t - (self.keyframes[0]["t"] - 0.6)) / 0.6)
            z, cx, cy = za + (zm - za) * w, xa + (xm - xa) * w, ya + (ym - ya) * w
        elif self.keyframes:
            z, cx, cy = self._manual(t)
        else:
            z, cx, cy = self._auto(t, pen_xy, size)
        half = 0.5 / z
        return z, min(max(cx, half), 1 - half), min(max(cy, half), 1 - half)

    def _manual(self, t: float):
        ks = self.keyframes
        if t <= ks[0]["t"]:
            k = ks[0]
            return k["zoom"], k["x"], k["y"]
        for a, b in zip(ks, ks[1:]):
            if a["t"] <= t <= b["t"]:
                u = _smooth((t - a["t"]) / max(b["t"] - a["t"], 1e-6))
                return (a["zoom"] + (b["zoom"] - a["zoom"]) * u,
                        a["x"] + (b["x"] - a["x"]) * u,
                        a["y"] + (b["y"] - a["y"]) * u)
        k = ks[-1]
        return k["zoom"], k["x"], k["y"]

    def _auto(self, t: float, pen_xy, size, outro: bool = True):
        w, h = size
        end = self._draw_end
        if end < 2.0:
            return 1.0, 0.5, 0.5
        # zoom: ease in over the first 0.8 s, ease out over the last 1.0 s of drawing
        zin = _smooth(t / 0.8)
        zout = 1.0 - _smooth((t - (end - 1.0)) / 1.0) if outro else 1.0
        zoom = 1.0 + (self.auto_zoom - 1.0) * min(zin, zout)
        if pen_xy is not None:
            target = (pen_xy[0] / w, pen_xy[1] / h)
            if self._cam is None:
                self._cam = (0.5, 0.5)
            # dead zone: only move when the pen leaves the middle of the view
            dx, dy = target[0] - self._cam[0], target[1] - self._cam[1]
            limit = 0.18 / zoom
            if abs(dx) > limit or abs(dy) > limit:
                self._cam = (self._cam[0] + 0.06 * dx, self._cam[1] + 0.06 * dy)
        cx, cy = self._cam if self._cam else (0.5, 0.5)
        # glide back to the centre while zooming out
        back = _smooth((t - (end - 1.0)) / 1.0) if outro else 0.0
        return zoom, cx + (0.5 - cx) * back, cy + (0.5 - cy) * back

    # ---------------- apply ----------------
    @staticmethod
    def apply(frame: np.ndarray, zoom: float, cx: float, cy: float) -> np.ndarray:
        if zoom <= 1.0001:
            return frame
        h, w = frame.shape[:2]
        x0 = cx * w - w / (2 * zoom)
        y0 = cy * h - h / (2 * zoom)
        m = np.array([[zoom, 0, -x0 * zoom], [0, zoom, -y0 * zoom]], dtype=np.float32)
        return cv2.warpAffine(frame, m, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
