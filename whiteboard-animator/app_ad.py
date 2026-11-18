#!/usr/bin/env python3
"""
app_ad.py - app advert maker: ONLY the camera and the phone move.

Nothing inside the picture is ever bent, torn or "jelly":
  * the coloured scene (from Gemini) is a still picture - only the CAMERA moves over it (zoom / pan),
  * the phone is a separate, rigid layer drawn by this tool (your screenshots go on its screen):
    it can drop in, slide in, pop, float, sway, tilt, push in, slide out,
  * the screen content swipes from one screenshot to the next, with an optional "tap" ripple,
  * captions pop in over everything.

NEW in v2 (all optional, old ad.json files still work):
  phones[]            several phones in one scene
  screens[] items     "focus": [{"t":..,"zoom":1.8,"x":0.5,"y":0.3}]  zoom/pan INSIDE the screenshot
                      "crop_top"/"crop_bottom" per screenshot (fractions < 1 or pixels)
  phone.popouts[]     a section is PROJECTED OUT of the phone (light beams + floating card):
                      {"screen":0,"box":[x0,y0,x1,y1],"start":..,"end":..,"pos":[0.3,0.5],"width":0.36}
  phone.highlights[]  pulsing spotlight on part of a screenshot: {"screen":0,"box":[x0,y0,x1,y1],"start":..,"end":..,"spot":true}
  phone.projections[] a section of the screenshot is pulled OUT of the phone like a projector beam:
                      {"screen":0,"box":[x0,y0,x1,y1],"start":..,"end":..,"to":[0.3,0.5],"width":0.36,"tilt":-2}
  captions[] "style": glass | solid | classic,  "font": "Inter-Black.otf"  ({word} in braces = accent colour)
  props[]             your own PNG pictures (white background is removed automatically) that pop / drop / slide / float
  charts[]            animated equity curve or candlesticks drawing themselves: {"type":"equity"|"candles",...}
  fx[]                confetti | coins | sparkle | rise  (falling / rising particles)
  captions[]          "style": classic | card | glass | gradient ; "*word*" gets the accent colour ; defaults: "font", "caption_style"
                      "anim": pop|slide_left|slide_right|slide_up|drop ;  "counter": {"to":9,...} counts up
  scene "transition_type": fade | slide_left | slide_up | zoom | wipe

Needs: Python, numpy, opencv-python, Pillow, ffmpeg + ffprobe on PATH.
  python app_ad.py ad.json -o ad.mp4            (full ad)
  python app_ad.py ad.json -o t.mp4 --scene 3   (test one scene)
  --size 1080x1920 for a vertical version (Shorts / Reels / Status)
"""
import argparse, json, math, os, subprocess, tempfile
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def ease(t): t = clamp(t); return 0.5 - 0.5 * math.cos(math.pi * t)
def out_cubic(t): t = clamp(t); return 1 - (1 - t) ** 3
def out_back(t, s=1.5): t = clamp(t) - 1; return 1 + t * t * ((s + 1) * t + s)
def out_bounce(t):
    t = clamp(t); n, d = 7.5625, 2.75
    if t < 1 / d: return n * t * t
    if t < 2 / d: t -= 1.5 / d; return n * t * t + 0.75
    if t < 2.5 / d: t -= 2.25 / d; return n * t * t + 0.9375
    t -= 2.625 / d; return n * t * t + 0.984375

def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

# ------------------------------------------------------------------ io helpers
def read_image(path):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None: raise SystemExit("Cannot read image: " + path)
    return img

def audio_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: raise SystemExit("Cannot read audio: " + path)

def find_font(size, bold=True, path=None):
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if path:
        cands += [path, os.path.join(here, "fonts", path), os.path.join("C:/Windows/Fonts", path)]
    cands += ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/comicbd.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    for p in cands:
        if p and os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def m3(a):  # 2x3 -> 3x3
    return np.vstack([a, [0, 0, 1]]).astype(np.float64)
def T(x, y): return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], np.float64)
def S(s): return np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], np.float64)
def R(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)

def parse_t(v, dur, default=0.0):
    if v is None: return default
    if isinstance(v, str):
        v = v.strip()
        if v == "end": return dur
        if v.endswith("%"): return dur * float(v[:-1]) / 100
        v = float(v)
    return dur + v if v < 0 else float(v)

# ------------------------------------------------------------------ phone
def crop_px(v, total):
    v = float(v)
    return int(round(v * total)) if v < 1.0 else int(v)


class Phone:
    """A drawn doodle phone; the screen shows screenshots. Pure rigid layer."""
    def __init__(self, cfg, W, H, zmax):
        self.cfg = cfg
        shots = []
        for s in cfg["screens"]:
            d = s if isinstance(s, dict) else {"img": s}
            im = read_image(d["img"])
            ct = crop_px(d.get("crop_top", cfg.get("crop_top", 130)), im.shape[0])
            cb = crop_px(d.get("crop_bottom", cfg.get("crop_bottom", 140)), im.shape[0])
            im = im[ct:im.shape[0] - cb]
            shots.append((im, d))
        self.aspect_in = shots[0][0].shape[1] / shots[0][0].shape[0]
        self.hfrac = float(cfg.get("height", 0.80))
        self.ph = int(min(2300, max(500, self.hfrac * H * max(1.0, zmax) * 1.05)))
        bz = self.ph * 0.028
        bzt = self.ph * 0.040
        self.sh = int(self.ph - bzt - bz)
        self.sw = int(self.sh * self.aspect_in)
        self.pw = int(self.sw + 2 * bz)
        self.bz, self.bzt = bz, bzt
        # hi-res copies (so zooming inside the screenshot stays sharp)
        hw = int(min(self.sw * 2, shots[0][0].shape[1]))
        hw = max(hw, self.sw)
        hh = int(round(hw / self.aspect_in))
        self.hw, self.hh = hw, hh
        self.hires = []
        for im, _ in shots:
            interp = cv2.INTER_AREA if im.shape[1] > hw else cv2.INTER_CUBIC
            self.hires.append(cv2.resize(im, (hw, hh), interpolation=interp))
        self.screens = [cv2.resize(im, (self.sw, self.sh), interpolation=cv2.INTER_AREA) for im in self.hires]
        self.taps = [d.get("tap") for _, d in shots]
        self.focus = []
        for _, d in shots:
            kf = d.get("focus")
            self.focus.append(sorted([(float(k.get("t", 0)), float(k.get("zoom", 1)), float(k.get("x", .5)), float(k.get("y", .5)))
                                      for k in kf]) if kf else None)
        self.hls = cfg.get("highlights", [])
        body = hex2rgb(cfg.get("color", "#2b2d42"))
        edge = hex2rgb(cfg.get("edge", "#ffd23f"))
        k = 3
        W2, H2 = self.pw * k, self.ph * k
        im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        rad = int(self.pw * 0.14 * k)
        ow = int(self.pw * 0.022 * k)
        d.rounded_rectangle([0, 0, W2 - 1, H2 - 1], rad, fill=edge + (255,))
        d.rounded_rectangle([ow, ow, W2 - 1 - ow, H2 - 1 - ow], rad - ow, fill=body + (255,))
        cx = W2 // 2
        d.rounded_rectangle([cx - int(self.pw * .07 * k), int(bzt * k * .42), cx + int(self.pw * .07 * k), int(bzt * k * .42) + int(bzt * k * .16)],
                            int(bzt * k * .1), fill=(70, 74, 100, 255))
        d.ellipse([cx + int(self.pw * .13 * k), int(bzt * k * .40), cx + int(self.pw * .13 * k) + int(bzt * k * .2), int(bzt * k * .40) + int(bzt * k * .2)],
                  fill=(70, 74, 100, 255))
        self.body_rgba = np.array(im.resize((self.pw, self.ph), Image.LANCZOS))
        self.body_rgb = cv2.cvtColor(self.body_rgba[:, :, :3], cv2.COLOR_RGB2BGR)
        self.body_a = self.body_rgba[:, :, 3]
        mk = Image.new("L", (self.sw * 2, self.sh * 2), 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, self.sw * 2 - 1, self.sh * 2 - 1], int(self.pw * 0.075 * 2), fill=255)
        self.smask = np.array(mk.resize((self.sw, self.sh), Image.LANCZOS)).astype(np.float32)[:, :, None] / 255.0
        self.sx, self.sy = int(round(bz)), int(round(bzt))
        self.scale = self.hfrac * H / self.ph      # phone px -> world px

    # --- window (zoom/pan inside a screenshot) at scene time ts
    def window(self, i, ts):
        kf = self.focus[i]
        if not kf: return 1.0, 0.5, 0.5
        if ts <= kf[0][0]: _, z, x, y = kf[0]
        elif ts >= kf[-1][0]: _, z, x, y = kf[-1]
        else:
            for a, b in zip(kf, kf[1:]):
                if a[0] <= ts <= b[0]:
                    e = ease((ts - a[0]) / max(1e-6, b[0] - a[0]))
                    z, x, y = [a[j] + (b[j] - a[j]) * e for j in (1, 2, 3)]
                    break
        z = max(1.0, z)
        hw_, hh_ = 0.5 / z, 0.5 / z
        return z, clamp(x, hw_, 1 - hw_), clamp(y, hh_, 1 - hh_)

    def view(self, i, ts):
        z, x, y = self.window(i, ts)
        if z <= 1.0001:
            v = self.screens[i].copy()
        else:
            ww, wh = self.hw / z, self.hh / z
            x0 = int(round(x * self.hw - ww / 2)); y0 = int(round(y * self.hh - wh / 2))
            x0 = int(clamp(x0, 0, self.hw - int(ww))); y0 = int(clamp(y0, 0, self.hh - int(wh)))
            crop = self.hires[i][y0:y0 + int(wh), x0:x0 + int(ww)]
            v = cv2.resize(crop, (self.sw, self.sh), interpolation=cv2.INTER_AREA if crop.shape[1] > self.sw else cv2.INTER_CUBIC)
        # highlights for this screenshot
        for h in self.hls:
            if int(h.get("screen", 0)) != i: continue
            t0 = parse_t(h.get("start", 0), 1e9); t1 = parse_t(h.get("end", 9999), 1e9)
            if not (t0 <= ts <= t1): continue
            e = clamp((ts - t0) / 0.35) * clamp((t1 - ts) / 0.3)
            if e <= 0: continue
            bx0, by0, bx1, by1 = h["box"]
            # box is in the full screenshot -> view coordinates
            x0w, y0w = x - 0.5 / z, y - 0.5 / z
            px0, px1 = (bx0 - x0w) * z * self.sw, (bx1 - x0w) * z * self.sw
            py0, py1 = (by0 - y0w) * z * self.sh, (by1 - y0w) * z * self.sh
            col = hex2rgb(h.get("color", "#ff3d71"))[::-1]
            pul = 0.5 + 0.5 * math.sin((ts - t0) * 2 * math.pi * 1.4)
            grow = (1 - e) * 0.06 * self.sw
            r = int(self.sw * 0.035)
            if h.get("spot", True):
                m = np.zeros((self.sh, self.sw), np.float32)
                cv2.rectangle(m, (int(px0 - 6), int(py0 - 6)), (int(px1 + 6), int(py1 + 6)), 1.0, -1, cv2.LINE_AA)
                m = cv2.GaussianBlur(m, (0, 0), 10)[:, :, None]
                dim = 0.30 * e
                v = (v.astype(np.float32) * (1 - dim * (1 - m))).astype(np.uint8)
            ov = v.copy()
            th = max(4, int(self.sw * (0.008 + 0.006 * pul)))
            p0 = (int(px0 - grow - th), int(py0 - grow - th)); p1 = (int(px1 + grow + th), int(py1 + grow + th))
            cv2.rectangle(ov, p0, p1, col, th, cv2.LINE_AA)
            a = clamp(e * (0.75 + 0.25 * pul))
            v = cv2.addWeighted(v, 1 - a, ov, a, 0)
        return v

    def current(self, tl, schedule):
        i, e = 0, 0.0
        for k, (t0, t1) in enumerate(schedule):
            if tl >= t1: i = k + 1
            elif tl >= t0: i, e = k, ease((tl - t0) / (t1 - t0))
        return min(i, len(self.screens) - 1), e

    def frame(self, tl, schedule, dur, ts=0.0):
        """phone image (BGR, alpha); tl = phone-local time, ts = scene time"""
        n = len(self.screens)
        i, e, ripple = 0, 0.0, None
        for k, (t0, t1) in enumerate(schedule):          # swipe k -> k+1 between t0..t1
            if tl >= t1: i = k + 1
            elif tl >= t0:
                i, e = k, ease((tl - t0) / (t1 - t0))
            if self.taps[k] is not None and t0 - 0.35 <= tl <= t0 + 0.15:
                ripple = (self.taps[k], (tl - (t0 - 0.35)) / 0.5)
        i = min(i, n - 1)
        if e > 0 and i + 1 < n:
            a_, b_ = self.view(i, ts), self.view(i + 1, ts)
            sc = np.empty_like(a_)
            off = int(round(e * self.sw))
            sc[:, :self.sw - off] = a_[:, off:]
            sc[:, self.sw - off:] = b_[:, :off]
        else:
            sc = self.view(i, ts)
        if ripple is not None:
            (tx, ty), p = ripple
            ov = sc.copy()
            r = int(self.sw * (0.04 + 0.12 * clamp(p)))
            cv2.circle(ov, (int(tx * self.sw), int(ty * self.sh)), r, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(ov, (int(tx * self.sw), int(ty * self.sh)), r, (60, 60, 255), max(3, self.sw // 120), cv2.LINE_AA)
            sc = cv2.addWeighted(sc, 1 - 0.55 * (1 - clamp(p)), ov, 0.55 * (1 - clamp(p)), 0)
        out = self.body_rgb.copy()
        reg = out[self.sy:self.sy + self.sh, self.sx:self.sx + self.sw].astype(np.float32)
        reg = reg * (1 - self.smask) + sc.astype(np.float32) * self.smask
        out[self.sy:self.sy + self.sh, self.sx:self.sx + self.sw] = reg.astype(np.uint8)
        return out, self.body_a


class Rig:
    """one phone + its timing (schedule, enter/exit/motion)"""
    def __init__(self, pcfg, W, H, zmax, dur):
        self.pc = pcfg; self.W, self.H, self.dur = W, H, dur
        self.phone = Phone(pcfg, W, H, zmax)
        n = len(pcfg["screens"])
        self.schedule = []
        if n > 1:
            t_in = float(pcfg.get("enter_at", 0.4)) + float(pcfg.get("enter_time", 0.9))
            t_end = dur - float(pcfg.get("hold_end", 0.6))
            times = pcfg.get("swipe_times")
            if times:
                times = [parse_t(t, dur) for t in times]
            else:
                first = t_in + float(pcfg.get("hold_first", 0.9))
                step = (t_end - first) / max(1, n - 1)
                times = [first + k * step for k in range(n - 1)]
            st = float(pcfg.get("swipe_time", 0.45))
            self.schedule = [(t, t + st) for t in times]

    def schedule_local(self):
        t_in = float(self.pc.get("enter_at", 0.4))
        return [(a - t_in, b - t_in) for a, b in self.schedule]

    def state(self, t):
        pc, W, H = self.pc, self.W, self.H
        px, py = pc.get("pos", [0.5, 0.5])
        cx, cy = px * W, py * H
        rot = float(pc.get("tilt", 0.0))
        scale = 1.0; alpha = 1.0
        t_in = float(pc.get("enter_at", 0.4)); et = float(pc.get("enter_time", 0.9))
        en = pc.get("enter", "drop")
        e = clamp((t - t_in) / et)
        if t < t_in: return None
        if en == "drop": cy += -(1 - out_bounce(e)) * H * 1.1
        elif en == "slide_up": cy += (1 - out_back(e, 1.2)) * H * 1.1
        elif en == "slide_left": cx += (1 - out_back(e, 1.2)) * W * 0.8
        elif en == "slide_right": cx -= (1 - out_back(e, 1.2)) * W * 0.8
        elif en == "pop": scale = max(0.001, out_back(e))
        elif en == "fade": alpha = e
        elif en == "spin": scale = max(0.001, out_back(e)); rot += (1 - ease(e)) * 360
        motion = pc.get("motion", "float")
        te = t - t_in
        if motion in ("float", "float+sway"):
            cy += math.sin(te * 2 * math.pi / 3.2) * 0.012 * H
        if motion in ("sway", "float+sway"):
            rot += math.sin(te * 2 * math.pi / 3.6) * float(pc.get("sway", 3.0))
        if motion == "push":
            scale *= 1 + 0.10 * ease(te / max(0.5, self.dur - t_in))
        if motion == "tilt_in":
            rot += (1 - ease(te / 1.5)) * float(pc.get("tilt_from", -14))
        if motion == "turn":      # gentle 3D-ish turn: squeeze width a little while swaying
            rot += math.sin(te * 2 * math.pi / 4.0) * 2.0
            scale *= 1 + 0.03 * math.sin(te * 2 * math.pi / 4.0)
        ex = pc.get("exit")
        if ex:
            xt = self.dur - float(pc.get("exit_time", 0.6))
            ee = ease((t - xt) / float(pc.get("exit_time", 0.6)))
            if ex == "slide_down": cy += ee * H * 1.1
            elif ex == "slide_right": cx += ee * W * 0.8
            elif ex == "slide_left": cx -= ee * W * 0.8
            elif ex == "shrink": scale *= max(0.001, 1 - ee)
        return cx, cy, rot, scale, alpha


class Prop:
    """your own picture (PNG; a white background is removed automatically) as a moving rigid layer"""
    def __init__(self, cfg, W, H, zmax, dur):
        self.c = cfg; self.W, self.H, self.dur = W, H, dur
        im = cv2.imdecode(np.fromfile(cfg["image"], dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if im is None: raise SystemExit("Cannot read prop image: " + cfg["image"])
        if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
        if im.shape[2] == 3: im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
        if cfg.get("key_white", True) and im[:, :, 3].min() == 255:
            im = key_white(im, int(cfg.get("white_tol", 28)))
        ys, xs = np.nonzero(im[:, :, 3] > 8)             # trim empty margins
        if xs.size: im = im[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        hh = max(16, int(float(cfg.get("height", 0.2)) * H * max(1.0, zmax) * 1.1))
        hh = min(hh, im.shape[0]) if im.shape[0] > 16 else hh
        ww = max(8, int(im.shape[1] * hh / im.shape[0]))
        im = cv2.resize(im, (ww, hh), interpolation=cv2.INTER_AREA)
        self.rgb = np.ascontiguousarray(im[:, :, :3]); self.a = np.ascontiguousarray(im[:, :, 3])
        self.scale = float(cfg.get("height", 0.2)) * H / hh
        self.t0 = parse_t(cfg.get("enter_at", 0.4), dur)
        self.layer = cfg.get("layer", "front")

    def state(self, t):
        c = self.c; W, H = self.W, self.H
        if t < self.t0: return None
        px, py = c.get("pos", [0.5, 0.5]); cx, cy = px * W, py * H
        rot = float(c.get("tilt", 0)); scale = 1.0; alpha = 1.0
        et = float(c.get("enter_time", 0.7)); e = clamp((t - self.t0) / et)
        en = c.get("enter", "pop")
        if en == "pop": scale = max(0.001, out_back(e))
        elif en == "drop": cy += -(1 - out_bounce(e)) * H * 1.0
        elif en == "slide_left": cx += (1 - out_back(e, 1.2)) * W * 0.7
        elif en == "slide_right": cx -= (1 - out_back(e, 1.2)) * W * 0.7
        elif en == "slide_up": cy += (1 - out_back(e, 1.2)) * H * 0.9
        elif en == "fade": alpha = e
        te = t - self.t0
        m = c.get("motion", "float")
        amp = float(c.get("amp", 1.0))
        if m == "float": cy += math.sin(te * 2 * math.pi / 2.8) * 0.018 * H * amp
        elif m == "bob": cy -= abs(math.sin(te * math.pi / 0.9)) * 0.035 * H * amp
        elif m == "spin": rot += te * 90 * amp
        elif m == "pulse": scale *= 1 + 0.07 * amp * math.sin(te * 2 * math.pi / 1.2)
        elif m == "swing": rot += math.sin(te * 2 * math.pi / 2.2) * 8 * amp
        ex = c.get("exit")
        if ex:
            xt = self.dur - float(c.get("exit_time", 0.5)); ee = ease((t - xt) / float(c.get("exit_time", 0.5)))
            if ex == "shrink": scale *= max(0.001, 1 - ee)
            elif ex == "fade": alpha *= 1 - ee
        end = c.get("end")
        if end is not None and t > parse_t(end, self.dur): return None
        return cx, cy, rot, scale, alpha


def key_white(im, tol=28):
    """remove the plain white background (only the white connected to the picture edge)"""
    bgr = im[:, :, :3]
    near = (bgr.min(axis=2) >= 255 - tol).astype(np.uint8)
    h, w = near.shape
    pad = np.pad(near, 1, constant_values=1)
    lab_n, lab = cv2.connectedComponents(pad, connectivity=4)[:2]
    bg = (lab == lab[0, 0]) & (pad == 1)
    bg = bg[1:-1, 1:-1]
    a = np.where(bg, 0, 255).astype(np.uint8)
    a = cv2.erode(a, np.ones((2, 2), np.uint8))
    a = cv2.GaussianBlur(a, (3, 3), 0)
    out = im.copy(); out[:, :, 3] = a
    return out


def blend_layer(frame, C, rgb, a, cx, cy, rot, scale, alpha, base_scale, shadow=True):
    H, W = frame.shape[:2]
    ph, pw = rgb.shape[:2]
    Mp = C @ T(cx, cy) @ R(rot) @ S(base_scale * scale) @ T(-pw / 2, -ph / 2)
    r = cv2.warpAffine(rgb, Mp[:2], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    aa = cv2.warpAffine(a, Mp[:2], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    z = float(np.sqrt(abs(np.linalg.det(C[:2, :2]))))
    f = frame.astype(np.float32)
    if shadow:
        sh = cv2.GaussianBlur(aa, (0, 0), 14 * max(1.0, z))
        Ms = np.float32([[1, 0, 10 * z], [0, 1, 26 * z]])
        sh = cv2.warpAffine(sh, Ms, (W, H))
        f *= (1 - 0.35 * (sh.astype(np.float32) / 255.0) * alpha)[:, :, None]
    af = (aa.astype(np.float32) / 255.0 * alpha)[:, :, None]
    f = f * (1 - af) + r.astype(np.float32) * af
    return np.clip(f, 0, 255).astype(np.uint8)


def project_out(frame, C, rig, st, pj, t, W, H):
    """pull a part of the phone screen out of the phone: it flies to a floating card with a light beam"""
    ph = rig.phone
    t0 = parse_t(pj.get("start", 1.0), rig.dur); t1 = parse_t(pj.get("end", "end"), rig.dur)
    e = min(ease((t - t0) / float(pj.get("in", 0.8))), ease((t1 - t) / float(pj.get("out", 0.5))))
    if e <= 0.001: return frame
    cx, cy, rot, scale, alpha = st
    Mq = C @ T(cx, cy) @ R(rot) @ S(ph.scale * scale) @ T(-ph.pw / 2, -ph.ph / 2)
    i = int(pj.get("screen", 0))
    bx0, by0, bx1, by1 = pj["box"]
    src_pts = []
    for (bx, by) in ((bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)):
        v = Mq @ np.array([ph.sx + bx * ph.sw, ph.sy + by * ph.sh, 1.0])
        src_pts.append(v[:2])
    src = np.array(src_pts, np.float32)
    # the crop itself (hi-res, no highlight), with a white rim and rounded corners
    hw, hh = ph.hw, ph.hh
    crop = ph.hires[i][int(by0 * hh):int(by1 * hh), int(bx0 * hw):int(bx1 * hw)].copy()
    ch, cw = crop.shape[:2]
    rim = max(6, int(min(cw, ch) * 0.025))
    pad = cv2.copyMakeBorder(crop, rim, rim, rim, rim, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    PH, PW = pad.shape[:2]
    mk = Image.new("L", (PW * 2, PH * 2), 0)
    ImageDraw.Draw(mk).rounded_rectangle([0, 0, PW * 2 - 1, PH * 2 - 1], int(min(PW, PH) * 0.09 * 2), fill=255)
    amask = np.array(mk.resize((PW, PH), Image.LANCZOS))
    # destination card (screen space)
    tx, ty = pj.get("to", [0.3, 0.5])
    wpx = float(pj.get("width", 0.36)) * W
    hpx = wpx * PH / PW
    ang = math.radians(float(pj.get("tilt", 0)))
    ca, sa = math.cos(ang), math.sin(ang)
    dst = np.array([[tx * W + ca * x - sa * y, ty * H + sa * x + ca * y]
                    for x, y in ((-wpx / 2, -hpx / 2), (wpx / 2, -hpx / 2), (wpx / 2, hpx / 2), (-wpx / 2, hpx / 2))], np.float32)
    k = out_back(e, 1.0) if e < 1 else 1.0
    cur = src + (dst - src) * k
    # light beam: from the box on the phone to the card
    hull = cv2.convexHull(np.vstack([src, cur]).astype(np.float32)).astype(np.int32)
    beam = np.zeros((H, W), np.float32)
    cv2.fillConvexPoly(beam, hull, 1.0, cv2.LINE_AA)
    beam = cv2.GaussianBlur(beam, (0, 0), 5)
    f = frame.astype(np.float32)
    glow = np.array(hex2rgb(pj.get("color", "#9fd8ff"))[::-1], np.float32)
    a_b = (0.30 * e * beam)[:, :, None]
    f = f * (1 - a_b) + glow * a_b
    # corner rays
    ray = np.zeros((H, W), np.uint8)
    for p0, p1 in zip(src, cur):
        cv2.line(ray, tuple(int(v) for v in p0), tuple(int(v) for v in p1), 255, 2, cv2.LINE_AA)
    a_r = (cv2.GaussianBlur(ray, (0, 0), 1.2).astype(np.float32) / 255.0 * 0.45 * e)[:, :, None]
    f = f * (1 - a_r) + 255.0 * a_r
    frame = np.clip(f, 0, 255).astype(np.uint8)
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [PW, 0], [PW, PH], [0, PH]]), cur.astype(np.float32))
    card = cv2.warpPerspective(pad, M, (W, H), flags=cv2.INTER_LINEAR)
    ca_ = cv2.warpPerspective(amask, M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    sh = cv2.GaussianBlur(ca_, (0, 0), 16)
    sh = cv2.warpAffine(sh, np.float32([[1, 0, 8], [0, 1, 22]]), (W, H))
    f = frame.astype(np.float32)
    f *= (1 - 0.45 * sh * min(1.0, e * 1.5))[:, :, None]
    a3 = (ca_ * min(1.0, e * 2.0))[:, :, None]
    f = f * (1 - a3) + card.astype(np.float32) * a3
    return np.clip(f, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ particles / charts
PALETTE = ["#ff4f8b", "#ffd23f", "#22c55e", "#38bdf8", "#a78bfa", "#fb923c"]


class FX:
    def __init__(self, cfg, W, H, dur):
        self.c = cfg; self.W, self.H = W, H
        self.kind = cfg.get("type", "confetti")
        self.t0 = parse_t(cfg.get("start", 0.5), dur); self.t1 = parse_t(cfg.get("end", "end"), dur)
        rng = np.random.RandomState(int(cfg.get("seed", 7)))
        n = int(cfg.get("count", {"confetti": 90, "coins": 22, "sparkle": 26, "rise": 18}.get(self.kind, 40)))
        span = max(0.5, self.t1 - self.t0)
        area = cfg.get("area", [0, 0, 1, 1])
        self.p = []
        cols = [hex2rgb(c)[::-1] for c in cfg.get("colors", PALETTE)]
        for k in range(n):
            self.p.append(dict(
                t=self.t0 + rng.uniform(0, span * (0.55 if self.kind in ("confetti", "coins") else 1.0)),
                x=rng.uniform(area[0], area[2]) * W, y=rng.uniform(area[1], area[3]) * H,
                vy=rng.uniform(0.28, 0.55) * H, sw=rng.uniform(0.5, 1.5), ph=rng.uniform(0, 6.28),
                sz=rng.uniform(0.7, 1.3), col=cols[k % len(cols)], life=rng.uniform(0.8, 1.6), rot=rng.uniform(0, 360)))

    def draw(self, f, t):
        if not (self.t0 <= t <= self.t1): return
        W, H = self.W, self.H
        u = H / 1080.0
        for p in self.p:
            a = t - p["t"]
            if a < 0: continue
            if self.kind == "confetti":
                y = -30 * u + p["vy"] * a; x = p["x"] + math.sin(a * 2.2 * p["sw"] + p["ph"]) * 50 * u
                if y > H + 30: continue
                ang = math.radians(p["rot"] + a * 240 * p["sw"])
                w_, h_ = 14 * u * p["sz"], 8 * u * p["sz"] * abs(math.cos(a * 5 * p["sw"] + p["ph"])) + 2
                c, s = math.cos(ang), math.sin(ang)
                pts = np.array([[x + c * dx - s * dy, y + s * dx + c * dy] for dx, dy in ((-w_, -h_), (w_, -h_), (w_, h_), (-w_, h_))], np.int32)
                cv2.fillConvexPoly(f, pts, p["col"], cv2.LINE_AA)
            elif self.kind == "coins":
                y = -40 * u + p["vy"] * 1.15 * a; x = p["x"] + math.sin(a * 1.6 + p["ph"]) * 30 * u
                if y > H + 40: continue
                r = 30 * u * p["sz"]; sq = abs(math.cos(a * 3.2 * p["sw"] + p["ph"]))
                ax = (max(3, int(r * sq)), int(r))
                cv2.ellipse(f, (int(x), int(y)), ax, 0, 0, 360, (40, 170, 235), -1, cv2.LINE_AA)
                cv2.ellipse(f, (int(x), int(y)), ax, 0, 0, 360, (20, 120, 190), max(2, int(3 * u)), cv2.LINE_AA)
                if sq > 0.55:
                    sym = self.c.get("symbol", "$")
                    sc_ = 0.9 * u * p["sz"]
                    (tw, th), _ = cv2.getTextSize(sym, cv2.FONT_HERSHEY_SIMPLEX, sc_, max(2, int(3 * u)))
                    cv2.putText(f, sym, (int(x - tw / 2), int(y + th / 2)), cv2.FONT_HERSHEY_SIMPLEX, sc_, (20, 110, 175), max(2, int(3 * u)), cv2.LINE_AA)
            elif self.kind == "sparkle":
                cyc = a % (p["life"] * 1.6)
                if cyc > p["life"]: continue
                k = math.sin(math.pi * cyc / p["life"]) * 26 * u * p["sz"]
                x, y = int(p["x"]), int(p["y"])
                col = (255, 255, 255) if int(p["ph"] * 3) % 2 else (90, 220, 255)
                pts = np.array([[x, y - k], [x + k * .22, y - k * .22], [x + k, y], [x + k * .22, y + k * .22],
                                [x, y + k], [x - k * .22, y + k * .22], [x - k, y], [x - k * .22, y - k * .22]], np.int32)
                cv2.fillConvexPoly(f, pts, col, cv2.LINE_AA)
            elif self.kind == "rise":
                cyc = a % (H / p["vy"] * 0.9)
                y = H + 40 * u - p["vy"] * cyc; x = p["x"] + math.sin(cyc * 1.8 + p["ph"]) * 22 * u
                if y < -40: continue
                s = 26 * u * p["sz"]
                g = (94, 197, 34)
                pts = np.array([[x, y - s], [x + s, y + s * .5], [x + s * .35, y + s * .5], [x + s * .35, y + s * 1.3],
                                [x - s * .35, y + s * 1.3], [x - s * .35, y + s * .5], [x - s, y + s * .5]], np.int32)
                cv2.fillConvexPoly(f, pts, g, cv2.LINE_AA)
                cv2.polylines(f, [pts], True, (20, 110, 20), max(2, int(2 * u)), cv2.LINE_AA)


class Chart:
    """equity curve or candlesticks that draw themselves, on a rounded dark card"""
    def __init__(self, cfg, W, H, dur):
        self.c = cfg; self.W, self.H = W, H
        self.t0 = parse_t(cfg.get("start", 0.5), dur); self.t1 = parse_t(cfg.get("end", "end"), dur)
        self.dur_draw = float(cfg.get("dur", 2.0))
        self.w = int(float(cfg.get("width", 0.4)) * W); self.h = int(float(cfg.get("height", 0.3)) * H)
        rng = np.random.RandomState(int(cfg.get("seed", 5)))
        n = int(cfg.get("points", 34))
        steps = rng.normal(0.35, 1.0, n)
        steps[::7] -= 0.9
        ys = np.cumsum(steps); ys = (ys - ys.min()) / max(1e-6, ys.max() - ys.min())
        self.ys = 0.12 + 0.76 * ys
        self.kind = cfg.get("type", "equity")
        self.col = hex2rgb(cfg.get("color", "#22c55e"))[::-1]
        self.bg = hex2rgb(cfg.get("bg", "#111827"))[::-1]
        if self.kind == "candles":
            o = self.ys[:-1]; c = self.ys[1:]
            self.cd = [(a, b, max(a, b) + abs(rng.normal(0, 0.03)), min(a, b) - abs(rng.normal(0, 0.03))) for a, b in zip(o[::1], c[::1])][:int(cfg.get("candles", 16))]

    def render(self, t):
        w, h = self.w, self.h
        e = clamp((t - self.t0) / 0.45)
        k = max(0.01, out_back(e))
        card = np.zeros((h, w, 3), np.uint8); card[:] = self.bg
        a = np.zeros((h, w), np.uint8)
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], int(min(w, h) * 0.08), fill=255)
        a = np.array(m)
        for gy in (0.25, 0.5, 0.75):
            cv2.line(card, (int(w * 0.05), int(h * gy)), (int(w * 0.95), int(h * gy)), (60, 66, 82), max(1, h // 150), cv2.LINE_AA)
        p = ease((t - self.t0 - 0.3) / self.dur_draw)
        px0, px1, py0, py1 = w * 0.06, w * 0.94, h * 0.1, h * 0.9
        th = max(3, h // 38)
        if self.kind == "equity":
            n = len(self.ys)
            pts = np.array([[px0 + (px1 - px0) * i / (n - 1), py1 - (py1 - py0) * y] for i, y in enumerate(self.ys)])
            upto = p * (n - 1); i = int(upto); fr = upto - i
            seg = list(pts[:i + 1])
            if i + 1 < n: seg.append(pts[i] + (pts[i + 1] - pts[i]) * fr)
            seg = np.array(seg, np.int32)
            if len(seg) >= 2:
                fill = np.vstack([seg, [seg[-1][0], int(py1)], [seg[0][0], int(py1)]]).astype(np.int32)
                ov = card.copy(); cv2.fillPoly(ov, [fill], tuple(int(c * 0.35) for c in self.col))
                card = cv2.addWeighted(card, 0.5, ov, 0.5, 0)
                glow = card.copy(); cv2.polylines(glow, [seg], False, self.col, th * 3, cv2.LINE_AA)
                glow = cv2.GaussianBlur(glow, (0, 0), th * 1.5); card = cv2.addWeighted(card, 0.6, glow, 0.4, 0)
                cv2.polylines(card, [seg], False, self.col, th, cv2.LINE_AA)
                cv2.circle(card, tuple(int(v) for v in seg[-1]), int(th * 1.9), (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(card, tuple(int(v) for v in seg[-1]), int(th * 1.9), self.col, max(2, th // 2), cv2.LINE_AA)
        else:
            n = len(self.cd); cw = (px1 - px0) / n
            for i, (o, c, hi, lo) in enumerate(self.cd):
                q = clamp(p * n - i)
                if q <= 0: continue
                xc = px0 + cw * (i + .5)
                yf = lambda v: py1 - (py1 - py0) * v
                col = (94, 197, 34) if c >= o else (68, 68, 239)
                cv2.line(card, (int(xc), int(yf(hi))), (int(xc), int(yf(lo))), col, max(2, th // 2), cv2.LINE_AA)
                yo, yc = yf(o), yf(o + (c - o) * q)
                cv2.rectangle(card, (int(xc - cw * .3), int(min(yo, yc))), (int(xc + cw * .3), int(max(yo, yc) + 1)), col, -1, cv2.LINE_AA)
        return card, a, k

# ------------------------------------------------------------------ scene
class Scene:
    def __init__(self, cfg, W, H, defaults):
        c = dict(defaults); c.update(cfg)
        self.c = c; self.W, self.H = W, H
        self.dur = c["_dur"]
        kfs = c.get("camera") or [{"t": 0, "zoom": 1.0}, {"t": "end", "zoom": 1.08}]
        self.zmax = max([float(k.get("zoom", 1)) for k in kfs] + [1.0])
        plist = c.get("phones") or ([c["phone"]] if c.get("phone") else [])
        self.rigs = [Rig(p, W, H, self.zmax, self.dur) for p in plist]
        self.phone = self.rigs[0].phone if self.rigs else None
        ppos = plist[0].get("pos", [0.5, 0.5]) if plist else [0.5, 0.5]
        self.kfs = []
        for k in kfs:
            look = k.get("look")
            if look == "phone":
                x, y = ppos[0] + float(k.get("dx", 0)), ppos[1] + float(k.get("dy", 0))
            else:
                x, y = float(k.get("x", 0.5)), float(k.get("y", 0.5))
            self.kfs.append((parse_t(k.get("t"), self.dur), float(k.get("zoom", 1.0)), x * W, y * H))
        self.kfs.sort()
        bg = read_image(c["background"])
        ih, iw = bg.shape[:2]
        cover = max(W / iw, H / ih)
        over = min(self.zmax, 2.0)
        sc = cover * over
        sc = min(sc, 1.0) if sc < 1 else sc
        self.bg = cv2.resize(bg, (int(iw * sc), int(ih * sc)), interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC)
        self.bg_to_world = cover / sc
        self.bgw, self.bgh = self.bg.shape[1] * self.bg_to_world, self.bg.shape[0] * self.bg_to_world
        pl = []
        for p_ in c.get("props", []):
            if os.path.exists(p_["image"]): pl.append(p_)
            else: print("NOTE: prop image not found (%s) - skipped." % p_["image"])
        self.props = [Prop(p_, W, H, self.zmax, self.dur) for p_ in pl]
        self.fx = [FX(f, W, H, self.dur) for f in c.get("fx", [])]
        self.charts = [Chart(ch, W, H, self.dur) for ch in c.get("charts", [])]
        self.font_path = c.get("font")
        self.caps = [self.make_caption(cp) for cp in c.get("captions", [])]

    # ---- captions
    def _render_text(self, cp, text):
        style = cp.get("style", self.c.get("caption_style", "classic"))
        font = cp.get("font", self.c.get("font"))
        size = int(cp.get("size", 0.075) * self.H)
        if style == "classic" or not cp.get("box", True):
            return self._render_classic(cp, text, size, font)
        return self._render_modern(cp, text, size, font, style)

    def _render_classic(self, cp, text, size, font):
        text = text.replace("{", "").replace("}", "")
        f = find_font(size, path=font)
        lines = text.split("\n")
        dm = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        ws = [dm.textlength(l, font=f) for l in lines]
        pad = int(size * 0.35)
        w = int(max(ws) + 2 * pad); h = int(len(lines) * size * 1.25 + 2 * pad)
        w = max(w, int(cp.get("min_width", 0) * self.W))
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if cp.get("box", True):
            d.rounded_rectangle([0, 0, w - 1, h - 1], int(size * 0.5), fill=hex2rgb(cp.get("bg", "#ff4f8b")) + (245,),
                                outline=(255, 255, 255, 255), width=max(3, size // 14))
        col = hex2rgb(cp.get("color", "#ffffff"))
        for k, l in enumerate(lines):
            d.text(((w - ws[k]) / 2, pad + k * size * 1.25), l, font=f, fill=col + (255,),
                   stroke_width=max(2, size // 16), stroke_fill=hex2rgb(cp.get("stroke", "#2b2d42")) + (255,))
        a = np.array(im)
        return cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2BGR), a[:, :, 3]

    def _render_modern(self, cp, text, size, font, style):
        """glass: dark frosted panel + coloured edge, glow and accent bar; solid: flat colour tile.
        Words inside {braces} are drawn in the accent colour."""
        K = 2
        accent = hex2rgb(cp.get("bg", cp.get("accent", "#38bdf8")))
        light = tuple(int(c + (255 - c) * 0.45) for c in accent)
        sz = size * K
        f = find_font(sz, path=font)
        lines = text.split("\n")
        dm = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        runs_per_line, widths = [], []
        for l in lines:
            runs = []; inside = False; cur = ""
            for ch in l:
                if ch == "{": 
                    if cur: runs.append((cur, inside))
                    cur = ""; inside = True
                elif ch == "}":
                    if cur: runs.append((cur, inside))
                    cur = ""; inside = False
                else: cur += ch
            if cur: runs.append((cur, inside))
            runs_per_line.append(runs)
            widths.append(sum(dm.textlength(t, font=f) for t, _ in runs))
        padx, pady = int(sz * 0.62), int(sz * 0.42)
        bar = int(sz * 0.16) if style == "glass" else 0
        lh = int(sz * 1.22)
        pw = int(max(widths) + 2 * padx + (bar + sz * 0.25 if bar else 0))
        pw = max(pw, int(cp.get("min_width", 0) * self.W * K))
        ph = int(len(lines) * lh + 2 * pady - (lh - sz) * 0.4)
        m = int(sz * 0.9)                                     # room for glow + shadow
        im = Image.new("RGBA", (pw + 2 * m, ph + 2 * m), (0, 0, 0, 0))
        rad = int(min(ph * 0.34, sz * 0.7))
        # shadow
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([m, m + int(sz * 0.14), m + pw, m + ph + int(sz * 0.14)], rad, fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(sz * 0.18)))
        if style == "glass":
            gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(gl).rounded_rectangle([m, m, m + pw, m + ph], rad, outline=accent + (255,), width=int(sz * 0.10))
            im = Image.alpha_composite(im, gl.filter(ImageFilter.GaussianBlur(sz * 0.20)))
        panel = Image.new("RGBA", im.size, (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        if style == "glass":
            pd.rounded_rectangle([m, m, m + pw, m + ph], rad, fill=(12, 18, 36, 238))
            # soft top sheen
            sheen = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(sheen).rounded_rectangle([m + 3, m + 3, m + pw - 3, m + ph * 0.5], rad, fill=(255, 255, 255, 22))
            panel = Image.alpha_composite(panel, sheen)
            pd = ImageDraw.Draw(panel)
            pd.rounded_rectangle([m, m, m + pw, m + ph], rad, outline=accent + (255,), width=max(3, int(sz * 0.055)))
            pd.rounded_rectangle([m + int(sz * 0.30), m + int(ph * 0.2), m + int(sz * 0.30) + bar, m + int(ph * 0.8)], bar // 2, fill=accent + (255,))
        else:
            pd.rounded_rectangle([m, m, m + pw, m + ph], rad, fill=accent + (255,))
            pd.rounded_rectangle([m, m, m + pw, m + ph], rad, outline=light + (255,), width=max(3, int(sz * 0.04)))
        im = Image.alpha_composite(im, panel)
        d = ImageDraw.Draw(im)
        tx0 = m + padx + (bar + sz * 0.25 if bar else 0)
        txt_col = hex2rgb(cp.get("color", "#ffffff"))
        for k, runs in enumerate(runs_per_line):
            x = tx0 + (pw - 2 * padx - (bar + sz * 0.25 if bar else 0) - widths[k]) / 2
            y = m + pady + k * lh - (lh - sz) * 0.15
            for t, hi in runs:
                col = (light if style == "glass" else (255, 255, 255)) if hi else txt_col
                if style == "solid" and hi: col = (30, 30, 30)
                d.text((x, y), t, font=f, fill=col + (255,))
                x += dm.textlength(t, font=f)
        im = im.resize((im.width // K, im.height // K), Image.LANCZOS)
        a = np.array(im)
        return cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2BGR), a[:, :, 3]

    def make_caption(self, cp):
        W, H = self.W, self.H
        base = dict(pos=cp.get("pos", [0.5, 0.12]), t0=parse_t(cp.get("start", 0.5), self.dur), t1=parse_t(cp.get("end", "end"), self.dur),
                    anim=cp.get("anim", "pop"))
        if cp.get("image"):
            if os.path.exists(cp["image"]):
                im = cv2.imdecode(np.fromfile(cp["image"], dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                if im.ndim == 2: im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
                if im.shape[2] == 3: im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
                hh = max(20, int(float(cp.get("height", 0.15)) * H))
                ww = int(im.shape[1] * hh / im.shape[0])
                im = cv2.resize(im, (ww, hh), interpolation=cv2.INTER_AREA)
                return dict(base, rgb=np.ascontiguousarray(im[:, :, :3]), a=np.ascontiguousarray(im[:, :, 3]))
            print("NOTE: badge image not found (%s) - using text instead." % cp["image"])
            cp = dict(cp, text=cp.get("fallback_text", "Get it on Google Play"), size=cp.get("size", 0.06), bg="#2b2d42")
        if cp.get("counter"):
            ct = cp["counter"]
            return dict(base, counter=ct, cp=cp, cache={}, rgb=None, a=None)
        rgb, a = self._render_text(cp, cp["text"])
        return dict(base, rgb=rgb, a=a)

    def cap_image(self, cp, t):
        if cp.get("counter"):
            ct = cp["counter"]
            q = ease((t - cp["t0"] - 0.2) / float(ct.get("dur", 1.4)))
            v = float(ct.get("from", 0)) + (float(ct["to"]) - float(ct.get("from", 0))) * q
            dec = int(ct.get("decimals", 0))
            txt = "%s%s%s" % (ct.get("prefix", ""), ("%.*f" % (dec, v)), ct.get("suffix", ""))
            if cp["cp"].get("text"): txt = cp["cp"]["text"].replace("{n}", "{" + txt + "}")
            if txt not in cp["cache"]:
                cp["cache"][txt] = self._render_text(cp["cp"], txt)
            return cp["cache"][txt]
        return cp["rgb"], cp["a"]

    def draw_popouts(self, frame, rig, Mp, t):
        """a section of the screen is projected out of the phone: light beams + a floating card"""
        W, H = self.W, self.H
        ph = rig.phone
        for po in rig.pc["popouts"]:
            t0 = parse_t(po.get("start", 1.0), self.dur); t1 = parse_t(po.get("end", "end"), self.dur)
            if not (t0 <= t <= t1): continue
            i = int(po.get("screen", 0))
            cur, e = ph.current(t - float(rig.pc.get("enter_at", 0.4)), rig.schedule_local())
            if cur != i or e > 0: continue
            p = ease((t - t0) / 0.8) * ease((t1 - t) / 0.5)
            if p <= 0.002: continue
            bx0, by0, bx1, by1 = po["box"]
            pts = np.array([[ph.sx + bx0 * ph.sw, ph.sy + by0 * ph.sh], [ph.sx + bx1 * ph.sw, ph.sy + by0 * ph.sh],
                            [ph.sx + bx1 * ph.sw, ph.sy + by1 * ph.sh], [ph.sx + bx0 * ph.sw, ph.sy + by1 * ph.sh]], np.float64)
            src = (Mp[:2, :2] @ pts.T).T + Mp[:2, 2]
            crop = ph.hires[i][int(by0 * ph.hh):int(by1 * ph.hh), int(bx0 * ph.hw):int(bx1 * ph.hw)]
            cw = max(60, int(float(po.get("width", 0.34)) * W)); ch = max(30, int(cw * crop.shape[0] / crop.shape[1]))
            img = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_AREA if crop.shape[1] > cw else cv2.INTER_CUBIC)
            rad = int(min(cw, ch) * 0.07); bd = max(5, int(cw * 0.009))
            ring = Image.new("L", (cw * 2, ch * 2), 0); ImageDraw.Draw(ring).rounded_rectangle([0, 0, cw * 2 - 1, ch * 2 - 1], rad * 2, fill=255)
            outer = np.array(ring.resize((cw, ch), Image.LANCZOS))
            inn = Image.new("L", (cw * 2, ch * 2), 0)
            ImageDraw.Draw(inn).rounded_rectangle([bd * 2, bd * 2, cw * 2 - 1 - bd * 2, ch * 2 - 1 - bd * 2], max(2, rad * 2 - bd * 2), fill=255)
            innm = np.array(inn.resize((cw, ch), Image.LANCZOS)).astype(np.float32)[:, :, None] / 255.0
            bcol = np.array(hex2rgb(po.get("border", "#ffffff"))[::-1], np.float32)
            card = (img.astype(np.float32) * innm + bcol * (1 - innm)).astype(np.uint8)
            px, py = po.get("pos", [0.3, 0.5])
            x0, y0 = px * W - cw / 2, py * H - ch / 2
            D = np.array([[x0, y0], [x0 + cw, y0], [x0 + cw, y0 + ch], [x0, y0 + ch]], np.float64)
            q = out_cubic(p)
            Q = src + (D - src) * q
            beam = frame.copy()
            for k in range(4):
                cv2.fillConvexPoly(beam, np.int32([src[k], src[(k + 1) % 4], Q[(k + 1) % 4], Q[k]]), (255, 255, 255), cv2.LINE_AA)
            frame = cv2.addWeighted(frame, 1 - 0.20 * p, beam, 0.20 * p, 0)
            edge = frame.copy()
            for k in range(4):
                cv2.line(edge, tuple(int(v) for v in src[k]), tuple(int(v) for v in Q[k]), (255, 255, 255), 3, cv2.LINE_AA)
            frame = cv2.addWeighted(frame, 1 - 0.40 * p, edge, 0.40 * p, 0)
            M3 = cv2.getPerspectiveTransform(np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]]), np.float32(Q))
            rgb = cv2.warpPerspective(card, M3, (W, H), flags=cv2.INTER_LINEAR)
            al = cv2.warpPerspective(outer, M3, (W, H), flags=cv2.INTER_LINEAR)
            shd = cv2.GaussianBlur(al, (0, 0), 16 * H / 1080.0)
            shd = cv2.warpAffine(shd, np.float32([[1, 0, 8], [0, 1, 22]]), (W, H))
            f = frame.astype(np.float32) * (1 - 0.45 * (shd.astype(np.float32) / 255.0))[:, :, None]
            af = (al.astype(np.float32) / 255.0)[:, :, None]
            frame = np.clip(f * (1 - af) + rgb.astype(np.float32) * af, 0, 255).astype(np.uint8)
        return frame

    def camera(self, t):
        k = self.kfs
        if t <= k[0][0]: z, x, y = k[0][1:]
        elif t >= k[-1][0]: z, x, y = k[-1][1:]
        else:
            for a, b in zip(k, k[1:]):
                if a[0] <= t <= b[0]:
                    e = ease((t - a[0]) / max(1e-6, b[0] - a[0]))
                    z, x, y = [a[j] + (b[j] - a[j]) * e for j in (1, 2, 3)]
                    break
        hw, hh = self.W / (2 * z), self.H / (2 * z)
        x = clamp(x, hw, self.W - hw); y = clamp(y, hh, self.H - hh)
        return T(self.W / 2, self.H / 2) @ S(z) @ T(-x, -y)

    def render(self, t):
        W, H = self.W, self.H
        C = self.camera(t)
        off = T((W - self.bgw) / 2, (H - self.bgh) / 2)
        M = C @ off @ S(self.bg_to_world)
        frame = cv2.warpAffine(self.bg, M[:2], (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        for pr in self.props:
            if pr.layer == "back":
                st = pr.state(t)
                if st: frame = blend_layer(frame, C, pr.rgb, pr.a, *st, pr.scale, pr.c.get("shadow", True))
        for ch in self.charts:
            if ch.t0 <= t <= ch.t1:
                card, ca, k = ch.render(t)
                px, py = ch.c.get("pos", [0.5, 0.5])
                h_, w_ = card.shape[:2]
                Mc = T(px * W, py * H) @ S(k) @ T(-w_ / 2, -h_ / 2)
                rgb = cv2.warpAffine(card, Mc[:2], (W, H), flags=cv2.INTER_LINEAR)
                a = cv2.warpAffine(ca, Mc[:2], (W, H), flags=cv2.INTER_LINEAR).astype(np.float32)[:, :, None] / 255.0
                frame = np.clip(frame.astype(np.float32) * (1 - a) + rgb.astype(np.float32) * a, 0, 255).astype(np.uint8)
        pops = []
        drawn = []
        for rig in self.rigs:
            st = rig.state(t)
            if st is None: continue
            cx, cy, rot, scale, alpha = st
            pimg, pa = rig.phone.frame(t - float(rig.pc.get("enter_at", 0.4)), rig.schedule_local(), self.dur, t)
            frame = blend_layer(frame, C, pimg, pa, cx, cy, rot, scale, alpha, rig.phone.scale, True)
            drawn.append((rig, st))
            if rig.pc.get("popouts"):
                Mp = C @ T(cx, cy) @ R(rot) @ S(rig.phone.scale * scale) @ T(-pimg.shape[1] / 2, -pimg.shape[0] / 2)
                pops.append((rig, Mp))
        for pr in self.props:
            if pr.layer != "back":
                st = pr.state(t)
                if st: frame = blend_layer(frame, C, pr.rgb, pr.a, *st, pr.scale, pr.c.get("shadow", True))
        for rig, Mp in pops:
            frame = self.draw_popouts(frame, rig, Mp, t)
        for rig, st in drawn:
            for pj in rig.pc.get("projections", []):
                frame = project_out(frame, C, rig, st, pj, t, self.W, self.H)
        for fx in self.fx:
            fx.draw(frame, t)
        for cp in self.caps:
            if cp["t0"] <= t <= cp["t1"]:
                rgb_, a_ = self.cap_image(cp, t)
                e = clamp((t - cp["t0"]) / 0.45)
                h, w = rgb_.shape[:2]
                px, py = cp["pos"][0] * W, cp["pos"][1] * H
                k = 1.0; an = cp["anim"]
                if an == "pop": k = max(0.01, out_back(e))
                elif an == "slide_left": px += (1 - out_back(e, 1.1)) * W * 0.7
                elif an == "slide_right": px -= (1 - out_back(e, 1.1)) * W * 0.7
                elif an == "slide_up": py += (1 - out_back(e, 1.1)) * H * 0.5
                elif an == "drop": py -= (1 - out_bounce(e)) * H * 0.7
                Mc = T(px, py) @ S(k) @ T(-w / 2, -h / 2)
                rgb = cv2.warpAffine(rgb_, Mc[:2], (W, H), flags=cv2.INTER_LINEAR)
                a = cv2.warpAffine(a_, Mc[:2], (W, H), flags=cv2.INTER_LINEAR).astype(np.float32)[:, :, None] / 255.0
                frame = np.clip(frame.astype(np.float32) * (1 - a) + rgb.astype(np.float32) * a, 0, 255).astype(np.uint8)
        return frame


def transition(prev, fr, al, kind):
    """al 0..1 (eased): old frame prev -> new frame fr"""
    H, W = fr.shape[:2]
    if kind == "slide_left":
        off = int(round(al * W)); out = np.empty_like(fr)
        out[:, :W - off] = prev[:, off:]; out[:, W - off:] = fr[:, :off]; return out
    if kind == "slide_up":
        off = int(round(al * H)); out = np.empty_like(fr)
        out[:H - off] = prev[off:]; out[H - off:] = fr[:off]; return out
    if kind == "zoom":
        s = 1.0 + 0.35 * (1 - al)
        Mz = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        z = cv2.warpAffine(fr, Mz, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return cv2.addWeighted(prev, 1 - al, z, al, 0)
    if kind == "wipe":
        xs = np.arange(W, dtype=np.float32)[None, :, None]
        edge = al * (W * 1.2) - W * 0.1
        m = np.clip((edge - xs) / (W * 0.1) + 0.5, 0, 1)
        return (prev * (1 - m) + fr * m).astype(np.uint8)
    return cv2.addWeighted(prev, 1 - al, fr, al, 0)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("-o", "--output", default="ad.mp4")
    ap.add_argument("--size"); ap.add_argument("--fps", type=int)
    ap.add_argument("--scene", type=int)
    a = ap.parse_args()
    spec = json.load(open(a.json, encoding="utf-8-sig"))
    base = os.path.dirname(os.path.abspath(a.json))
    W, H = (int(v) for v in a.size.lower().split("x")) if a.size else spec.get("size", [1920, 1080])
    W -= W % 2; H -= H % 2
    fps = a.fps or spec.get("fps", 30)
    defaults = spec.get("defaults", {})

    def fix(p): return p if os.path.isabs(p) else os.path.join(base, p)
    if defaults.get("font"): defaults["font"] = fix(defaults["font"])
    scenes = spec["scenes"]
    if a.scene: scenes = [scenes[a.scene - 1]]
    tmp = tempfile.mkdtemp(prefix="appad_")
    parts = []
    for n, s in enumerate(scenes):
        s["background"] = fix(s["background"])
        plist = s.get("phones") or ([s["phone"]] if s.get("phone") else [])
        for ph in plist:
            sc = []
            for x in ph["screens"]:
                if isinstance(x, dict): x["img"] = fix(x["img"]); sc.append(x)
                else: sc.append(fix(x))
            ph["screens"] = sc
        for cp in s.get("captions", []):
            if cp.get("image"): cp["image"] = fix(cp["image"])
        for pr in s.get("props", []):
            pr["image"] = fix(pr["image"])
        if s.get("font"): s["font"] = fix(s["font"])
        tail = float(s.get("tail", 0.5))
        if s.get("audio"):
            s["audio"] = fix(s["audio"])
            dur = float(s["duration"]) if s.get("duration") else audio_duration(s["audio"]) + tail
        else:
            dur = float(s.get("duration", 4))
        s["_dur"] = dur
        wav = os.path.join(tmp, "a%03d.wav" % n)
        if s.get("audio"):
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", s["audio"], "-af", "apad", "-t", "%.3f" % dur, "-ar", "44100", "-ac", "2", wav]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "%.3f" % dur, wav]
        subprocess.run(cmd, check=True); parts.append(wav)
    lst = os.path.join(tmp, "l.txt")
    open(lst, "w").write("".join("file '%s'\n" % p.replace("\\", "/") for p in parts))
    full = os.path.join(tmp, "audio.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", full], check=True)
    music = spec.get("music")
    if music and not os.path.exists(fix(music)):
        print("NOTE: music file not found (%s) - making the ad without background music." % fix(music))
        music = None
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-i", full]
    if music:
        cmd += ["-stream_loop", "-1", "-i", fix(music), "-filter_complex",
                "[2:a]volume=%.2f[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]" % float(spec.get("music_volume", 0.12)),
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", a.output]
    od = os.path.dirname(os.path.abspath(a.output)); os.makedirs(od, exist_ok=True)
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prev = None
    total = 0
    for n, cfg in enumerate(scenes):
        sc = Scene(cfg, W, H, defaults)
        frames = int(round(sc.dur * fps))
        print("Scene %d | %.1fs | phones=%d | props=%d" % (n + 1, sc.dur, len(sc.rigs), len(sc.props)), flush=True)
        fade = float(cfg.get("transition", defaults.get("transition", 0.35)))
        tkind = cfg.get("transition_type", defaults.get("transition_type", "fade"))
        for f in range(frames):
            t = f / fps
            fr = sc.render(t)
            if prev is not None and t < fade:
                fr = transition(prev, fr, ease(t / fade), tkind)
            enc.stdin.write(fr.tobytes())
            if f == frames - 1: prev = fr
        total += frames
    enc.stdin.close(); enc.wait()
    print("Done: %s (%d frames, %.1f s)" % (a.output, total, total / fps))

if __name__ == "__main__":
    main()
