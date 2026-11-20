"""Guided app-ad builder: turns a plain form (what the user typed and picked) into the files the ad maker needs.
Users never see ad.json; it is written here from a simple description. The form is kept in builder.json so the ad can be edited later."""
from __future__ import annotations
import json, re, shutil
from pathlib import Path

PHONES = {"black": ("#0b0b0f", "#7a7d8c"), "white": ("#f4f4f6", "#b9bcc8"), "blue": ("#1d3a8a", "#6c8cf0"),
          "red": ("#9b1c2e", "#f08a98"), "gold": ("#8a6a1d", "#f0d28a"), "green": ("#14532d", "#6fd39a")}
LOOKS = {  # name: (background top, background bottom, caption colours)
    "purple": ("#2b1055", "#7c3aed", ["#e11d48", "#2563eb", "#f97316", "#16a34a"]),
    "ocean": ("#06223f", "#0e7490", ["#f59e0b", "#7c3aed", "#e11d48", "#16a34a"]),
    "sunset": ("#4a1030", "#f97316", ["#2563eb", "#7c3aed", "#16a34a", "#0891b2"]),
    "forest": ("#052e1a", "#16a34a", ["#f59e0b", "#2563eb", "#e11d48", "#7c3aed"]),
    "night": ("#0b0b12", "#2a2f4a", ["#38bdf8", "#e11d48", "#f59e0b", "#16a34a"]),
    "light": ("#e8eefc", "#ffffff", ["#2563eb", "#e11d48", "#16a34a", "#7c3aed"]),
}
EFFECTS = {"confetti", "sparkle", "rise", "coins"}
SLUG = re.compile(r"[^A-Za-z0-9._ -]")

def _safe(name: str) -> str:
    n = SLUG.sub("_", Path(str(name)).name).strip(" .")
    return n or "file"

def _accent(text: str) -> str:
    """*word* -> {word} (the ad maker's accent mark)."""
    t = str(text or "").replace("{", "").replace("}", "")
    return re.sub(r"\*([^*\n]+)\*", r"{\1}", t).replace("*", "").strip()

def _gradient(path: Path, size: tuple[int, int], top: str, bottom: str) -> None:
    from PIL import Image
    import numpy as np
    W, H = size
    def rgb(h): h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    a, b = np.array(rgb(top), float), np.array(rgb(bottom), float)
    t = np.linspace(0, 1, H)[:, None, None] * 0.75 + np.linspace(0, 1, W)[None, :, None] * 0.25
    img = (a + (b - a) * t).clip(0, 255).astype("uint8")
    Image.fromarray(np.broadcast_to(img, (H, W, 3)).copy()).save(path)

def _clean_box(b):
    try:
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in b)
    except (TypeError, ValueError):
        return None
    if x1 - x0 < 0.03 or y1 - y0 < 0.02:
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]

def validate(spec: dict) -> list[str]:
    """Plain-language problems that stop the ad being made."""
    out = []
    scenes = spec.get("scenes") or []
    if not scenes:
        out.append("Add at least one scene.")
    for i, s in enumerate(scenes, 1):
        if not (str(s.get("headline") or "").strip() or s.get("shot")):
            out.append(f"Scene {i} is empty. Type a headline or choose a screenshot.")
    return out

def build(project: Path, spec: dict) -> str:
    """Writes ads/<name>/ (ad.json, ad-preview.json, script, pictures) and returns the ad name."""
    probs = validate(spec)
    if probs:
        raise ValueError(" ".join(probs))
    name = _safe(spec.get("name") or spec.get("app_name") or "My ad")
    root = project / "ads" / name
    existed = root.is_dir()
    root.mkdir(parents=True, exist_ok=True)
    try:
        return _build(project, spec, name, root)
    except Exception:
        if not existed: shutil.rmtree(root, ignore_errors=True)
        raise

def _build(project: Path, spec: dict, name: str, root: Path) -> str:
    for sub in ("0-screenshots", "0-scripts", "1-images", "2-audio"):
        (root / sub).mkdir(exist_ok=True)
    for f in (root / "1-images").glob("bg-*.png"):
        f.unlink()
    size = str(spec.get("size") or "1920x1080")
    W, H = (int(v) for v in size.split("x")) if re.fullmatch(r"\d{3,4}x\d{3,4}", size) else (1920, 1080)
    tall = H > W
    pc, pe = PHONES.get(spec.get("phone"), PHONES["black"])
    top, bot, caps = LOOKS.get(spec.get("look"), LOOKS["purple"])
    cr = dict(crop_top=0.0, crop_bottom=0.0, color=pc, edge=pe)
    _gradient(root / "1-images" / "bg.png", (1280, 720) if not tall else (720, 1280), top, bot)
    # copy pictures the ad uses
    def bring(ref, dest_folder):
        src = None
        for folder in ("screenshots", "images", "media", "audio"):
            p = project / folder / _safe(ref)
            if p.is_file(): src = p; break
        if not src:
            raise ValueError(f"The file “{ref}” could not be found. Please add it again.")
        shutil.copy2(src, root / dest_folder / src.name)
        return f"{dest_folder}/{src.name}"
    scenes_out, script = [], []
    for i, s in enumerate(spec.get("scenes") or [], 1):
        sc = {"background": "1-images/bg.png"}
        voice = str(s.get("voice") or "").strip()
        secs = min(30.0, max(2.0, float(s.get("seconds") or 6)))
        sc["duration"] = secs  # silent length. When there is a voice, its length is used instead.
        if voice:
            script.append(re.sub(r"\s+", " ", voice))
            sc["_voice_audio"] = f"2-audio/scene-{len(script):02d}.wav"
        side = s.get("side") if s.get("side") in ("left", "right", "center") else "right"
        if tall: side = "center"
        col = caps[(i - 1) % len(caps)]
        col2 = caps[i % len(caps)]
        motion = s.get("motion")
        if motion == "zoom":
            sc["camera"] = [{"t": 0, "zoom": 1.0}, {"t": "end", "zoom": 1.2}]
        elif motion == "pan":
            sc["camera"] = [{"t": 0, "zoom": 1.15, "x": 0.4, "y": 0.5}, {"t": "end", "zoom": 1.15, "x": 0.6, "y": 0.5}]
        sc["transition_type"] = ["fade", "slide_left", "zoom", "wipe", "slide_up"][(i - 1) % 5] if i > 1 else "fade"
        # phone
        if s.get("shot"):
            shot = bring(s["shot"], "0-screenshots")
            if tall:    pos, ph, tx, ty = [0.5, 0.62], 0.66, 0.5, 0.1
            elif side == "left":   pos, ph, tx, ty = [0.28, 0.5], 0.86, 0.73, 0.2
            elif side == "right":  pos, ph, tx, ty = [0.72, 0.5], 0.86, 0.27, 0.2
            else:       pos, ph, tx, ty = [0.5, 0.58], 0.76, 0.5, 0.09
            enter = ["drop", "slide_right", "pop", "slide_left"][(i - 1) % 4]
            phone = dict(pos=pos, height=ph, enter=enter, enter_at=0.3, motion="float+sway", **cr, screens=[shot])
            box = _clean_box(s.get("box")) if s.get("box") else None
            if box:
                phone["highlights"] = [{"screen": 0, "box": box, "start": 1.8, "end": "end"}]
                if s.get("pullout"):
                    to = ([0.5, 0.3], 0.5) if tall else ([0.28, 0.62] if side == "right" else [0.72, 0.62] if side == "left" else [0.2, 0.5], 0.28)
                    phone["projections"] = [{"screen": 0, "box": box, "start": 2.0, "end": "end", "to": to[0], "width": to[1], "tilt": -2}]
            sc["phone"] = phone
        else:
            tx, ty = 0.5, 0.4 if not tall else 0.3
        # captions
        caps_out = []
        head, sub = _accent(s.get("headline")), _accent(s.get("sub"))
        size1 = 0.062 if tall else 0.075
        if head:
            caps_out.append({"text": head, "pos": [tx, ty], "start": 0.8, "anim": "pop" if not s.get("shot") else ("slide_right" if tx < 0.5 else "slide_left"), "bg": col,
                             "size": 0.05 if tall else 0.07, **({} if size1 else {})})
        if sub:
            caps_out.append({"text": sub, "pos": [tx, min(0.95, ty + (0.16 if not tall else 0.1))], "start": 2.4, "anim": "slide_up", "bg": col2,
                             "size": 0.04 if tall else 0.052})
        if s.get("badge"):
            badge = None
            for folder in ("images",):
                for cand in ("google-play-badge.png",):
                    if (project / folder / cand).is_file(): badge = bring(cand, "1-images")
            entry = {"fallback_text": "Get it on Google Play", "pos": [tx, 0.82 if tall else (0.72 if s.get("shot") else 0.66)], "start": 1.4, "height": 0.1 if tall else 0.17}
            entry["image"] = badge or "1-images/none.png"
            caps_out.append(entry)
        if caps_out: sc["captions"] = caps_out
        if s.get("effect") in EFFECTS:
            sc["fx"] = [{"type": s["effect"], "start": 1.0, "end": "end"}]
        scenes_out.append(sc)
    music = None
    if spec.get("music"):
        music = bring(spec["music"], "2-audio")
    def doc(with_audio):
        sl = []
        for sc in scenes_out:
            d = {k: v for k, v in sc.items() if k != "_voice_audio"}
            if with_audio and sc.get("_voice_audio"):
                d["audio"] = sc["_voice_audio"]; d.pop("duration", None)
            sl.append(d)
        j = {"size": [W, H], "fps": 30, "defaults": {"transition": 0.45, "caption_style": "glass", "font": "Inter-ExtraBold.otf"}, "scenes": sl}
        if music:
            j["music"] = music; j["music_volume"] = min(0.4, max(0.0, float(spec.get("music_volume", 0.1))))
        return j
    has_voice = any(str(s.get("voice") or "").strip() for s in spec.get("scenes") or [])
    (root / "ad.json").write_text(json.dumps(doc(has_voice), indent=1), encoding="utf-8")
    (root / "ad-preview.json").write_text(json.dumps(doc(False), indent=1), encoding="utf-8")
    sp = root / "0-scripts" / "ad-voice-script.txt"
    if has_voice: sp.write_text("\n\n".join(script) + "\n", encoding="utf-8")
    else: sp.unlink(missing_ok=True)
    (root / "builder.json").write_text(json.dumps({**spec, "name": name}, indent=1), encoding="utf-8")
    return name

def load(project: Path, name: str) -> dict:
    f = project / "ads" / _safe(name) / "builder.json"
    if not f.is_file():
        raise ValueError("This ad was imported, so it cannot be edited in the builder.")
    return json.loads(f.read_text(encoding="utf-8"))
