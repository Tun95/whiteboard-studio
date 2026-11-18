#!/usr/bin/env python3
"""
manhwa_panels.py  -  "Manhwa recap" style video maker (blur background + moving panel).

Every scene = one panel image (+ one voice file).  The same panel is also used, enlarged and
blurred, as the background.  Both the background and the panel get motion:

  panel motion  : zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down, scroll (long panels), none, auto
  entrances     : swipe_left, swipe_right, swipe_up, swipe_down, drop (falls + bounces), zoom, fade, none
  background    : follows the panel motion (slower), or counter / none; entrance moves with the panel

Needs only: Python, numpy, opencv-python, ffmpeg + ffprobe on PATH (same as whiteboard-animator).

Quick use (folder of panels + folder of voices, matched by sorted order):
  python manhwa_panels.py --panels panels --audio audio -o out.mp4
Full control:
  python manhwa_panels.py scenes.json -o out.mp4
Test one scene only:  add  --scene 3
"""
import argparse, json, math, os, subprocess, sys, tempfile, glob

import cv2
import numpy as np

# ----------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def ease(t):                      # smooth in/out
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)

def out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3

def out_back(t, s=1.4):
    t = clamp(t) - 1
    return 1 + t * t * ((s + 1) * t + s)

def out_bounce(t):
    t = clamp(t)
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375

# ----------------------------------------------------------------------------- helpers
AUTO_MOTION = ["zoom_in", "zoom_out", "pan_left", "zoom_in", "pan_right", "zoom_out"]
AUTO_ENTER = ["swipe_left", "drop", "swipe_up", "swipe_right", "zoom", "swipe_down", "fade"]

DEFAULTS = dict(
    motion="auto", enter="auto", enter_time=0.7, fg_delay=0.10,
    zoom=0.16,            # zoom amount for zoom_in / zoom_out (0.16 = 16 %)
    fit=0.88,             # panel may fill this much of the canvas (normal panels)
    tall_ratio=1.9,       # height/width above this = "long panel" -> scroll
    tall_width=None,      # width of a long panel as a fraction of canvas width (auto)
    focus=None,           # [x, y] 0-1 inside the panel: zoom toward this point
    bg="blur", bg_blur=40, bg_dim=0.55, bg_motion="follow", bg_zoom=0.08,
    border=0, shadow=0.5, tail=0.4, duration=None,
)

def read_image(path):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit("Cannot read image: " + path)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:       # put transparent parts on white
        a = img[:, :, 3:4].astype(np.float32) / 255
        img = (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return img

def audio_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit("Cannot read audio: " + path)

def warp(src, M, size, dst=None, transparent=False):
    return cv2.warpAffine(src, M, size, dst=dst, flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_TRANSPARENT if transparent else cv2.BORDER_CONSTANT,
                          borderValue=0)

# ----------------------------------------------------------------------------- scene
class Scene:
    def __init__(self, cfg, index, W, H):
        self.W, self.H = W, H
        c = dict(DEFAULTS)
        c.update(cfg)
        self.c = c
        self.index = index
        img = read_image(c["image"])
        if c["border"]:
            b = int(c["border"])
            img = cv2.copyMakeBorder(img, b, b, b, b, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        self.ih, self.iw = img.shape[:2]
        portrait = H > W
        self.tall = (self.ih / self.iw) > float(c["tall_ratio"]) * (1.0 if not portrait else 1.6)
        motion = c["motion"]
        enter = c["enter"]
        if motion == "auto":
            motion = "scroll" if self.tall else AUTO_MOTION[index % len(AUTO_MOTION)]
        if motion.startswith("scroll") and not self.tall and motion == "scroll":
            motion = "zoom_in"
        if enter == "auto":
            enter = AUTO_ENTER[index % len(AUTO_ENTER)]
        self.motion, self.enter = motion, enter
        self.dur = 0.0

        # ---- foreground placement
        z = float(c["zoom"])
        self.kmax = 1 + z + 0.1
        if self.tall:
            tw = c["tall_width"] or (0.94 if portrait else 0.46)
            self.s0 = tw * W / self.iw
            pre = self.s0
        else:
            self.s0 = min(W * c["fit"] / self.iw, H * c["fit"] / self.ih)
            pre = self.s0 * self.kmax * 1.15
        pre = min(pre, 1.0) if pre < 1 else 1.0
        if pre < 1:
            img = cv2.resize(img, (max(1, int(self.iw * pre)), max(1, int(self.ih * pre))),
                             interpolation=cv2.INTER_AREA)
        self.pre = pre
        self.fg = img
        self.fh, self.fw = img.shape[:2]
        self.mask = np.full((self.fh, self.fw), 255, np.uint8)

        # ---- background source (tiny & blurred, enlarged by the warp)
        r = 320.0 / max(self.iw, self.ih) if not self.tall else 320.0 / self.iw
        r = min(r, 1.0)
        small = cv2.resize(read_image(c["image"]), (max(2, int(self.iw * r)), max(2, int(self.ih * r))),
                           interpolation=cv2.INTER_AREA)
        cover = max(W / self.iw, H / self.ih)
        sigma = max(0.5, float(c["bg_blur"]) * r / cover)
        small = cv2.GaussianBlur(small, (0, 0), sigma)
        small = (small.astype(np.float32) * float(c["bg_dim"])).astype(np.uint8)
        self.bg = small
        self.bgr = r
        self.bgcover = cover

    # --------------------------------------------------------------- motion curves
    def fg_transform(self, t):
        W, H, c = self.W, self.H, self.c
        p = clamp(t / self.dur)
        e = ease(p)
        z = float(c["zoom"])
        m = self.motion
        a = self.s0
        sx = sy = 0.0
        k = 1.0
        if self.tall:
            hold = 0.5 if self.dur > 3.5 else 0.0
            q = clamp((t - hold) / max(0.1, self.dur - 2 * hold))
            q = 0.15 * ease(q) + 0.85 * q
            if m == "scroll_up":
                q = 1 - q
            total = self.ih * self.s0 - H
            off = q * total if total > 0 else 0
            ty = -off if total > 0 else (H - self.ih * self.s0) / 2
            tx = (W - self.iw * self.s0) / 2
            # source pixels of fg are pre-scaled by self.pre
            A = self.s0 / self.pre
            return np.float32([[A, 0, tx], [0, A, ty]]), self.s0, tx, ty
        if m == "zoom_in":
            k = 1 + z * e
        elif m == "zoom_out":
            k = 1 + z * (1 - e)
        elif m in ("pan_left", "pan_right", "pan_up", "pan_down"):
            k = 1 + 0.6 * z
            d = 0.04 * W if m in ("pan_left", "pan_right") else 0.04 * H
            v = (1 - 2 * e) * d                    # +d -> -d
            if m == "pan_left":
                sx = v                            # picture drifts to the left
            elif m == "pan_right":
                sx = -v
            elif m == "pan_up":
                sy = v
            else:
                sy = -v
        a = self.s0 * k
        fx, fy = (c["focus"] or [0.5, 0.5])
        fxp, fyp = fx * self.iw, fy * self.ih
        qx = W / 2 + (fxp - self.iw / 2) * self.s0
        qy = H / 2 + (fyp - self.ih / 2) * self.s0
        tx = qx - fxp * a + sx
        ty = qy - fyp * a + sy
        A = a / self.pre
        return np.float32([[A, 0, tx], [0, A, ty]]), a, tx, ty

    def bg_transform(self, t):
        W, H, c = self.W, self.H, self.c
        p = clamp(t / self.dur)
        e = ease(p)
        bz = float(c["bg_zoom"])
        bm = c["bg_motion"]
        base = self.bgcover
        sh, sw = self.bg.shape[:2]
        sx = sy = 0.0
        if self.tall:
            a = base * 1.04
            hold = 0.5 if self.dur > 3.5 else 0.0
            q = clamp((t - hold) / max(0.1, self.dur - 2 * hold))
            q = 0.15 * ease(q) + 0.85 * q
            if self.motion == "scroll_up":
                q = 1 - q
            total = self.ih * a - H
            if bm == "none":
                q = 0.5
            elif bm == "counter":
                q = 1 - q
            off = q * total if total > 0 else 0
            ty = -off if total > 0 else (H - self.ih * a) / 2
            tx = (W - self.iw * a) / 2
        else:
            direction = 0.0
            if self.motion == "zoom_in":
                direction = e
            elif self.motion == "zoom_out":
                direction = 1 - e
            elif self.motion.startswith("pan"):
                direction = 0.5
                v = (1 - 2 * e) * 0.02
                sx = {"pan_left": v * W, "pan_right": -v * W}.get(self.motion, 0.0)
                sy = {"pan_up": v * H, "pan_down": -v * H}.get(self.motion, 0.0)
            else:
                direction = 0.5
            if bm == "none":
                direction, sx, sy = 0.5, 0.0, 0.0
            elif bm == "counter":
                direction, sx, sy = 1 - direction, -sx, -sy
            a = base * (1.12 + bz * direction)
            tx = W / 2 - self.iw * a / 2 + sx
            ty = H / 2 - self.ih * a / 2 + sy
        A = a * 1.0 / self.bgr
        return np.float32([[A, 0, tx], [0, A, ty]])

# ----------------------------------------------------------------------------- entrance
def entrance_offsets(kind, e_bg, e_fg, W, H):
    """returns (bg_dx, bg_dy, bg_alpha, fg_dx, fg_dy, fg_scale, fg_alpha)"""
    if kind == "swipe_left":
        return ((1 - out_cubic(e_bg)) * W, 0, 1, (1 - out_cubic(e_fg)) * W * 1.1, 0, 1, 1)
    if kind == "swipe_right":
        return (-(1 - out_cubic(e_bg)) * W, 0, 1, -(1 - out_cubic(e_fg)) * W * 1.1, 0, 1, 1)
    if kind == "swipe_up":
        return (0, (1 - out_cubic(e_bg)) * H, 1, 0, (1 - out_cubic(e_fg)) * H * 1.1, 1, 1)
    if kind == "swipe_down":
        return (0, -(1 - out_cubic(e_bg)) * H, 1, 0, -(1 - out_cubic(e_fg)) * H * 1.1, 1, 1)
    if kind == "drop":
        return (0, -(1 - out_cubic(e_bg)) * H, 1, 0, -(1 - out_bounce(e_fg)) * H * 1.1, 1, 1)
    if kind == "zoom":
        return (0, 0, clamp(e_bg), 0, 0, 0.55 + 0.45 * out_back(e_fg), clamp(e_fg * 2))
    if kind == "fade":
        return (0, 0, clamp(e_bg), 0, 0, 1, clamp(e_fg))
    return (0, 0, 1, 0, 0, 1, 1)

def shift(M, dx, dy):
    M = M.copy()
    M[0, 2] += dx
    M[1, 2] += dy
    return M

def render_frame(sc, t, prev):
    W, H, c = sc.W, sc.H, sc.c
    et = max(0.05, float(c["enter_time"]))
    e_bg = clamp(t / et)
    e_fg = clamp((t - float(c["fg_delay"])) / et)
    bdx, bdy, ba, fdx, fdy, fs, fa = entrance_offsets(sc.enter, e_bg, e_fg, W, H)

    cur = prev.copy()
    Mb = shift(sc.bg_transform(t), bdx, bdy)
    if ba >= 0.999:
        warp(sc.bg, Mb, (W, H), dst=cur, transparent=True)
    else:
        tmp = cur.copy()
        warp(sc.bg, Mb, (W, H), dst=tmp, transparent=True)
        cur = cv2.addWeighted(cur, 1 - ba, tmp, ba, 0)

    if fa <= 0.001:
        return cur
    Mf, a, tx, ty = sc.fg_transform(t)
    if fs != 1:                                   # scale about the canvas centre (zoom entrance)
        Mf = Mf.copy()
        Mf[0, :] = Mf[0, :] * fs + (1 - fs) * (W / 2) * np.float32([0, 0, 1])
        Mf[1, :] = Mf[1, :] * fs + (1 - fs) * (H / 2) * np.float32([0, 0, 1])
    Mf = shift(Mf, fdx, fdy)
    fgw = np.zeros((H, W, 3), np.uint8)
    warp(sc.fg, Mf, (W, H), dst=fgw)
    m = warp(sc.mask, Mf, (W, H)).astype(np.float32) / 255.0
    m = (m * fa)[:, :, None]
    cf = cur.astype(np.float32)
    if c["shadow"] and sc.c["shadow"] > 0:
        ds = 4
        Ms = Mf.copy() / ds
        Ms[0, 2] = Mf[0, 2] / ds
        Ms[1, 2] = (Mf[1, 2] + 14) / ds
        ms = warp(sc.mask, Ms, (W // ds, H // ds)).astype(np.float32) / 255.0
        ms = cv2.GaussianBlur(ms, (0, 0), 6)
        sh = cv2.resize(ms, (W, H), interpolation=cv2.INTER_LINEAR)[:, :, None] * float(c["shadow"]) * fa
        cf *= (1 - sh)
    cf = cf * (1 - m) + fgw.astype(np.float32) * m
    return np.clip(cf, 0, 255).astype(np.uint8)

# ----------------------------------------------------------------------------- main
def load_scenes(args):
    W, H = args.size
    cfgs, glob_defaults = [], {}
    if args.json:
        spec = json.load(open(args.json, encoding="utf-8-sig"))
        base = os.path.dirname(os.path.abspath(args.json))
        if "size" in spec and not args.size_given:
            W, H = spec["size"]
        if "fps" in spec and not args.fps_given:
            args.fps = spec["fps"]
        glob_defaults = spec.get("defaults", {})
        for s in spec["scenes"]:
            s = dict(s)
            for k in ("image", "audio"):
                if s.get(k) and not os.path.isabs(s[k]):
                    s[k] = os.path.join(base, s[k])
            cfgs.append(s)
    else:
        ims = sorted(p for ext in ("png", "jpg", "jpeg", "webp") for p in glob.glob(os.path.join(args.panels, "*." + ext)))
        aus = []
        if args.audio:
            aus = sorted(p for ext in ("wav", "mp3", "m4a") for p in glob.glob(os.path.join(args.audio, "*." + ext)))
            if len(aus) != len(ims):
                raise SystemExit("Found %d panels but %d audio files - counts must match." % (len(ims), len(aus)))
        for i, p in enumerate(ims):
            d = {"image": p}
            if aus:
                d["audio"] = aus[i]
            cfgs.append(d)
    scenes = []
    for i, cfg in enumerate(cfgs):
        merged = dict(glob_defaults)
        merged.update(cfg)
        if args.duration and "duration" not in merged and "audio" not in merged:
            merged["duration"] = args.duration
        scenes.append((i, merged))
    return W, H, scenes

def main():
    ap = argparse.ArgumentParser(description="Manhwa-recap style panel video (blur bg + zoom/swipe/drop/scroll)")
    ap.add_argument("json", nargs="?", help="scenes.json (optional)")
    ap.add_argument("--panels", help="folder of panel images")
    ap.add_argument("--audio", help="folder of voice files (same count, sorted order)")
    ap.add_argument("--duration", type=float, default=4.0, help="seconds per scene when there is no audio")
    ap.add_argument("-o", "--output", default="manhwa.mp4")
    ap.add_argument("--size", default="1920x1080", help="WxH. Use 1080x1920 for Shorts.")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scene", type=int, help="render only this scene number (1-based) as a test")
    args = ap.parse_args()
    if not args.json and not args.panels:
        ap.error("give scenes.json or --panels FOLDER")
    args.size_given = args.size != "1920x1080"
    args.fps_given = args.fps != 30
    args.size = tuple(int(v) for v in args.size.lower().split("x"))

    W, H, scenes = load_scenes(args)
    W -= W % 2
    H -= H % 2
    if args.scene:
        scenes = [scenes[args.scene - 1]]
    fps = args.fps
    tmp = tempfile.mkdtemp(prefix="manhwa_")

    # ---- scene lengths + audio track
    parts = []
    for n, (i, cfg) in enumerate(scenes):
        tail = float(cfg.get("tail", DEFAULTS["tail"]))
        if cfg.get("duration"):
            dur = float(cfg["duration"])
        elif cfg.get("audio"):
            dur = audio_duration(cfg["audio"]) + tail
        else:
            dur = args.duration
        cfg["_dur"] = dur
        wav = os.path.join(tmp, "a%03d.wav" % n)
        if cfg.get("audio"):
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", cfg["audio"], "-af", "apad", "-t", "%.3f" % dur,
                   "-ar", "44100", "-ac", "2", wav]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                   "-t", "%.3f" % dur, wav]
        subprocess.run(cmd, check=True)
        parts.append(wav)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '%s'\n" % p.replace("\\", "/").replace("'", "'\\''"))
    full = os.path.join(tmp, "audio.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", full], check=True)

    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (W, H),
         "-r", str(fps), "-i", "-", "-i", full, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
         args.output], stdin=subprocess.PIPE)

    prev = np.zeros((H, W, 3), np.uint8)
    total = 0
    for n, (i, cfg) in enumerate(scenes):
        sc = Scene(cfg, i, W, H)
        sc.dur = cfg["_dur"]
        frames = int(round(sc.dur * fps))
        print("Scene %d: %s | panel %dx%d | motion=%s%s | enter=%s | %.1fs" % (
            i + 1, os.path.basename(cfg["image"]), sc.iw, sc.ih, sc.motion,
            " (long panel)" if sc.tall else "", sc.enter, sc.dur), flush=True)
        for f in range(frames):
            frame = render_frame(sc, f / fps, prev)
            enc.stdin.write(frame.tobytes())
            if f == frames - 1:
                prev = frame
        total += frames
    enc.stdin.close()
    enc.wait()
    print("Done: %s  (%d frames, %.1f s)" % (args.output, total, total / fps))

if __name__ == "__main__":
    main()
