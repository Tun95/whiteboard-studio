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

## Phase 3: fixes after user testing (branch studio-fixes)
- [x] 1. Plain-language errors: `studio/friendly.py` turns technical failures into a headline, a plain explanation, what to do, and an optional button. Technical text is hidden under "Technical details" with a Copy button. Japanese / Mandarin voices: the cause is a missing Kokoro language add-on, so the error offers "Install Japanese/Mandarin support" (runs pip for `misaki[ja]` / `misaki[zh]` in the Kokoro python). NOT verified against real Kokoro: only tested with a fake pip and a fake Kokoro. Other languages (Spanish, French, Hindi, Italian, Portuguese) likely need eSpeak NG: the error says so but there is no install button.
- [x] 2. Delete/remove: Library (videos, uploads, audio, images), Editor media list, Ad packs, and saved voice samples. Always asks first. Deleting a file also removes scenes, clips and tracks that used it.
- [ ] 3. Editor: live preview of titles, captions, music and voices before export
- [ ] 4. App ads: guided form (no ad.json, no zip packs)
- [ ] 5. Editor redesign (DaVinci-style: media pool, preview, timeline with tracks)
- [ ] 6. Plain-language wording pass over the other tabs
