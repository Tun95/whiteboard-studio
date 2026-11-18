"""Picture effects: make chosen parts of the drawing move once they are drawn.

A sidecar file IMAGE.effects.json lists boxes (fractions of the picture, 0..1)
and a movement for each:

  {"effects": [
     {"box": [0.28, 0.40, 0.46, 0.72], "type": "pulse"},
     {"box": [0.05, 0.40, 0.24, 0.72], "type": "bounce", "start": "art+1.0"},
     {"box": [0.70, 0.30, 0.95, 1.00], "type": "wave", "amp": 1.2}
  ]}

types (idle movement, after the object is drawn):
  sway, wave, bounce, pulse, float, pop, shake, glow
  swing   bends the picture inside the box around a "pivot" [x, y] (fractions): waving hand/forearm,
          nodding head...  "angle" (degrees, default 10), "freq" (default 1.2), "feather" (default 0.25)
types (entrances - the object is NOT drawn by the pen, it arrives instead):
  slide_left, slide_right, slide_up, slide_down, drop (falls and bounces), zoom_in
  "duration" seconds (default 0.8); default start "art+0.4"
  start  seconds | "NN%" | "art+N" (after headline) | "draw+N" (after ALL drawing) |
         "done+N" (N s after THIS object has been drawn)   default "done+0.15"
  end    same format; default end of clip
  amp    strength, 1.0 = default;  speed  1.0 = default
  anchor "bottom" | "center" (default depends on the type)

Top-level "hold": seconds of the clip kept after drawing ends so movements have
time to play (default 0.8).  {"hold": 1.0, "effects": [...]}

v13 - NO MORE JELLY / TEARING.  The moving object is cut out as its own layer (a mask), the page
behind it is repaired once (a "plate"), and only the layer moves - rigidly, over the plate.
Neighbours (chalkboard, monitor, body...) inside the box are never dragged along.
  "polygon": [[x,y],...]  trace the moving object (fractions of the picture) - exact cut-out, best for
                          hands that touch other drawings.  Without it the cut-out is automatic.
  "bend": 0.6   (swing) how much of the limb stays still near the pivot (0 = rigid, 1 = long gentle bend)
  "isolate": true|false  (automatic cut-out) keep only the drawing connected to the pivot (default true for swing)

Only the object inside the box moves, so keep each box tight around ONE object.
Movement eases in after its start and eases out before the clip ends, so the
last frame is always the original drawing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from .camera import Camera, _smooth

ENTER = {"slide_left", "slide_right", "slide_up", "slide_down", "drop", "zoom_in"}
TYPES = {"sway", "wave", "bounce", "pulse", "float", "pop", "shake", "glow", "swing"} | ENTER
BOTTOM = {"sway", "wave", "bounce"}


def _out_cubic(p):
    return 1 - (1 - p) ** 3


def _out_bounce(p):
    n1, d1 = 7.5625, 2.75
    if p < 1 / d1:
        return n1 * p * p
    if p < 2 / d1:
        p -= 1.5 / d1
        return n1 * p * p + 0.75
    if p < 2.5 / d1:
        p -= 2.25 / d1
        return n1 * p * p + 0.9375
    p -= 2.625 / d1
    return n1 * p * p + 0.984375


def _out_back(p):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _bg_color(img):
    """Most common colour of the picture = the paper."""
    q = (img[::4, ::4].reshape(-1, 3) // 8).astype(np.int32)
    key = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    k = np.bincount(key).argmax()
    return np.array([(k // 1024) * 8 + 4, ((k // 32) % 32) * 8 + 4, (k % 32) * 8 + 4], np.float32)


def _fill_holes(m):
    """m: uint8 0/1.  Fill enclosed holes so the inside of a hand/face moves with its outline."""
    h, w = m.shape
    pad = np.pad(m, 1)
    ff = (pad * 255).astype(np.uint8)
    mask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 128)
    return ((ff != 128)[1:-1, 1:-1]).astype(np.uint8)


def _object_mask(img, bg, box, polygon, pivot, isolate):
    """Soft 0..1 mask of the moving object inside box (pixel box X0,Y0,X1,Y1)."""
    h, w = img.shape[:2]
    X0, Y0, X1, Y1 = box
    if polygon is not None and len(polygon) >= 3:
        pts = np.array([[(p[0] * w if p[0] <= 1 else p[0]), (p[1] * h if p[1] <= 1 else p[1])] for p in polygon], np.float32)
        full = np.zeros((h, w), np.uint8)
        cv2.fillPoly(full, [np.round(pts).astype(np.int32)], 1)
        return cv2.GaussianBlur(full.astype(np.float32), (3, 3), 0)
    sub = img[Y0:Y1, X0:X1].astype(np.float32)
    ink = (np.abs(sub - bg).max(axis=2) > 14).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    ink = _fill_holes(ink)
    if isolate:
        n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        if n > 2:
            px = int(np.clip(pivot[0] - X0, 0, X1 - X0 - 1))
            py = int(np.clip(pivot[1] - Y0, 0, Y1 - Y0 - 1))
            areas = st[1:, cv2.CC_STAT_AREA]
            big = areas.max()
            keep = np.zeros(n, bool)
            for i in range(1, n):
                if areas[i - 1] >= 0.03 * big:
                    keep[i] = True
            # always keep the piece nearest to the pivot
            ys, xs = np.nonzero(lab > 0)
            if xs.size:
                i = lab[ys[np.argmin((xs - px) ** 2 + (ys - py) ** 2)], xs[np.argmin((xs - px) ** 2 + (ys - py) ** 2)]]
                keep[i] = True
            ink = keep[lab].astype(np.uint8)
    ink = cv2.dilate(ink, np.ones((3, 3), np.uint8), iterations=1)
    full = np.zeros((h, w), np.float32)
    full[Y0:Y1, X0:X1] = cv2.GaussianBlur(ink.astype(np.float32), (3, 3), 0)
    return full


class Effects:
    def __init__(self, items: list[dict]):
        if not items:
            raise ValueError("effects file has no effects")
        self.items = items
        self.text_end = None
        self.hold = 0.8
        self.preview_path = None
        self.jobs: list[dict] = []
        self._done: list = []

    @classmethod
    def from_file(cls, path) -> "Effects":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        hold = 0.8
        if isinstance(data, dict):
            hold = float(data.get("hold", 0.8))
            data = data.get("effects", [])
        items = []
        for k, e in enumerate(data, 1):
            box = e.get("box")
            if not box or len(box) != 4:
                raise ValueError(f"{path}: effect {k} needs a box [x0, y0, x1, y1] (fractions 0..1)")
            kind = str(e.get("type", "")).lower()
            if kind not in TYPES:
                raise ValueError(f"{path}: effect {k} type must be one of {sorted(TYPES)}")
            items.append(dict(e, box=[float(v) for v in box], type=kind))
        fx = cls(items)
        fx.hold = hold
        return fx

    # ------------------------------------------------------------------
    @staticmethod
    def _px_box(e, w, h):
        x0, y0, x1, y1 = e["box"]
        if max(x0, y0, x1, y1) > 1.0:
            x0, x1, y0, y1 = x0 / w, x1 / w, y0 / h, y1 / h
        X0, X1 = sorted((int(round(x0 * w)), int(round(x1 * w))))
        Y0, Y1 = sorted((int(round(y0 * h)), int(round(y1 * h))))
        return max(X0, 0), max(Y0, 0), min(X1, w), min(Y1, h)

    def pre(self, img: np.ndarray, timing: np.ndarray):
        """Called before drawing is scheduled into frames: remember when each object finishes
        being drawn, and hide entrance objects from the pen."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        self._done = []
        for e in self.items:
            X0, Y0, X1, Y1 = self._px_box(e, w, h)
            done = None
            if X1 - X0 >= 4 and Y1 - Y0 >= 4:
                sel = gray[Y0:Y1, X0:X1] < 240
                tb = timing[Y0:Y1, X0:X1][sel]
                tb = tb[np.isfinite(tb)]
                if tb.size:
                    done = float(tb.max())
                if e["type"] in ENTER:
                    sub = timing[Y0:Y1, X0:X1]
                    sub[sel] = np.inf
            self._done.append(done)

    # ------------------------------------------------------------------
    def prepare(self, img: np.ndarray, total: float, draw_end: float, fade: float, timing=None):
        h, w = img.shape[:2]
        art = self.text_end if self.text_end is not None else 0.35 * draw_end
        bg = _bg_color(img)
        self.jobs = []
        for idx, e in enumerate(self.items):
            X0, Y0, X1, Y1 = self._px_box(e, w, h)
            bw, bh = X1 - X0, Y1 - Y0
            if bw < 4 or bh < 4:
                continue
            kind = e["type"]
            pad = int((0.95 if kind == "glow" else 0.35) * max(bw, bh)) + 6
            ex0, ey0 = max(X0 - pad, 0), max(Y0 - pad, 0)
            ex1, ey1 = min(X1 + pad, w), min(Y1 + pad, h)
            if kind in ENTER:
                ex0, ey0, ex1, ey1 = 0, 0, w, h
            ew, eh = ex1 - ex0, ey1 - ey0

            oy, ox = Y0 - ey0, X0 - ex0
            pv = e.get("pivot", [(X0 + bw / 2) / w, Y1 / h])
            pivot_abs = ((pv[0] * w if pv[0] <= 1 else pv[0]), (pv[1] * h if pv[1] <= 1 else pv[1]))
            isolate = bool(e.get("isolate", kind == "swing"))
            full_m = _object_mask(img, bg, (X0, Y0, X1, Y1), e.get("polygon"), pivot_abs, isolate)
            if e.get("polygon") is None:
                pass
            else:   # a traced polygon may leave its box: grow the working rectangle to hold it
                ys_, xs_ = np.nonzero(full_m > 0.01)
                if xs_.size:
                    ex0, ey0 = max(min(ex0, xs_.min() - 2), 0), max(min(ey0, ys_.min() - 2), 0)
                    ex1, ey1 = min(max(ex1, xs_.max() + 3), w), min(max(ey1, ys_.max() + 3), h)
                    if kind in ENTER:
                        ex0, ey0, ex1, ey1 = 0, 0, w, h
                    ew, eh = ex1 - ex0, ey1 - ey0
                    oy, ox = Y0 - ey0, X0 - ex0
            maskc = full_m[ey0:ey1, ex0:ex1].copy()
            patchc = img[ey0:ey1, ex0:ex1].copy()
            # the plate = the page with the moving object removed and the hole repaired
            hole = (cv2.dilate((maskc > 0.02).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2) * 255)
            plate = cv2.inpaint(patchc, hole, 5, cv2.INPAINT_NS) if hole.any() else patchc.copy()

            done = self._done[idx] if idx < len(self._done) and self._done[idx] is not None else draw_end
            dflt = "art+0.4" if kind in ENTER else "done+0.15"
            st = str(e.get("start", dflt)).strip().lower().replace(" ", "")
            if st.startswith("done"):
                start = done + fade + (float(st[4:]) if st[4:] else 0.0)
            else:
                start = Camera._parse_t(st, total, draw_end, art)
            dur = float(e.get("duration", 0.8)) / max(float(e.get("speed", 1.0)), 0.1)
            if kind in ENTER:
                start = min(start, total - dur - 0.1)     # the object must have arrived before the clip ends
            end = Camera._parse_t(e["end"], total, draw_end, art) if "end" in e else total
            anchor = e.get("anchor") or ("bottom" if kind in BOTTOM else "center")
            ax = ox + bw / 2.0
            ay = oy + (bh if anchor == "bottom" else bh / 2.0)
            glow = None
            if kind == "glow":
                yy, xx = np.mgrid[0:eh, 0:ew].astype(np.float32)
                r = 0.7 * max(bw, bh)
                d = np.sqrt((xx - (ox + bw / 2)) ** 2 + (yy - (oy + bh / 2)) ** 2) / r
                glow = np.clip(1.0 - d, 0, 1) ** 1.5
            self.jobs.append(dict(
                kind=kind, rect=(ex0, ey0, ex1, ey1), size=(ew, eh), bw=bw, bh=bh,
                mask=maskc, patch=patchc, plate=plate, hole=(cv2.GaussianBlur(hole.astype(np.float32) / 255.0, (3, 3), 0))[..., None], wipe=maskc > 0.01, anchor=(ax, ay),
                start=start, end=min(end, total), amp=float(e.get("amp", 1.0)),
                speed=float(e.get("speed", 1.0)), glow=glow,
                color=tuple(e.get("color", (255, 214, 90))), box=(X0, Y0, X1, Y1), dur=dur,
                full=(w, h), cfg=e))
            if kind == "swing":
                j = self.jobs[-1]
                j["pivot"] = (pivot_abs[0] - ex0, pivot_abs[1] - ey0)
                yy, xx = np.mgrid[0:eh, 0:ew].astype(np.float32)
                d = np.sqrt((xx - j["pivot"][0]) ** 2 + (yy - j["pivot"][1]) ** 2)
                sel = maskc > 0.3
                reach = float(d[sel].max()) if sel.any() else float(max(bw, bh))
                bend = max(float(e.get("bend", 0.6)), 0.0)
                if bend <= 0:
                    wt = np.ones_like(d)
                else:
                    t_ = np.clip(d / (bend * reach), 0, 1)
                    wt = t_ * t_ * (3 - 2 * t_)
                j["weight"] = wt.astype(np.float32)
                j["gx"], j["gy"] = xx, yy
                j["rgba"] = np.dstack([patchc, (np.clip(maskc, 0, 1) * 255).astype(np.uint8)])
        if self.preview_path:
            self._preview(img)

    def _preview(self, img):
        p = img.copy()
        for k, j in enumerate(self.jobs, 1):
            x0, y0, x1, y1 = j["box"]
            cv2.rectangle(p, (x0, y0), (x1, y1), (255, 0, 0), 3)
            cv2.putText(p, f'{k} {j["kind"]}', (x0 + 4, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        cv2.imwrite(str(self.preview_path), cv2.cvtColor(p, cv2.COLOR_RGB2BGR))

    # ------------------------------------------------------------------
    def apply(self, frame: np.ndarray, t: float):
        """Draw the moving parts into frame; returns undo records."""
        undo = []
        for j in self.jobs:
            if j["kind"] in ENTER:
                rec = self._enter(frame, j, t)
                if rec:
                    undo.append(rec)
                continue
            if t < j["start"] or t > j["end"]:
                continue
            if j["kind"] == "swing":
                rec = self._swing(frame, j, t)
                if rec:
                    undo.append(rec)
                continue
            u = t - j["start"]
            env = _smooth(u / 0.5) * _smooth((j["end"] - t) / 0.4)
            if env <= 0.001:
                continue
            ph = u * j["speed"]
            amp = j["amp"] * env
            bw, bh, kind = j["bw"], j["bh"], j["kind"]
            ang, sc, dx, dy = 0.0, 1.0, 0.0, 0.0
            if kind == "sway":
                ang = 3.0 * amp * math.sin(2 * math.pi * 0.6 * ph)
            elif kind == "wave":
                ang = 14.0 * amp * math.sin(2 * math.pi * 1.4 * ph)
            elif kind == "bounce":
                dy = -0.10 * bh * amp * abs(math.sin(math.pi * 1.2 * ph))
            elif kind == "pulse":
                sc = 1.0 + 0.06 * amp * math.sin(2 * math.pi * 0.9 * ph)
            elif kind == "float":
                dy = 0.05 * bh * amp * math.sin(2 * math.pi * 0.4 * ph)
                dx = 0.015 * bw * amp * math.sin(2 * math.pi * 0.27 * ph)
            elif kind == "pop":
                q = (ph % 3.0) / 0.6
                if q < 1.0:
                    sc = 1.0 + 0.18 * amp * math.sin(math.pi * q)
            elif kind == "shake":
                q = (ph % 2.5) / 0.5
                if q < 1.0:
                    dx = 0.04 * bw * amp * math.sin(2 * math.pi * 9 * (ph % 2.5)) * (1 - q)

            ex0, ey0, ex1, ey1 = j["rect"]
            ew, eh = j["size"]
            region = frame[ey0:ey1, ex0:ex1]
            undo.append((slice(ey0, ey1), slice(ex0, ex1), region.copy()))
            region[:] = (region * (1 - j["hole"]) + j["plate"] * j["hole"]).astype(np.uint8)   # lift the object off: only its own hole is repaired
            if j["glow"] is not None:
                a = (j["glow"] * amp * 0.55 * (0.65 + 0.35 * math.sin(2 * math.pi * 0.8 * ph)))[..., None]
                col = np.array(j["color"], np.float32)
                region[:] = (region * (1 - a) + col * a).astype(np.uint8)
                region[:] = (region * (1 - j["mask"][..., None]) + j["patch"] * j["mask"][..., None]).astype(np.uint8)
                continue
            M = cv2.getRotationMatrix2D(j["anchor"], ang, sc)
            M[0, 2] += dx
            M[1, 2] += dy
            pw = cv2.warpAffine(j["patch"], M, (ew, eh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            mw = cv2.warpAffine(j["mask"], M, (ew, eh), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)[..., None]
            region[:] = (region * (1 - mw) + pw * mw).astype(np.uint8)
        return undo

    def _enter(self, frame, j, t):
        p = (t - j["start"]) / j["dur"]
        if p < 0:
            return None                                   # not arrived yet: nothing drawn
        p = min(p, 1.0)
        w, h = j["full"]
        X0, Y0, X1, Y1 = j["box"]
        kind = j["kind"]
        dx = dy = 0.0
        sc = 1.0
        if kind == "slide_left":
            dx = -X1 * (1 - _out_cubic(p))
        elif kind == "slide_right":
            dx = (w - X0) * (1 - _out_cubic(p))
        elif kind == "slide_up":
            dy = -Y1 * (1 - _out_cubic(p))
        elif kind == "slide_down":
            dy = (h - Y0) * (1 - _out_cubic(p))
        elif kind == "drop":
            dy = -Y1 * (1 - _out_bounce(p))
        elif kind == "zoom_in":
            sc = max(_out_back(p), 0.001)
        saved = frame.copy()
        if p >= 1.0:
            pw, mw = j["patch"], j["mask"][..., None]
        else:
            cx, cy = (X0 + X1) / 2.0, (Y0 + Y1) / 2.0
            M = cv2.getRotationMatrix2D((cx, cy), 0.0, sc)
            M[0, 2] += dx
            M[1, 2] += dy
            pw = cv2.warpAffine(j["patch"], M, (w, h), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
            mw = cv2.warpAffine(j["mask"], M, (w, h), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)[..., None]
        frame[:] = (frame * (1 - mw) + pw * mw).astype(np.uint8)
        return (slice(0, h), slice(0, w), saved)

    def _swing(self, frame, j, t):
        u = t - j["start"]
        env = _smooth(u / 0.5) * _smooth((j["end"] - t) / 0.4)
        if env <= 0.001:
            return None
        cfg = j["cfg"]
        ang = math.radians(float(cfg.get("angle", 10.0))) * j["amp"] * env * \
            math.sin(2 * math.pi * float(cfg.get("freq", 1.2)) * u * j["speed"])
        ex0, ey0, ex1, ey1 = j["rect"]
        region = frame[ey0:ey1, ex0:ex1]
        saved = region.copy()
        px, py = j["pivot"]
        a = ang * j["weight"]
        c, s_ = np.cos(a), np.sin(a)
        dx, dy = j["gx"] - px, j["gy"] - py
        mx = (px + c * dx + s_ * dy).astype(np.float32)
        my = (py - s_ * dx + c * dy).astype(np.float32)
        moved = cv2.remap(j["rgba"], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        al = (moved[..., 3:4].astype(np.float32)) / 255.0
        # only the object layer moves, over the repaired page
        base = region * (1 - j["hole"]) + j["plate"] * j["hole"]
        region[:] = (base * (1 - al) + moved[..., :3] * al).astype(np.uint8)
        return (slice(ey0, ey1), slice(ex0, ex1), saved)

    @staticmethod
    def restore(frame, undo):
        for ys, xs, saved in reversed(undo):
            frame[ys, xs] = saved
