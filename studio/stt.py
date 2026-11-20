"""Speech to text (transcription) with faster-whisper, an open-source engine (MIT licence) that runs on this computer.

The engine lives in its own small Python environment ("stt-env") so it can never disturb your voices (Kokoro) or the app.
"""
from __future__ import annotations
import datetime, json, re, shutil, subprocess, sys, textwrap, threading
from pathlib import Path
from . import config
from .engine import JobError, _find_media, _run, media_info, safe_name

WORKER = Path(__file__).with_name("stt_worker.py")

MODELS = [   # id is the faster-whisper model name. Sizes are the one-time download.
    {"id": "base",   "label": "Fast",                    "size": "about 150 MB", "bytes": 150_000_000, "note": "Quick. Fine for clear speech."},
    {"id": "small",  "label": "Balanced (recommended)",  "size": "about 480 MB", "bytes": 480_000_000, "note": "Good accuracy at a reasonable speed."},
    {"id": "medium", "label": "Most accurate",           "size": "about 1.5 GB", "bytes": 1_550_000_000, "note": "Best results, but slow on a normal PC."},
]
# Only languages Whisper really supports (checked against faster-whisper). Igbo and Zulu are NOT supported by Whisper.
LANGUAGES = [("", "Detect automatically"), ("en", "English"), ("yo", "Yoruba"), ("ha", "Hausa"), ("sw", "Swahili"), ("fr", "French"),
             ("es", "Spanish"), ("pt", "Portuguese"), ("ar", "Arabic"), ("hi", "Hindi"), ("zh", "Chinese"), ("ja", "Japanese"),
             ("ko", "Korean"), ("de", "German"), ("it", "Italian"), ("ru", "Russian"), ("tr", "Turkish"), ("nl", "Dutch"),
             ("pl", "Polish"), ("uk", "Ukrainian"), ("vi", "Vietnamese"), ("id", "Indonesian"), ("th", "Thai"), ("am", "Amharic"),
             ("so", "Somali"), ("sn", "Shona"), ("af", "Afrikaans")]
FORMATS = {"docx": "Word document (.docx)", "pdf": "PDF (.pdf)", "txt": "Plain text (.txt)", "srt": "Subtitles (.srt)", "vtt": "Subtitles (.vtt)"}


def stt_dir() -> Path:
    d = config.data_dir() / "stt"; d.mkdir(parents=True, exist_ok=True); return d

def venv_dir() -> Path: return stt_dir() / "env"
def models_dir() -> Path: return stt_dir() / "models"
def venv_python() -> Path:
    v = venv_dir()
    return v / "Scripts" / "python.exe" if sys.platform.startswith("win") else v / "bin" / "python"
def _ready_marker() -> Path: return venv_dir() / ".ready"

def model_downloaded(name: str) -> bool:
    d = models_dir()
    return d.is_dir() and any(d.glob(f"models--*--faster-whisper-{name}/snapshots/*/model.bin"))

def status() -> dict:
    return {"installed": venv_python().is_file() and _ready_marker().is_file(),
            "models": [dict(m, downloaded=model_downloaded(m["id"])) for m in MODELS],
            "languages": [{"id": i, "name": n} for i, n in LANGUAGES], "formats": FORMATS}

def _base_python(settings: dict) -> str:
    exe = Path(sys.executable)
    if exe.stem.lower().startswith("python"): return str(exe)
    for cand in (shutil.which("python"), shutil.which("python3")):
        if cand: return cand
    from .engine import _kokoro_python
    return _kokoro_python(settings)

def install(settings: dict, log, step=lambda: None) -> None:
    """One-time add-on: creates the environment and installs faster-whisper, python-docx and reportlab (all open source)."""
    py = venv_python()
    _ready_marker().unlink(missing_ok=True)
    if not py.is_file():
        log("Creating the transcription add-on folder...")
        _run([_base_python(settings), "-m", "venv", str(venv_dir())], log, what="step")
    step()
    log("Installing the speech engine. This needs internet and can take a few minutes...")
    _run([str(py), "-m", "pip", "install", "--upgrade", "faster-whisper", "python-docx", "reportlab"], log, what="step")
    step()
    _run([str(py), "-c", "import faster_whisper, docx, reportlab; print('Everything installed correctly.')"], log, what="step")
    _ready_marker().write_text("ok", encoding="utf-8")


# ------------------------------------------------------------------ transcribing
def _progress_setter(step, total=100):
    st = {"n": 0}
    def set_p(frac: float):
        target = int(max(0.0, min(1.0, frac)) * (total - 1))
        while st["n"] < target:
            step(); st["n"] += 1
    return set_p

def transcribe(project: Path, spec: dict, settings: dict, log, step) -> Path:
    if not status()["installed"]:
        raise JobError("The transcription add-on is not installed yet.", {"title": "Transcription is not set up yet", "what": "The transcription add-on has not been installed on this computer.",
                       "fix": "Click “Set up transcription” at the top of this page (one time, needs internet).", "action": None, "details": ""})
    model = spec.get("model") if spec.get("model") in {m["id"] for m in MODELS} else "small"
    lang = spec.get("language") if spec.get("language") in {i for i, _ in LANGUAGES} else ""
    task = "translate" if spec.get("task") == "translate" else "transcribe"
    src = _find_media(project, spec.get("file", ""))
    info = media_info(src)
    if not info.get("has_audio"):
        raise JobError("This file has no sound to transcribe.", {"title": "This file has no sound", "what": "The file you picked has no audio track, so there is nothing to turn into text.",
                       "fix": "Pick a video or audio file that has speech in it.", "action": None, "details": ""})
    set_p = _progress_setter(step)
    work = project / "work" / "stt"; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    wav = work / "audio.wav"
    log("Getting the sound ready...")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], log, what="step")
    set_p(0.05)
    out_dir = project / "transcripts"; out_dir.mkdir(exist_ok=True)
    base = safe_name(Path(src).stem); out = out_dir / (base + ".json"); i = 1
    while out.exists():
        out = out_dir / f"{base}-{i}.json"; i += 1
    tmp = work / "result.json"
    models_dir().mkdir(parents=True, exist_ok=True)
    seen = {"lang": lang}
    def on_line(line: str):
        if line.startswith("PROGRESS "):
            try: set_p(0.15 + 0.85 * float(line.split()[1]))
            except ValueError: pass
        elif line.startswith("MODEL_READY"):
            set_p(0.15); log("The model is ready. Listening to your audio...")
        elif line.startswith("LANGUAGE "):
            parts = line.split(); seen["lang"] = parts[1]; log(f"Language heard: {parts[1]}")
        elif not line.startswith("Warning: You are sending unauthenticated"):
            log(line[:160])
    if not model_downloaded(model):
        log(f"First time with this model: downloading it now ({next(m['size'] for m in MODELS if m['id']==model)}). Please keep this window open.")
    have = model_downloaded(model)
    stop = threading.Event()
    if not have:   # show real download progress (the download library prints nothing we can read)
        want = next(m["bytes"] for m in MODELS if m["id"] == model)
        def watch():
            while not stop.wait(3):
                try: got = sum(f.stat().st_size for f in models_dir().rglob("*") if f.is_file())
                except OSError: continue
                set_p(0.02 + 0.12 * min(1.0, got / want))
                try: log(f"Downloading the speech model: {got // 1_000_000} MB of about {want // 1_000_000} MB. This only happens once.")
                except Exception: return
        threading.Thread(target=watch, daemon=True).start()
    try:
        _run([str(venv_python()), str(WORKER), "transcribe", "--audio", str(wav), "--model", model, "--models-dir", str(models_dir()),
              "--out", str(tmp), "--language", lang, "--task", task] + (["--offline"] if have else []), on_line, what="stt",
             skip=("PROGRESS ", "Warning: You are sending unauthenticated"))
    finally:
        stop.set()
    if not tmp.is_file():
        raise JobError("The transcript was not created.")
    data = json.loads(tmp.read_text(encoding="utf-8"))
    data.update({"source": src.name, "model": model, "task": task, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                 "language": data.get("language") or seen["lang"]})
    if not data["segments"]:
        raise JobError("No speech was found.", {"title": "No speech was found", "what": "The model did not hear any words in this file.",
                       "fix": "Check that the file really has speech, or try the “Most accurate” quality.", "action": None, "details": ""})
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    step()
    return out


# ------------------------------------------------------------------ saved transcripts
def list_transcripts(project: Path) -> dict:
    d = project / "transcripts"; items, docs = [], []
    if d.is_dir():
        for p in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if p.suffix == ".json":
                try: j = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError): continue
                items.append({"name": p.name, "source": j.get("source", ""), "language": j.get("language", ""), "created": j.get("created", ""), "pieces": len(j.get("segments", []))})
            elif p.suffix.lower() in {".txt", ".srt", ".vtt", ".docx", ".pdf"}:
                docs.append({"name": p.name, "size": p.stat().st_size, "folder": "transcripts"})
    return {"transcripts": items, "documents": docs}

def load_transcript(project: Path, name: str) -> dict:
    p = project / "transcripts" / safe_name(name)
    if p.suffix != ".json" or not p.is_file():
        raise JobError("That transcript was not found.")
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ exporting
def clock(sec: float) -> str:
    sec = max(0, int(sec)); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _stamp(sec: float, comma: bool) -> str:
    ms = int(round(max(0.0, sec) * 1000)); h, r = divmod(ms, 3_600_000); m, r = divmod(r, 60_000); s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"

def blocks(segs: list[dict], timestamps: bool) -> list[tuple[str, str]]:
    """With time stamps: one block per piece. Without: readable paragraphs (new paragraph after a pause or when it gets long)."""
    if timestamps:
        return [(clock(s["start"]), s["text"].strip()) for s in segs if s["text"].strip()]
    paras, cur, last_end = [], "", 0.0
    for s in segs:
        t = s["text"].strip()
        if not t: continue
        if cur and (s["start"] - last_end > 1.8 or len(cur) > 600 or (len(cur) > 350 and cur.rstrip()[-1:] in ".?!。！？")):
            paras.append(cur); cur = ""
        cur = (cur + " " + t) if cur else t; last_end = s["end"]
    if cur: paras.append(cur)
    return [("", p) for p in paras]

def cues(segs: list[dict]) -> list[tuple[float, float, str]]:
    """Subtitle cues: at most 2 short lines each. Long pieces are split in proportion to their length."""
    out = []
    for s in segs:
        text = " ".join(s["text"].split())
        if not text: continue
        lines = textwrap.wrap(text, 42) or [text]
        groups = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        total = sum(len(g) for g in groups) or 1; t0 = float(s["start"]); span = max(0.4, float(s["end"]) - t0)
        for g in groups:
            t1 = t0 + span * len(g) / total; out.append((t0, t1, g)); t0 = t1
    return out

def export(project: Path, spec: dict, log=lambda *_: None) -> Path:
    fmt = spec.get("format", "docx")
    if fmt not in FORMATS: raise JobError("Unknown file type.")
    data = {}
    if spec.get("name"):
        try: data = load_transcript(project, spec["name"])
        except JobError: data = {}
    segs = spec.get("segments") or data.get("segments") or []
    segs = [{"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": str(s.get("text", ""))} for s in segs]
    if not any(s["text"].strip() for s in segs): raise JobError("There is no text to export.")
    stamps = bool(spec.get("timestamps"))
    title = (spec.get("title") or "").strip() or (Path(data.get("source", "Transcript")).stem or "Transcript")
    out_dir = project / "transcripts"; out_dir.mkdir(exist_ok=True)
    base = safe_name(spec.get("filename") or title)
    if Path(base).suffix.lower() in {".txt", ".srt", ".vtt", ".docx", ".pdf"}: base = Path(base).stem
    out = out_dir / f"{base}.{fmt}"; i = 1
    while out.exists():
        out = out_dir / f"{base}-{i}.{fmt}"; i += 1
    bl = blocks(segs, stamps)
    if fmt == "txt":
        out.write_text((title + "\n\n" if spec.get("with_title", True) else "") + "\n\n".join((f"[{l}] " if l else "") + t for l, t in bl) + "\n", encoding="utf-8")
    elif fmt in ("srt", "vtt"):
        cs = cues(segs); comma = fmt == "srt"
        body = "\n\n".join((f"{n}\n" if comma else "") + f"{_stamp(a, comma)} --> {_stamp(b, comma)}\n{t}" for n, (a, b, t) in enumerate(cs, 1))
        out.write_text(("" if comma else "WEBVTT\n\n") + body + "\n", encoding="utf-8")
    else:
        if not status()["installed"]:
            raise JobError("The transcription add-on is not installed yet.", {"title": "Word and PDF files need the add-on", "what": "Creating Word and PDF files uses the transcription add-on, which is not installed.",
                           "fix": "Click “Set up transcription”, or export as plain text or subtitles instead.", "action": None, "details": ""})
        meta = " · ".join(x for x in [f"Language: {data['language']}" if data.get("language") else "", f"Source: {data['source']}" if data.get("source") else "", datetime.date.today().isoformat()] if x)
        tmp = out_dir / "_export.json"
        tmp.write_text(json.dumps({"title": title, "meta": meta, "blocks": bl}, ensure_ascii=False), encoding="utf-8")
        try:
            _run([str(venv_python()), str(WORKER), "export", "--in", str(tmp), "--format", fmt, "--out", str(out)], log, what="export")
        finally:
            tmp.unlink(missing_ok=True)
    return out
