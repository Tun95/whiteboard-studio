"""Runs the two engines: Kokoro (voice) and whiteboard-animator (drawing). Used by the server in a background thread."""
from __future__ import annotations
import os, re, shutil, subprocess, sys
from pathlib import Path
from . import config, friendly

VOICES = ["am_liam", "am_onyx", "am_puck", "am_michael", "am_eric", "bm_george", "bm_lewis",
          "af_heart", "af_sarah", "af_nicole", "bf_emma", "bf_isabella"]
STYLES = ["calm", "normal", "energetic", "hype"]

def _env() -> dict:
    env = dict(os.environ)
    ap = config.animator_path()
    if ap:
        env["PYTHONPATH"] = str(ap) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def tool_cmd(kind: str) -> list[str]:
    """Command prefix for: animator | manhwa | ad. In the packaged .exe the app calls itself."""
    if getattr(sys, "frozen", False):
        return [sys.executable, {"animator": "--run-animator", "manhwa": "--run-manhwa", "ad": "--run-ad"}[kind]]
    if kind == "animator":
        return [sys.executable, "-m", "whiteboard_animator.cli"]
    ap = config.animator_path()
    script = {"manhwa": "manhwa_panels.py", "ad": "app_ad.py"}[kind]
    return [sys.executable, str((ap / script) if ap else script)]

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
    """A problem to show the user. `info` (optional) is the friendly card: title / what / fix / action / details."""
    def __init__(self, message: str, info: dict | None = None):
        super().__init__(message)
        self.info = info or {"title": "Problem", "what": message, "fix": "", "action": None, "details": ""}

def _run(cmd: list[str], log, cwd=None, what: str = "step", voice: str = "") -> None:
    log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    lines: list[str] = []
    try:
        p = subprocess.Popen(cmd, cwd=cwd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        info = friendly.explain([f"FileNotFoundError: {e}", cmd[0]], what, voice)
        raise JobError(info["title"] + ". " + info["what"], info)
    for line in p.stdout:
        line = line.rstrip()
        if line:
            log(line); lines.append(line); del lines[:-120]
    if p.wait() != 0:
        info = friendly.explain(lines, what, voice)
        info["details"] = f"(exit code {p.returncode})\n" + info["details"]
        raise JobError(info["title"] + ". " + info["what"], info)

def make_voice(text: str, out_wav: Path, voice: str, style: str, settings: dict, log) -> None:
    work = out_wav.parent / "_voice_work"
    work.mkdir(parents=True, exist_ok=True)
    script = work / (out_wav.stem + ".txt")
    script.write_text(text, encoding="utf-8")
    _run([_kokoro_python(settings), str(Path(__file__).with_name("voice_kokoro.py")),
          "--script", str(script), "--out", str(work), "--name", out_wav.stem,
          "--voice", voice, "--mode", style, "--fresh"], log, what="voice", voice=voice)
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
    _run(cmd, log, what="video")
    step()
    if not out.exists():
        raise JobError("The video was not created.")
    return out


# ----------------------------------------------------------------------------- voices
def voice_sample(voice: str, text: str, settings: dict, log=lambda *_: None) -> Path:
    """Make (or reuse) a short sample so users can listen before choosing."""
    import hashlib
    from . import voices
    if voice not in {v["id"] for v in voices.library()}:
        raise JobError("Unknown voice.")
    text = (text or "").strip() or voices.SAMPLE_TEXT[voices.lang_of(voice)]
    folder = config.data_dir() / "voice-samples"; folder.mkdir(exist_ok=True)
    out = folder / f"{voice}-{hashlib.md5(text.encode()).hexdigest()[:8]}.wav"
    if not out.exists():
        make_voice(text, out, voice, "normal", settings, log)
    return out

# ----------------------------------------------------------------------------- manhwa
def run_manhwa(project: Path, panels: list[dict], opts: dict, settings: dict, log, step) -> Path:
    if not panels:
        raise JobError("Add at least one panel image first.")
    modes = {p.get("audio_mode", "none") for p in panels}
    if "none" in modes and len(modes) > 1:
        raise JobError("Either every panel has a voice, or none does.")
    work = project / "work" / "manhwa"
    shutil.rmtree(work, ignore_errors=True)
    (work / "panels").mkdir(parents=True); (work / "audio").mkdir()
    scenes = []
    for i, pn in enumerate(panels, 1):
        src = project / "images" / safe_name(pn.get("image", ""))
        if not src.is_file():
            raise JobError(f"Panel {i}: the image file is missing. Upload it again.")
        dst = work / "panels" / f"{i:03d}{src.suffix.lower()}"
        shutil.copyfile(src, dst)
        sc = {"image": str(dst), "motion": pn.get("motion", "auto"), "enter": pn.get("enter", "auto")}
        mode = pn.get("audio_mode", "none")
        if mode == "generate":
            text = (pn.get("text") or "").strip()
            if not text:
                raise JobError(f"Panel {i}: type the words for this panel's voice.")
            wav = work / "audio" / f"{i:03d}.wav"
            log(f"Panel {i}: making the voice ({opts.get('voice', 'am_liam')})...")
            make_voice(text, wav, opts.get("voice", "am_liam"), opts.get("style", "normal"), settings, log)
            sc["audio"] = str(wav)
        elif mode == "upload":
            a = project / "audio" / safe_name(pn.get("audio", ""))
            if not a.is_file():
                raise JobError(f"Panel {i}: your audio file is missing.")
            dst_a = work / "audio" / f"{i:03d}{a.suffix.lower()}"; shutil.copyfile(a, dst_a); sc["audio"] = str(dst_a)
        scenes.append(sc)
        step()
    out = project / "out" / (safe_name(opts.get("name") or "manhwa-video").removesuffix(".mp4") + ".mp4")
    cmd = [*tool_cmd("manhwa"), "--panels", str(work / "panels"), "-o", str(out),
           "--size", opts.get("size", "1920x1080"), "--duration", str(float(opts.get("seconds", 4)))]
    if any(p.get("audio_mode", "none") != "none" for p in panels):
        cmd += ["--audio", str(work / "audio")]
    log("Building the manhwa video...")
    _run(cmd, log, what="manhwa")
    step()
    if not out.exists():
        raise JobError("The video was not created.")
    return out

# ----------------------------------------------------------------------------- app ads
def list_ad_packs(project: Path) -> list[dict]:
    root = project / "ads"; root.mkdir(exist_ok=True)
    packs = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if (d / "ad.json").is_file():
            packs.append({"name": d.name, "has_preview": (d / "ad-preview.json").is_file(),
                          "has_script": (d / "0-scripts" / "ad-voice-script.txt").is_file(),
                          "has_voice": any((d / "2-audio").glob("scene-*.wav")) if (d / "2-audio").is_dir() else False})
    return packs

def import_ad_pack(project: Path, zip_path: Path) -> str:
    import zipfile
    root = project / "ads"; root.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith("ad.json") and "__MACOSX" not in n]
        if not names:
            raise JobError("This zip does not contain an ad.json file. Use an ad pack made for this app.")
        base = min(names, key=len)[: -len("ad.json")]
        name = safe_name(Path(base.rstrip("/")).name or zip_path.stem)
        dest = root / name
        shutil.rmtree(dest, ignore_errors=True)
        for n in z.namelist():
            if not n.startswith(base) or n.endswith("/"):
                continue
            rel = Path(n[len(base):])
            if ".." in rel.parts or rel.is_absolute():
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(n))
    return name

def run_ad(project: Path, opts: dict, settings: dict, log, step) -> Path:
    pack = project / "ads" / safe_name(opts.get("pack", ""))
    if not (pack / "ad.json").is_file():
        raise JobError("Choose an ad pack first.")
    preview = bool(opts.get("preview"))
    if opts.get("make_voice") and not preview:
        script = pack / "0-scripts" / "ad-voice-script.txt"
        if not script.is_file():
            raise JobError("This pack has no voice script (0-scripts/ad-voice-script.txt).")
        (pack / "2-audio").mkdir(exist_ok=True)
        log(f"Making the voice ({opts.get('voice', 'am_liam')})...")
        _run([_kokoro_python(settings), str(Path(__file__).with_name("voice_kokoro.py")), "--script", str(script),
              "--out", str(pack / "2-audio"), "--split", "--prefix", "scene", "--voice", opts.get("voice", "am_liam"),
              "--mode", opts.get("style", "energetic"), "--fresh", "--name", "adtmp"], log, what="voice", voice=opts.get("voice", "am_liam"))
    step()
    jf = "ad-preview.json" if preview and (pack / "ad-preview.json").is_file() else "ad.json"
    suffix = "-preview" if preview else ""
    vertical = opts.get("size") == "1080x1920"
    out = project / "out" / f"{pack.name}{suffix}{'-vertical' if vertical else ''}.mp4"
    cmd = [*tool_cmd("ad"), jf, "-o", str(out)]
    if opts.get("size"):
        cmd += ["--size", opts["size"]]
    if str(opts.get("scene") or "").strip():
        cmd += ["--scene", str(int(opts["scene"]))]
        out = out.with_name(out.stem + f"-scene{int(opts['scene'])}.mp4"); cmd[cmd.index("-o") + 1] = str(out)
    log("Rendering the ad...")
    _run(cmd, log, cwd=str(pack), what="ad")
    step()
    if not out.exists():
        raise JobError("The video was not created.")
    return out

# ----------------------------------------------------------------------------- editor
def media_info(path: Path) -> dict:
    import json as _json
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise JobError("Could not read that file.")
    d = _json.loads(r.stdout or "{}")
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    dur = float(d.get("format", {}).get("duration") or 0)
    return {"duration": round(dur, 3), "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "has_video": v is not None, "width": (v or {}).get("width"), "height": (v or {}).get("height")}

def _find_media(project: Path, ref: str) -> Path:
    for folder in ("out", "media", "audio", "images"):
        p = project / folder / safe_name(ref)
        if p.is_file():
            return p
    raise JobError(f"File not found: {ref}")

def run_edit(project: Path, spec: dict, log, step) -> Path:
    clips = spec.get("clips") or []
    if not clips:
        raise JobError("Add at least one clip to the timeline.")
    W, H = (int(x) for x in str(spec.get("size", "1920x1080")).split("x"))
    fps = int(spec.get("fps", 30))
    work = project / "work" / "edit"
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    inputs, fparts, concat, total = [], [], [], 0.0
    for i, c in enumerate(clips):
        src = _find_media(project, c.get("file", ""))
        info = media_info(src)
        start = max(0.0, float(c.get("start") or 0))
        end = float(c.get("end") or 0) or info["duration"]
        end = min(end, info["duration"]) if info["duration"] else end
        speed = min(4.0, max(0.25, float(c.get("speed") or 1)))
        if end - start < 0.1:
            raise JobError(f"Clip {i+1}: the end must be after the start.")
        dur = (end - start) / speed; total += dur
        inputs += ["-i", str(src)]
        if info["has_video"] and info["height"]:
            v = (f"[{i}:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{speed},"
                 f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps},format=yuv420p[v{i}]")
        else:  # a still image or audio-only: show a black frame
            v = f"color=c=black:s={W}x{H}:r={fps}:d={dur},format=yuv420p[v{i}]"
        if info["has_audio"]:
            tempo = []
            sp = speed
            while sp > 2.0: tempo.append("atempo=2.0"); sp /= 2.0
            while sp < 0.5: tempo.append("atempo=0.5"); sp /= 0.5
            tempo.append(f"atempo={sp}")
            a = f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,{','.join(tempo)},aresample=48000,aformat=channel_layouts=stereo[a{i}]"
        else:
            a = f"anullsrc=r=48000:cl=stereo,atrim=0:{dur},asetpts=PTS-STARTPTS[a{i}]"
        fparts += [v, a]; concat.append(f"[v{i}][a{i}]")
    fparts.append("".join(concat) + f"concat=n={len(clips)}:v=1:a=1[vc][ac]")
    vlabel = "vc"
    # captions / title text
    font = None
    ap = config.animator_path()
    for cand in ([ap / "fonts" / "Inter-ExtraBold.otf"] if ap else []) + [config.HERE / "fonts" / "Inter-ExtraBold.otf"]:
        if cand.is_file():
            font = cand; break
    texts = [t for t in (spec.get("texts") or []) if (t.get("text") or "").strip()]
    if texts and not font:
        raise JobError("The caption font was not found.")
    if texts:
        shutil.copyfile(font, work / "font.otf")
    for j, t in enumerate(texts):
        (work / f"t{j}.txt").write_text(t["text"].strip(), encoding="utf-8")
        s0 = float(t.get("start") or 0); e0 = float(t.get("end") or 0) or total
        pos = {"top": "y=h*0.08", "center": "y=(h-text_h)/2", "bottom": "y=h*0.82"}.get(t.get("position", "bottom"), "y=h*0.82")
        size = int(H * (0.075 if t.get("style") == "title" else 0.05))
        box = ":borderw=8:bordercolor=black@0.85" if t.get("style") == "title" else ":box=1:boxcolor=black@0.55:boxborderw=18"
        fparts.append(f"[{vlabel}]drawtext=fontfile=font.otf:textfile=t{j}.txt:fontcolor=white:fontsize={size}:x=(w-text_w)/2:{pos}{box}:"
                      f"enable='between(t,{s0},{e0})'[vt{j}]")
        vlabel = f"vt{j}"
    fi = float(spec.get("fade_in") or 0); fo = float(spec.get("fade_out") or 0)
    vf = []
    if fi > 0: vf.append(f"fade=t=in:st=0:d={fi}")
    if fo > 0: vf.append(f"fade=t=out:st={max(0, total - fo)}:d={fo}")
    if vf:
        fparts.append(f"[{vlabel}]{','.join(vf)}[vf]"); vlabel = "vf"
    alabel = "ac"
    af = []
    if fi > 0: af.append(f"afade=t=in:st=0:d={fi}")
    if fo > 0: af.append(f"afade=t=out:st={max(0, total - fo)}:d={fo}")
    if af:
        fparts.append(f"[ac]{','.join(af)}[af]"); alabel = "af"
    n_in = len(clips)
    tracks = []
    for k, tr in enumerate(spec.get("tracks") or []):
        src = _find_media(project, tr.get("file", ""))
        loop = ["-stream_loop", "-1"] if tr.get("kind") == "music" else []
        inputs += [*loop, "-i", str(src)]
        idx = n_in + k
        delay = int(float(tr.get("start") or 0) * 1000)
        vol = float(tr.get("volume", 0.3))
        fparts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={delay}|{delay},atrim=0:{total},asetpts=PTS-STARTPTS[m{k}]")
        tracks.append(f"[m{k}]")
    if tracks:
        fparts.append(f"[{alabel}]" + "".join(tracks) + f"amix=inputs={1+len(tracks)}:duration=first:dropout_transition=0,volume={1+len(tracks)}[aout]")
        alabel = "aout"
    out = project / "out" / (safe_name(spec.get("name") or "edited-video").removesuffix(".mp4") + ".mp4")
    (work / "graph.txt").write_text(";\n".join(fparts), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stats", *inputs, "-filter_complex_script", "graph.txt",
           "-map", f"[{vlabel}]", "-map", f"[{alabel}]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)]
    log(f"Exporting {len(clips)} clip(s), about {total:.1f} seconds...")
    _run(cmd, log, cwd=str(work), what="export")
    step()
    if not out.exists():
        raise JobError("The video was not created.")
    return out


# ----------------------------------------------------------------------------- language add-ons
def install_lang(lang: str, settings: dict, log, step=lambda: None, part: str = "") -> None:
    """Installs the extra Kokoro add-on for a language (Japanese, Mandarin) into the Kokoro python."""
    if lang not in friendly.LANG_NAMES or (lang not in friendly.LANG_PACKAGES and lang != "j"):
        raise JobError("That language does not need an add-on.")
    py = _kokoro_python(settings)
    pip = [py, "-m", "pip", "install", "--upgrade"]
    if lang == "j" and part == "dict":
        log("Downloading the Japanese dictionary (a large download, please keep this window open)...")
        _run([py, "-m", "unidic", "download"], log, what="step")
        step(); step()
        log("Done. You can listen to the voice again now.")
        return
    log(f"Installing {friendly.LANG_NAMES[lang]} support. This needs internet and can take a few minutes...")
    if lang == "j":
        try:   # no compiler needed: ready-made Windows files
            log("Step 1 of 3: the Japanese speech engine (ready-made version)...")
            _run([*pip, *friendly.JA_PREBUILT], log, what="step")
            log("Step 2 of 3: the other Japanese add-ons...")
            _run([*pip, *friendly.JA_REST], log, what="step")
        except JobError:
            log("The ready-made version could not be used. Trying the standard version (needs a C++ build tool)...")
            _run([*pip, *friendly.JA_COMPILED], log, what="step")
        step()
        log("Step 3 of 3: the Japanese dictionary (a large download, please wait)...")
        _run([py, "-m", "unidic", "download"], log, what="step")
    else:
        _run([*pip, *friendly.LANG_PACKAGES[lang]], log, what="step")
        step()
    log("Done. You can listen to the voice again now.")

# ----------------------------------------------------------------------------- deleting files
FOLDERS = {"out": "out", "media": "media", "audio": "audio", "images": "images"}

def delete_file(project: Path, folder: str, name: str) -> None:
    if folder not in FOLDERS:
        raise JobError("That kind of file cannot be deleted here.")
    p = project / FOLDERS[folder] / safe_name(name)
    if not p.is_file():
        raise JobError("That file is already gone.")
    try:
        p.unlink()
    except PermissionError:
        raise JobError("The file is open in another program. Close it and try again.")

def delete_pack(project: Path, name: str) -> None:
    d = project / "ads" / safe_name(name)
    if not (d / "ad.json").is_file():
        raise JobError("That ad is already gone.")
    shutil.rmtree(d, ignore_errors=True)

def clear_samples() -> int:
    d = config.data_dir() / "voice-samples"; n = 0
    if d.is_dir():
        for f in d.glob("*.wav"):
            f.unlink(missing_ok=True); n += 1
    return n
