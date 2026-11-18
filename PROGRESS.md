# Whiteboard Wave Studio: progress and next steps

Goal: a FREE Windows app (with a Donate button) that turns scripts + images into whiteboard videos.
Built from `whiteboard-animator` (MIT) + Kokoro voice. Owner: Akande Tunji.

## Design decisions
- The window is a local web page (`studio/static/index.html`) served only to this computer by `studio/server.py`
  (stdlib only). Reason: it can be fully tested in the cloud workspace, no window toolkit needed.
- `studio/engine.py` runs Kokoro (`studio/voice_kokoro.py`) and the animator as separate steps.
- Installer v1 = animator + UI + FFmpeg only (small). Kokoro/PyTorch is an optional add-on: set `kokoro_python`
  in `Documents\WhiteboardWaveStudio\settings.json`, or it auto-finds `Desktop\White Board Animation\_Tools\kokoro\kokoro-env`.
- Donate link: `donate_url` in settings.json (empty = "coming soon"). Need the user's donation page link.

## Done and tested here
- [x] Server + UI: add scenes, scripts, voice mode (none / Kokoro / own recording), settings, Make video, preview, download.
- [x] No-voice render end to end (browser -> MP4).
- [x] Voice render end to end with a FAKE Kokoro (tests/stubs): audio + video in the MP4.
- [x] Packaged-app hook: `run_studio.py --run-animator` (a frozen .exe cannot use `python -m`).

## Not done / not tested
- [ ] Real Kokoro voice from the app (test on the user's PC).
- [ ] Windows build: `.github/workflows/build-windows.yml` + `packaging/installer.iss` are written but never run.
- [ ] Windows test of the installer on a clean PC.
- [ ] Donate link, app icon, version/updates, error screens for missing ffmpeg.
- [ ] Per-scene options (camera files, effects JSON), project save/load of several projects.
- [ ] Move `whiteboard-animator/.github/workflows/test.yml` to the repo root if wanted.

## Run it (dev)
    python run_studio.py                       # opens the browser
    set PYTHONPATH=whiteboard-animator         # Windows, if the animator is not pip-installed
