"""Doodle picture maker: describe a picture in words and the app draws it as a whiteboard doodle.

Everything is free and runs on this computer (no account, no key, no internet after set-up):
  - stable-diffusion.cpp  (MIT licence)            runs the picture model
  - Z-Image Turbo         (Apache-2.0, Alibaba)    the picture model (quantised GGUF files by leejet)
  - Qwen3 4B Instruct     (Apache-2.0)             understands the written description
  - FLUX/Z-Image "ae" VAE (Apache-2.0)             turns the result into pixels (public copy by Comfy-Org, no login)

The download links live in SOURCES below. If a link ever stops working, put a file called sources.json in the
"picmaker" folder with only the entries to change; no code change is needed.
"""
from __future__ import annotations
import hashlib, json, os, random, re, shutil, stat, sys, time, urllib.error, urllib.request, zipfile
from pathlib import Path
from . import config
from .engine import JobError, _run, safe_name

SOURCES = {
    "engine_api": "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest",
    "models": {   # quality id -> picture model file
        "standard": {"url": "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_0.gguf",
                     "name": "z_image_turbo-Q4_0.gguf", "bytes": 3_680_000_000},
        "small":    {"url": "https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q2_K.gguf",
                     "name": "z_image_turbo-Q2_K.gguf", "bytes": 2_590_000_000},
    },
    "text": {"url": "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
             "name": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "bytes": 2_500_000_000},
    "vae": {"url": "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
            "name": "ae.safetensors", "bytes": 335_000_000,
            "sha256": "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"},
}

QUALITY = [
    {"id": "standard", "label": "Standard (recommended)", "size": "about 6.5 GB", "note": "Best pictures."},
    {"id": "small",    "label": "Smallest download",      "size": "about 5.4 GB", "note": "Simpler pictures, a little less detail."},
]
STYLES = {
    "whiteboard": ("Black marker doodle (best for whiteboard videos)",
                   "a simple hand-drawn black marker doodle of {p}, whiteboard animation style, bold clean outlines, plain white background, no text, no shading"),
    "colour":     ("Colourful marker doodle",
                   "a simple hand-drawn colourful marker doodle of {p}, bright flat colours, thick outlines, plain white background, whiteboard explainer video style, no text"),
    "icon":       ("Simple line icon",
                   "a simple minimal black line icon of {p}, thick outline, plain white background, no text"),
}
SHAPES = {"square": ("Square", 512, 512), "wide": ("Wide (for videos)", 768, 448), "tall": ("Tall (for Reels)", 448, 768)}


def sources() -> dict:
    s = json.loads(json.dumps(SOURCES))
    f = pic_dir() / "sources.json"
    if f.is_file():
        try:
            for k, v in json.loads(f.read_text(encoding="utf-8")).items():
                if isinstance(v, dict) and isinstance(s.get(k), dict):
                    for kk, vv in v.items():
                        if isinstance(vv, dict) and isinstance(s[k].get(kk), dict): s[k][kk].update(vv)
                        else: s[k][kk] = vv
                else:
                    s[k] = v
        except (OSError, ValueError):
            pass
    return s

def pic_dir() -> Path:
    d = config.data_dir() / "picmaker"; d.mkdir(parents=True, exist_ok=True); return d
def bin_dir() -> Path: return pic_dir() / "engine"
def models_dir() -> Path:
    d = pic_dir() / "models"; d.mkdir(parents=True, exist_ok=True); return d
def _state_file() -> Path: return pic_dir() / "ready.json"

def find_exe() -> Path | None:
    forced = str(config.load_settings().get("picmaker_exe") or "").strip()
    if forced and Path(forced).is_file(): return Path(forced)
    b = bin_dir()
    if b.is_dir():
        for names in (("sd-cli.exe", "sd-cli"), ("sd.exe", "sd")):
            for n in names:
                hit = next(iter(sorted(b.rglob(n))), None)
                if hit and hit.is_file(): return hit
    return None

def _quality() -> str:
    try: return json.loads(_state_file().read_text(encoding="utf-8")).get("quality", "standard")
    except (OSError, ValueError): return "standard"

def _paths(quality: str | None = None) -> dict:
    s = sources(); q = quality or _quality()
    m = s["models"].get(q) or s["models"]["standard"]
    return {"model": models_dir() / m["name"], "text": models_dir() / s["text"]["name"], "vae": models_dir() / s["vae"]["name"]}

def _have(p: Path, want: int) -> bool:
    return p.is_file() and p.stat().st_size >= want * 0.9

def status() -> dict:
    s = sources(); q = _quality(); p = _paths(q)
    eng = find_exe() is not None
    files = _have(p["model"], (s["models"].get(q) or s["models"]["standard"])["bytes"]) and _have(p["text"], s["text"]["bytes"]) and _have(p["vae"], s["vae"]["bytes"])
    return {"ready": eng and files, "engine": eng, "files": files, "quality": q, "qualities": QUALITY,
            "styles": [{"id": k, "label": v[0]} for k, v in STYLES.items()],
            "shapes": [{"id": k, "label": v[0]} for k, v in SHAPES.items()]}


# ---------------------------------------------------------------- downloading
def _open(url: str, start: int = 0):
    req = urllib.request.Request(url, headers={"User-Agent": "WhiteboardWaveStudio", "Range": f"bytes={start}-" if start else "bytes=0-"})
    return urllib.request.urlopen(req, timeout=60)

def _net_error(e: Exception, url: str) -> JobError:
    code = getattr(e, "code", None)
    if code in (401, 403):
        what = "A download link now asks for a sign-in, which this app cannot do."
        fix = "Please tell the developer (use “Copy details”), so the link can be replaced with a public one."
    elif code == 404:
        what = "A download link no longer exists."
        fix = "Please tell the developer (use “Copy details”), so the link can be updated."
    else:
        what = "The internet connection failed or was too slow while downloading."
        fix = "Connect to the internet and press the button again. The download continues from where it stopped."
    return JobError(what + " " + fix, {"title": "The picture maker could not be downloaded", "what": what, "fix": fix, "action": None, "details": f"{url}\n{e}"})

def check_link(url: str) -> None:
    try:
        with _open(url) as r: r.read(1)
    except Exception as e:
        raise _net_error(e, url)

def _download(url: str, dest: Path, want: int, log, label: str, sha256: str = "") -> None:
    """Downloads to dest, resuming a partial file. Shows progress."""
    if _have(dest, want): return
    part = dest.with_suffix(dest.suffix + ".part"); got = part.stat().st_size if part.is_file() else 0
    try:
        r = _open(url, got)
    except urllib.error.HTTPError as e:
        if e.code == 416 and part.is_file():   # already complete
            part.replace(dest); return
        raise _net_error(e, url)
    except Exception as e:
        raise _net_error(e, url)
    if getattr(r, "status", 200) != 206 and got:   # server ignored the resume request
        got = 0
    total = got + int(r.headers.get("Content-Length") or 0) if r.headers.get("Content-Length") else want
    last = 0.0
    try:
        with r, open(part, "ab" if got else "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk: break
                f.write(chunk); got += len(chunk)
                if time.time() - last > 2:
                    last = time.time(); log(f"Downloading {label}: {got // 1_000_000} MB of about {max(total, want) // 1_000_000} MB")
    except Exception as e:
        raise _net_error(e, url)
    if got < want * 0.9:
        raise JobError("The download stopped early. Press the button again to continue.", {"title": "The download stopped early", "what": f"Only {got // 1_000_000} MB of about {want // 1_000_000} MB arrived.", "fix": "Press the button again. The download continues from where it stopped.", "action": None, "details": url})
    if sha256:
        h = hashlib.sha256()
        with open(part, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""): h.update(blk)
        if h.hexdigest().lower() != sha256.lower():
            part.unlink(missing_ok=True)
            raise JobError("A downloaded file was damaged. Press the button again to download it fresh.", {"title": "A downloaded file was damaged", "what": "The file did not match its checksum.", "fix": "Press the button again.", "action": None, "details": url})
    part.replace(dest)

def _pick_asset(assets: list[dict]) -> dict | None:
    win = sys.platform.startswith("win"); plat = "win" if win else ("linux" if sys.platform.startswith("linux") else "osx")
    best, best_score = None, -1
    for a in assets:
        n = a.get("name", "").lower()
        if not n.endswith(".zip") or plat not in n: continue
        if any(x in n for x in ("cuda", "cudart", "rocm", "hip", "sycl", "opencl", "vulkan", "noavx", "avx512")): continue
        score = 3 if "avx2" in n else (2 if "avx" in n else 1)
        if "x64" in n or "x86_64" in n or "amd64" in n: score += 1
        if score > best_score: best, best_score = a, score
    return best

def _install_engine(log) -> None:
    if find_exe(): return
    log("Finding the picture engine…")
    try:
        with urllib.request.urlopen(urllib.request.Request(sources()["engine_api"], headers={"User-Agent": "WhiteboardWaveStudio", "Accept": "application/vnd.github+json"}), timeout=30) as r:
            rel = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise _net_error(e, sources()["engine_api"])
    asset = _pick_asset(rel.get("assets", []))
    if not asset:
        raise JobError("No picture engine for this computer was found.", {"title": "No picture engine found for this computer", "what": "The free picture engine has no ready-made version for this computer in its latest release.", "fix": "Please tell the developer (use “Copy details”).", "action": None, "details": ", ".join(a.get("name", "") for a in rel.get("assets", []))[:600]})
    zp = pic_dir() / asset["name"]
    _download(asset["browser_download_url"], zp, max(1, int(asset.get("size") or 1_000_000)), log, "the picture engine")
    b = bin_dir(); shutil.rmtree(b, ignore_errors=True); b.mkdir(parents=True)
    with zipfile.ZipFile(zp) as z: z.extractall(b)
    zp.unlink(missing_ok=True)
    exe = find_exe()
    if not exe:
        raise JobError("The picture engine was downloaded but its program file was not inside.", {"title": "The picture engine looks incomplete", "what": "The downloaded package did not contain the expected program.", "fix": "Please tell the developer (use “Copy details”).", "action": None, "details": asset["name"]})
    if os.name != "nt": exe.chmod(exe.stat().st_mode | stat.S_IEXEC)


def install(settings: dict, quality: str, log, step) -> Path | None:
    """One-time set-up: engine (small) + three model files (about 6 GB). Resumes if interrupted."""
    s = sources(); quality = quality if quality in s["models"] else "standard"
    m = s["models"][quality]
    p = _paths(quality)
    log("Checking the download links…")
    todo = ([] if find_exe() else [s["engine_api"]]) \
        + ([] if _have(p["vae"], s["vae"]["bytes"]) else [s["vae"]["url"]]) \
        + ([] if _have(p["text"], s["text"]["bytes"]) else [s["text"]["url"]]) \
        + ([] if _have(p["model"], m["bytes"]) else [m["url"]])
    for u in todo:    # test every link first, so nothing big is downloaded just to fail later
        check_link(u)
    step()
    _install_engine(log); step()
    _download(s["vae"]["url"], p["vae"], s["vae"]["bytes"], log, "the picture decoder", s["vae"].get("sha256", "")); step()
    _download(s["text"]["url"], p["text"], s["text"]["bytes"], log, "the language part (2.5 GB)"); step()
    _download(m["url"], p["model"], m["bytes"], log, "the picture model"); step()
    _state_file().write_text(json.dumps({"quality": quality}), encoding="utf-8")
    log("Everything is ready.")
    return None


# ---------------------------------------------------------------- making pictures
def _slug(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:32]) or "picture"

def generate(project: Path, body: dict, settings: dict, log, step) -> Path:
    prompt = " ".join(str(body.get("prompt") or "").split())
    if not prompt:
        raise JobError("Please describe the picture first.", {"title": "Describe the picture first", "what": "The description box is empty.", "fix": "Type what you want to see, for example: a happy family eating together.", "action": None, "details": ""})
    if len(prompt) > 600: prompt = prompt[:600]
    st = status()
    if not st["ready"]:
        raise JobError("The picture maker is not set up yet.", {"title": "Set up the picture maker first", "what": "The one-time download has not finished.", "fix": "Press “Set up the picture maker” at the top of the page.", "action": None, "details": ""})
    exe = find_exe(); p = _paths(); style = body.get("style") if body.get("style") in STYLES else "whiteboard"
    _, w, h = SHAPES.get(body.get("shape"), SHAPES["square"]); count = max(1, min(4, int(body.get("count") or 1)))
    full = STYLES[style][1].format(p=prompt)
    work = project / "work" / "pictures"; work.mkdir(parents=True, exist_ok=True)
    images = project / "images"; images.mkdir(exist_ok=True)
    last = None
    for i in range(count):
        seed = random.randint(1, 2_000_000_000); tmp = work / f"pic-{seed}.png"
        log(f"Drawing picture {i + 1} of {count}… this can take a few minutes. Please keep the app open.")
        _run([str(exe), "--diffusion-model", str(p["model"]), "--vae", str(p["vae"]), "--llm", str(p["text"]),
              "-p", full, "--cfg-scale", "1.0", "--steps", "8", "-W", str(w), "-H", str(h), "-s", str(seed), "-o", str(tmp), "--diffusion-fa"],
             log, what="pic")
        if not tmp.is_file() or tmp.stat().st_size < 1000:
            raise JobError("The picture engine finished but no picture was made.", {"title": "No picture was made", "what": "The picture engine ran but did not save a picture.", "fix": "Try again. If it keeps happening, press “Copy details” and send them to the developer.", "action": None, "details": ""})
        dest = images / f"doodle-{_slug(prompt)}-{seed}.png"
        shutil.move(str(tmp), str(dest)); last = dest; step()
    shutil.rmtree(work, ignore_errors=True)
    return last

def list_doodles(project: Path) -> list[dict]:
    d = project / "images"
    items = sorted((p for p in d.glob("doodle-*.png")), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
    return [{"name": p.name, "size": p.stat().st_size} for p in items]
