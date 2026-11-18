"""Runs the two engines: Kokoro (voice) and whiteboard-animator (drawing). Used by the server in a background thread."""
from __future__ import annotations
import os, re, shutil, subprocess, sys
from pathlib import Path
from . import config

VOICES = ["am_liam", "am_onyx", "am_puck", "am_michael", "am_eric", "bm_george", "bm_lewis",
          "af_heart", "af_sarah", "af_nicole", "bf_emma", "bf_isabella"]
STYLES = ["calm", "normal", "energetic"]

def _env() -> dict:
    env = dict(os.environ)
    ap = config.animator_path()
    if ap:
        env["PYTHONPATH"] = str(ap) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def _kokoro_python(settings: dict) -> str:
    return config.find_kokoro_python(settings)

def animator_cmd() -> list[str]:
    """How to start the animator: a normal python runs the module; the packaged .exe calls itself with --run-animator."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-animator"]
    return [sys.executable, "-m", "whiteboard_animator.cli"]

def capabilities(settings: dict) -> dict:
    caps = {"ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe"))}
    try:
        if getattr(sys, "frozen", False):
            import whiteboard_animator  # bundled inside the .exe
            caps["animator"] = True
        else:
            r = subprocess.run([sys.executable, "-c", "import whiteboard_animator"], env=_env(),
                               capture_output=True, timeout=60)
            caps["animator"] = r.returncode == 0
    except Exception:
        caps["animator"] = False
    try:
        r = subprocess.run([_kokoro_python(settings), "-c", "import kokoro, soundfile"], env=_env(),
                           capture_output=True, timeout=120)
        caps["kokoro"] = r.returncode == 0
    except Exception:
        caps["kokoro"] = False
    return caps

class JobError(Exception):
    pass

def _run(cmd: list[str], log, cwd=None) -> None:
    log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    p = subprocess.Popen(cmd, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        line = line.rstrip()
        if line:
            log(line)
    if p.wait() != 0:
        raise JobError(f"A step failed (exit code {p.returncode}). See the log above.")

def make_voice(text: str, out_wav: Path, voice: str, style: str, settings: dict, log) -> None:
    work = out_wav.parent / "_voice_work"
    work.mkdir(parents=True, exist_ok=True)
    script = work / (out_wav.stem + ".txt")
    script.write_text(text, encoding="utf-8")
    _run([_kokoro_python(settings), str(Path(__file__).with_name("voice_kokoro.py")),
          "--script", str(script), "--out", str(work), "--name", out_wav.stem,
          "--voice", voice, "--mode", style, "--fresh"], log)
    produced = work / (out_wav.stem + ".wav")
    if not produced.exists():
        raise JobError("The voice step finished but no audio file was made.")
    shutil.move(str(produced), str(out_wav))
    shutil.rmtree(work / (out_wav.stem + "_parts"), ignore_errors=True)

def safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name).strip(" .")
    return name or "file"

def run_job(project: Path, scenes: list[dict], opts: dict, settings: dict, log, step) -> Path:
    """scenes: [{image, text, audio_mode: none|generate|upload, audio}]. Returns the output video path."""
    if not scenes:
        raise JobError("Add at least one scene (an image) first.")
    modes = {s.get("audio_mode", "none") for s in scenes}
    if "none" in modes and len(modes) > 1:
        raise JobError("Either every scene has a voice, or none does. Some scenes have no voice yet.")
    images = []
    for i, s in enumerate(scenes, 1):
        p = project / "images" / safe_name(s.get("image", ""))
        if not p.is_file():
            raise JobError(f"Scene {i}: the image file is missing. Upload it again.")
        images.append(p)

    audios: list[Path] = []
    for i, s in enumerate(scenes, 1):
        mode = s.get("audio_mode", "none")
        if mode == "generate":
            text = (s.get("text") or "").strip()
            if not text:
                raise JobError(f"Scene {i}: type the script to turn into a voice.")
            out = project / "audio" / f"scene-{i:02d}-voice.wav"
            log(f"Scene {i}: making the voice ({opts.get('voice', 'am_liam')})...")
            make_voice(text, out, opts.get("voice", "am_liam"), opts.get("style", "normal"), settings, log)
            audios.append(out)
            step()
        elif mode == "upload":
            p = project / "audio" / safe_name(s.get("audio", ""))
            if not p.is_file():
                raise JobError(f"Scene {i}: your audio file is missing. Upload it again.")
            audios.append(p)
            step()
        else:
            step()

    out = project / "out" / (safe_name(opts.get("name") or "my-video").removesuffix(".mp4") + ".mp4")
    cmd = [*animator_cmd(), *map(str, images), "-o", str(out),
           "--quality", opts.get("quality", "medium"), "--max-dim", str(int(opts.get("max_dim", 1280)))]
    if audios:
        cmd += ["--audio", *map(str, audios)]
    else:
        cmd += ["--duration", str(float(opts.get("seconds", 8)))]
    hand = opts.get("hand", "doodle")
    if hand == "off":
        cmd += ["--no-hand"]
    else:
        cmd += ["--hand-style", hand]
    if opts.get("camera") == "auto":
        cmd += ["--camera", "auto"]
    elif opts.get("camera") == "off":
        cmd += ["--camera", "off"]
    log("Drawing the video...")
    _run(cmd, log)
    step()
    if not out.exists():
        raise JobError("The video was not created.")
    return out
