"""Tiny local web server: the app window is a web page served only to this computer (127.0.0.1)."""
from __future__ import annotations
import json, mimetypes, socket, threading, time, traceback, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from . import __version__, config, engine, friendly, voices

STATIC = Path(__file__).with_name("static")
MAX_UPLOAD = 500 * 1024 * 1024
KINDS = {"image": ({".png", ".jpg", ".jpeg"}, "images"), "audio": ({".wav", ".mp3", ".m4a", ".ogg", ".flac"}, "audio"),
         "video": ({".mp4", ".mov", ".mkv", ".webm"}, "media"), "adpack": ({".zip"}, "work")}

class State:
    def __init__(self):
        self.settings = config.load_settings()
        self.project = config.project_dir()
        (self.project / "media").mkdir(exist_ok=True)
        self.caps: dict | None = None
        self.setup = {"state": "checking", "job": None, "missing": []}
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self):
        self.caps = engine.capabilities(self.settings)
        self.check_setup()

    def check_setup(self, auto=True):
        """Quietly checks Japanese/Mandarin and fixes them in the background if needed (so users never see an install error)."""
        if not (self.caps and self.caps.get("kokoro")):
            self.setup = {"state": "no_voice", "job": None, "missing": []}; return
        miss = engine.missing_languages(self.settings)
        if not miss:
            self.setup = {"state": "ready", "job": None, "missing": []}; return
        self.setup = {"state": "needed", "job": None, "missing": miss}
        if auto and self.settings.get("auto_setup", True):
            self.run_setup()

    def run_setup(self):
        try:
            jid = self.start_job(2, lambda log, step: (engine.ensure_languages(self.settings, log, step), self.refresh_caps())[1],
                                 "getting your voices ready")
        except RuntimeError:
            return
        self.setup = {"state": "installing", "job": jid, "missing": self.setup.get("missing", [])}
        def watch():
            while self.jobs[jid]["status"] == "running":
                time.sleep(1)
            j = self.jobs[jid]
            self.setup = {"state": "ready" if j["status"] == "done" else "failed", "job": jid, "missing": [],
                          "info": j.get("error_info")}
        threading.Thread(target=watch, daemon=True).start()

    def refresh_caps(self):
        self.caps = engine.capabilities(self.settings)

    def start_job(self, total: int, fn, title: str = "a job") -> str:
        """fn(log, step) -> Path of the finished video."""
        with self.lock:
            busy = next((j for j in self.jobs.values() if j["status"] == "running"), None)
            if busy:
                err = RuntimeError(f"Something is still running: {busy.get('title', 'a job')}. Wait for it to finish; it can take several minutes.")
                err.running_id = busy["id"]
                raise err
            jid = uuid.uuid4().hex[:10]
            job = {"id": jid, "status": "running", "log": [], "done": 0, "total": max(1, total), "output": None, "error": None, "error_info": None, "title": title}
            self.jobs[jid] = job
        def log(line: str):
            job["log"].append(line); del job["log"][:-400]
        def step():
            job["done"] += 1
        def work():
            try:
                out = fn(log, step)
                job["output"] = out.name if out else None
                job["status"] = "done"
            except engine.JobError as e:
                job["error"] = str(e); job["error_info"] = e.info; job["status"] = "error"
            except Exception as e:
                tb = traceback.format_exc(); log(tb)
                info = friendly.explain(tb.splitlines(), "step"); job["error"] = info["title"] + ". " + info["what"]
                job["error_info"] = info; job["status"] = "error"
        threading.Thread(target=work, daemon=True).start()
        return jid

STATE: State | None = None

def library() -> dict:
    pr = STATE.project
    def files(folder, exts):
        d = pr / folder
        items = sorted((p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
        return [{"name": p.name, "size": p.stat().st_size, "folder": folder} for p in items]
    return {"videos": files("out", {".mp4"}), "uploads": files("media", KINDS["video"][0]),
            "audio": files("audio", KINDS["audio"][0]), "images": files("images", KINDS["image"][0]),
            "packs": engine.list_ad_packs(pr)}

class Handler(BaseHTTPRequestHandler):
    server_version = "WhiteboardWaveStudio/" + __version__
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        try:
            self.end_headers(); self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass   # the browser tab was closed or reloaded; nothing to report

    def _file(self, path: Path):
        if not path.is_file():
            return self._json({"error": "not found"}, 404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else 0; end = min(int(b) if b else size - 1, size - 1)
                if start > end: raise ValueError
                code = 206
            except ValueError:
                self.send_response(416); self.end_headers(); return
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1)); self.send_header("Cache-Control", "no-store")
        if code == 206: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk: break
                try: self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError): break
                left -= len(chunk)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD: raise ValueError("That file is too big (limit 500 MB).")
        return self.rfile.read(n)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = unquote(u.path)
        if p in ("/", "/index.html"): return self._file(STATIC / "index.html")
        if p.startswith("/static/"):
            f = (STATIC / p[len("/static/"):]).resolve()
            return self._file(f) if STATIC.resolve() in f.parents else self._json({"error": "not found"}, 404)
        if p == "/api/state":
            s = STATE.settings
            return self._json({"version": __version__, "caps": STATE.caps, "voices": voices.library(), "styles": engine.STYLES,
                               "donate_url": s.get("donate_url", ""), "donate_text": s.get("donate_text", ""),
                               "data_dir": str(config.data_dir())})
        if p == "/api/setup": return self._json(STATE.setup)
        if p == "/api/project":
            f = STATE.project / "project.json"; data = {}
            if f.exists():
                try: data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError): pass
            return self._json(data)
        if p == "/api/library": return self._json(library())
        if p == "/api/media/info":
            try: return self._json(engine.media_info(engine._find_media(STATE.project, (q.get("file") or [""])[0])))
            except engine.JobError as e: return self._json({"error": str(e)}, 400)
        if p == "/api/job":
            job = STATE.jobs.get((q.get("id") or [""])[0])
            return self._json(job or {"error": "unknown job"}, 200 if job else 404)
        if p.startswith("/files/"):
            parts = p[len("/files/"):].split("/", 1)
            if len(parts) == 2 and parts[0] in ("images", "audio", "out", "media"):
                return self._file(STATE.project / parts[0] / engine.safe_name(parts[1]))
            if len(parts) == 2 and parts[0] == "samples":
                return self._file(config.data_dir() / "voice-samples" / engine.safe_name(parts[1]))
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path; S = STATE
        try:
            if p == "/api/upload":
                kind = (q.get("kind") or [""])[0]
                name = engine.safe_name((q.get("name") or ["file"])[0]); ext = Path(name).suffix.lower()
                exts, folder_name = KINDS.get(kind, (set(), ""))
                if ext not in exts:
                    return self._json({"error": f"Unsupported file type {ext or '(none)'}. Allowed: {', '.join(sorted(exts))}"}, 400)
                data = self._body(); folder = S.project / folder_name; folder.mkdir(exist_ok=True)
                dest = folder / name; i = 1
                while dest.exists():
                    dest = folder / f"{Path(name).stem}-{i}{ext}"; i += 1
                dest.write_bytes(data)
                if kind == "adpack":
                    try: pack = engine.import_ad_pack(S.project, dest)
                    finally: dest.unlink(missing_ok=True)
                    return self._json({"pack": pack})
                return self._json({"name": dest.name})
            body = json.loads(self._body() or b"{}")
            if p == "/api/project":
                (S.project / "project.json").write_text(json.dumps(body, indent=2), encoding="utf-8"); return self._json({"ok": True})
            if p == "/api/render":
                sc, op = body.get("scenes", []), body.get("opts", {})
                return self._json({"id": S.start_job(len(sc) + 1, lambda log, step: engine.run_job(S.project, sc, op, S.settings, log, step))})
            if p == "/api/manhwa/render":
                sc, op = body.get("panels", []), body.get("opts", {})
                return self._json({"id": S.start_job(len(sc) + 1, lambda log, step: engine.run_manhwa(S.project, sc, op, S.settings, log, step))})
            if p == "/api/ads/render":
                return self._json({"id": S.start_job(2, lambda log, step: engine.run_ad(S.project, body, S.settings, log, step))})
            if p == "/api/edit/render":
                return self._json({"id": S.start_job(1, lambda log, step: engine.run_edit(S.project, body, log, step))})
            if p == "/api/setup/run":
                S.run_setup(); return self._json(S.setup)
            if p == "/api/voice/install":
                lang = str(body.get("lang", ""))
                return self._json({"id": S.start_job(2, lambda log, step: (engine.install_lang(lang, S.settings, log, step, str(body.get("part", ""))), S.refresh_caps())[1],
                                                  "installing " + friendly.LANG_NAMES.get(lang, lang) + " voice support")})
            if p == "/api/delete":
                engine.delete_file(S.project, str(body.get("folder", "")), str(body.get("name", ""))); return self._json({"ok": True})
            if p == "/api/ads/delete":
                engine.delete_pack(S.project, str(body.get("name", ""))); return self._json({"ok": True})
            if p == "/api/voice/clear":
                return self._json({"removed": engine.clear_samples()})
            if p == "/api/voice/sample":
                if S.caps is not None and not S.caps.get("kokoro"):
                    return self._json({"error": "Kokoro is not installed on this computer, so voices cannot be previewed yet."}, 400)
                out = engine.voice_sample(body.get("voice", ""), body.get("text", ""), S.settings)
                return self._json({"url": "/files/samples/" + out.name})
        except ValueError as e: return self._json({"error": str(e)}, 400)
        except engine.JobError as e: return self._json({"error": str(e), "info": e.info}, 400)
        except RuntimeError as e: return self._json({"error": str(e), "running_id": getattr(e, "running_id", None)}, 409)
        return self._json({"error": "not found"}, 404)

def free_port(preferred=8765) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 30)]:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0: return port
    raise RuntimeError("No free port found.")

def serve(open_browser=True, port: int | None = None):
    global STATE
    STATE = State(); port = port or free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"{config.APP_NAME} is running at {url}\nKeep this window open. Press Ctrl+C to stop.")
    if open_browser: threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
