"""Tiny local web server: the app window is a web page served only to this computer (127.0.0.1)."""
from __future__ import annotations
import json, mimetypes, os, socket, threading, time, traceback, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from . import __version__, config, engine

STATIC = Path(__file__).with_name("static")
MAX_UPLOAD = 300 * 1024 * 1024
IMAGE_EXT = {".png", ".jpg", ".jpeg"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}

class State:
    def __init__(self):
        self.settings = config.load_settings()
        self.project = config.project_dir()
        self.caps: dict | None = None
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self):
        self.caps = engine.capabilities(self.settings)

    def start_job(self, scenes: list[dict], opts: dict) -> str:
        with self.lock:
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise RuntimeError("A video is already being made. Wait for it to finish.")
            jid = uuid.uuid4().hex[:10]
            total = len(scenes) + 1
            job = {"id": jid, "status": "running", "log": [], "done": 0, "total": total, "output": None, "error": None}
            self.jobs[jid] = job
        def log(line: str):
            job["log"].append(line)
            del job["log"][:-400]
        def step():
            job["done"] += 1
        def work():
            try:
                out = engine.run_job(self.project, scenes, opts, self.settings, log, step)
                job["output"] = out.name
                job["status"] = "done"
            except engine.JobError as e:
                job["error"] = str(e); job["status"] = "error"
            except Exception as e:  # unexpected
                log(traceback.format_exc())
                job["error"] = f"Unexpected problem: {e}"; job["status"] = "error"
        threading.Thread(target=work, daemon=True).start()
        return jid

STATE: State | None = None

class Handler(BaseHTTPRequestHandler):
    server_version = "WhiteboardWaveStudio/" + __version__

    def log_message(self, *a):  # keep the console quiet
        pass

    # ---- helpers
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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
                start = int(a) if a else 0
                end = int(b) if b else size - 1
                end = min(end, size - 1)
                if start > end:
                    raise ValueError
                code = 206
            except ValueError:
                self.send_response(416); self.end_headers(); return
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                left -= len(chunk)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ValueError("That file is too big (limit 300 MB).")
        return self.rfile.read(n)

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = unquote(u.path)
        if p in ("/", "/index.html"):
            return self._file(STATIC / "index.html")
        if p.startswith("/static/"):
            f = (STATIC / p[len("/static/"):]).resolve()
            if STATIC.resolve() in f.parents:
                return self._file(f)
            return self._json({"error": "not found"}, 404)
        if p == "/api/state":
            s = STATE.settings
            return self._json({"version": __version__, "caps": STATE.caps, "voices": engine.VOICES,
                               "styles": engine.STYLES, "donate_url": s.get("donate_url", ""),
                               "donate_text": s.get("donate_text", ""), "data_dir": str(config.data_dir())})
        if p == "/api/project":
            f = STATE.project / "project.json"
            data = {"scenes": [], "opts": {}}
            if f.exists():
                try: data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError): pass
            return self._json(data)
        if p == "/api/job":
            job = STATE.jobs.get((q.get("id") or [""])[0])
            return self._json(job or {"error": "unknown job"}, 200 if job else 404)
        if p.startswith("/files/"):
            parts = p[len("/files/"):].split("/", 1)
            if len(parts) == 2 and parts[0] in ("images", "audio", "out"):
                return self._file(STATE.project / parts[0] / engine.safe_name(parts[1]))
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path
        try:
            if p == "/api/upload":
                kind = (q.get("kind") or [""])[0]
                name = engine.safe_name((q.get("name") or ["file"])[0])
                ext = Path(name).suffix.lower()
                allowed = IMAGE_EXT if kind == "image" else AUDIO_EXT if kind == "audio" else set()
                if ext not in allowed:
                    return self._json({"error": f"Unsupported file type {ext or '(none)'}. Allowed: {', '.join(sorted(allowed))}"}, 400)
                data = self._body()
                folder = STATE.project / ("images" if kind == "image" else "audio")
                dest = folder / name
                i = 1
                while dest.exists():
                    dest = folder / f"{Path(name).stem}-{i}{ext}"; i += 1
                dest.write_bytes(data)
                return self._json({"name": dest.name})
            if p == "/api/project":
                data = json.loads(self._body() or b"{}")
                (STATE.project / "project.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
                return self._json({"ok": True})
            if p == "/api/render":
                data = json.loads(self._body() or b"{}")
                return self._json({"id": STATE.start_job(data.get("scenes", []), data.get("opts", {}))})
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except RuntimeError as e:
            return self._json({"error": str(e)}, 409)
        return self._json({"error": "not found"}, 404)

def free_port(preferred=8765) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 30)]:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port found.")

def serve(open_browser=True, port: int | None = None):
    global STATE
    STATE = State()
    port = port or free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"{config.APP_NAME} is running at {url}\nKeep this window open. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
