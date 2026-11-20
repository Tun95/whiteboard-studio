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
    "auto_setup": True,         # quietly add Japanese/Mandarin voice support on start if missing
    "kokoro_python": "",        # path to a python.exe that has Kokoro installed; empty = this python
}

def data_dir() -> Path:
    override = os.environ.get("WWS_DATA")
    base = Path(override) if override else Path.home() / "Documents" / "WhiteboardWaveStudio"
    base.mkdir(parents=True, exist_ok=True)
    return base

SUBFOLDERS = ("images", "screenshots", "audio", "media", "out", "work")
DEFAULT_PROJECT = "My first project"
_BAD = '<>:"/\\|?*'

def clean_project_name(name: str) -> str:
    n = "".join("_" if (c in _BAD or ord(c) < 32) else c for c in str(name or "")).strip(" .")
    return n[:60]

def save_setting(key: str, value) -> None:
    f = data_dir() / "settings.json"
    try: cur = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError): cur = dict(DEFAULT_SETTINGS)
    cur[key] = value
    f.write_text(json.dumps(cur, indent=2), encoding="utf-8")

def default_projects_dir() -> Path:
    return data_dir() / "projects"

def projects_dir() -> Path:
    """Where the projects are saved. The person can choose this folder (settings.json: projects_dir); if it cannot be used we fall back to the normal one."""
    chosen = str(load_settings().get("projects_dir") or "").strip()
    if chosen:
        try:
            d = Path(chosen); d.mkdir(parents=True, exist_ok=True)
            if os.access(d, os.W_OK): return d
        except OSError:
            pass
    d = default_projects_dir(); d.mkdir(parents=True, exist_ok=True)
    return d

def set_projects_folder(path: str, move: bool) -> str:
    """Changes where projects are saved. With move=True the existing projects are copied there first (originals removed only after a full copy)."""
    import shutil
    raw = str(path or "").strip().strip('"')
    if not raw:
        raise ValueError("Please choose a folder.")
    new = Path(raw).expanduser()
    if not new.is_absolute():
        raise ValueError("Please type the full folder path, for example D:\\My Videos, or press Browse.")
    try:
        new.mkdir(parents=True, exist_ok=True)
        t = new / ".wws-test"; t.write_text("x"); t.unlink()
    except OSError:
        raise ValueError("That folder cannot be used. It may be read-only or on a drive that is not connected. Choose another folder.")
    old = projects_dir()
    if new.resolve() == old.resolve():
        return str(new)
    if str(new.resolve()).startswith(str(old.resolve()) + os.sep):
        raise ValueError("Choose a folder outside your current projects folder.")
    if move:
        for d in [p for p in old.iterdir() if p.is_dir()]:
            dest = new / d.name
            if dest.exists():
                raise ValueError(f"The new folder already has a project called “{d.name}”. Choose an empty folder.")
        for d in [p for p in old.iterdir() if p.is_dir()]:
            shutil.copytree(d, new / d.name)
        for d in [p for p in old.iterdir() if p.is_dir()]:
            shutil.rmtree(d, ignore_errors=True)
    save_setting("projects_dir", str(new))
    return str(new)

def _make_project(p: Path) -> Path:
    for sub in SUBFOLDERS:
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p

def migrate_old_project() -> None:
    """Older versions kept everything in one 'current-project' folder. Move it into the first project, once."""
    old = data_dir() / "current-project"; new = projects_dir() / DEFAULT_PROJECT
    if old.is_dir() and not new.exists():
        try:
            old.rename(new)
        except OSError:
            import shutil; shutil.copytree(old, new)

def list_projects() -> list[dict]:
    out = []
    for d in sorted((p for p in projects_dir().iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        def n(sub, exts=None):
            f = d / sub
            return sum(1 for x in f.iterdir() if x.is_file() and (exts is None or x.suffix.lower() in exts)) if f.is_dir() else 0
        ads = d / "ads"
        out.append({"name": d.name, "videos": n("out", {".mp4"}), "files": n("media") + n("images") + n("audio") + n("screenshots"),
                    "ads": sum(1 for x in ads.iterdir() if x.is_dir()) if ads.is_dir() else 0,
                    "modified": max([d.stat().st_mtime] + [(d / "project.json").stat().st_mtime] if (d / "project.json").is_file() else [d.stat().st_mtime])})
    return out

def active_project_name() -> str:
    migrate_old_project()
    f = data_dir() / "active-project.txt"
    names = [p["name"] for p in list_projects()]
    try:
        cur = f.read_text(encoding="utf-8").strip()
    except OSError:
        cur = ""
    if cur not in names:
        cur = names[0] if names else DEFAULT_PROJECT
        if not names: _make_project(projects_dir() / cur)
        set_active_project(cur)
    return cur

def set_active_project(name: str) -> None:
    (data_dir() / "active-project.txt").write_text(name, encoding="utf-8")

def project_path(name: str) -> Path:
    p = projects_dir() / clean_project_name(name)
    if not p.is_dir():
        raise ValueError("That project could not be found.")
    return p

def create_project(name: str) -> str:
    n = clean_project_name(name)
    if not n:
        raise ValueError("Please type a name for the project.")
    p = projects_dir() / n
    if p.exists() or any(x.name.lower() == n.lower() for x in projects_dir().iterdir()):
        raise ValueError(f"You already have a project called “{n}”. Choose another name.")
    _make_project(p); return n

def rename_project(old: str, new: str) -> str:
    src = project_path(old); n = clean_project_name(new)
    if not n:
        raise ValueError("Please type a name for the project.")
    if n.lower() != src.name.lower() and any(x.name.lower() == n.lower() for x in projects_dir().iterdir()):
        raise ValueError(f"You already have a project called “{n}”. Choose another name.")
    if n != src.name:
        try:
            src.rename(projects_dir() / n)
        except OSError:
            raise ValueError("The project could not be renamed. A file inside it may be open in another program.")
    return n

def delete_project(name: str) -> None:
    import shutil
    p = project_path(name)
    shutil.rmtree(p, ignore_errors=True)
    if p.exists():
        raise ValueError("Some files could not be removed. Close other programs that use them and try again.")

def project_dir() -> Path:
    return _make_project(project_path(active_project_name()))

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
