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

## Phase 2 (done, tested here with fake Kokoro)
- [x] Sidebar app with tabs: Home, Whiteboard video, Voices, App ads, Manhwa recap, Editor, Library; Donate button last in the sidebar.
- [x] Voices tab: 54 Kokoro voices, search/filter, Listen (cached samples), set default voice; Listen button next to every voice choice.
- [x] Editor: clips timeline, trim (set start/end from preview), speed, join, titles/captions, music/voice tracks, fades, size, export (ffmpeg).
- [x] Manhwa tab (wraps manhwa_panels.py) and App ads tab (import ad pack .zip, make voice from pack script, preview, vertical, single scene).
- [ ] Voice ids are from memory of Kokoro v1.0: if a Listen fails for a voice, the id may not exist in the user's version.
- [ ] Non-English voices may need extra Kokoro language packages.
- [ ] App ads: guided builder (no hand-editing ad.json) is the next big feature.
- [ ] Donate link still needed from the user (settings.json donate_url).

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
- [x] Backend: voice library/samples, manhwa runner, ad-pack runner, editor (ffmpeg) tested. UI tabs: in progress

## Phase 2a (done): friendly errors, JA/ZH language packs, delete
- studio/errors.py explains failures in plain language; jobs carry `help`; UI shows problem card with copyable technical details.
- Japanese/Mandarin: voice_kokoro prints STUDIO_ERROR:LANGPACK; one-click install (misaki[ja]/[zh], unidic) via /api/voice/install-language. Untested against real Kokoro (sandbox has none) — if still failing, ask user for "Technical details".
- Delete: /api/delete; buttons in Library, ad packs, Voices (clear samples).
## Next: Editor rewrite (live preview timeline), App Ads guided wizard, plain-language pass, donate link, installer build.
