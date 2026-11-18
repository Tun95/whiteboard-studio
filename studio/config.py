"""Settings and folders for the app. Everything lives under one data folder the user can open."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

APP_NAME = "Whiteboard Wave Studio"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# Put your donation page here (Buy Me a Coffee, Ko-fi, PayPal.me, Paystack page...). Empty = "coming soon".
DEFAULT_SETTINGS = {
    "donate_url": "",
    "donate_text": "This app is free. If it saves you time, a small donation helps me keep improving it.",
    "kokoro_python": "",        # path to a python.exe that has Kokoro installed; empty = this python
}

def data_dir() -> Path:
    override = os.environ.get("WWS_DATA")
    base = Path(override) if override else Path.home() / "Documents" / "WhiteboardWaveStudio"
    base.mkdir(parents=True, exist_ok=True)
    return base

def project_dir() -> Path:
    p = data_dir() / "current-project"
    for sub in ("images", "audio", "out", "work"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p

def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    f = data_dir() / "settings.json"
    if f.exists():
        try:
            s.update(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    else:
        try:
            f.write_text(json.dumps(DEFAULT_SETTINGS, indent=2), encoding="utf-8")
        except OSError:
            pass
    return s

def animator_path() -> Path | None:
    """Folder that contains the whiteboard_animator package when it is not pip-installed."""
    for cand in (REPO / "whiteboard-animator", HERE / "whiteboard-animator", HERE.parent / "whiteboard-animator"):
        if (cand / "whiteboard_animator").is_dir():
            return cand
    return None

def find_kokoro_python(settings: dict) -> str:
    """The python that has Kokoro installed: the one set in settings.json, else the user's existing kokoro-env, else this python."""
    if settings.get("kokoro_python"):
        return settings["kokoro_python"]
    home = Path.home()
    for cand in (home / "Desktop" / "White Board Animation" / "_Tools" / "kokoro" / "kokoro-env" / "Scripts" / "python.exe",
                 home / "OneDrive" / "Desktop" / "White Board Animation" / "_Tools" / "kokoro" / "kokoro-env" / "Scripts" / "python.exe"):
        if cand.is_file():
            return str(cand)
    return sys.executable
