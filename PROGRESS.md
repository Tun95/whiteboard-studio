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
- [x] 1b. Japanese install on Windows failed in real testing (pyopenjtalk has no prebuilt Windows wheel, pip tried to compile, no C++ compiler). Now installs `lemon-pyopenjtalk-prebuilt` (third-party ready-made build of the same module) + misaki, fugashi, jaconv, mojimoji, unidic, then `python -m unidic download`; falls back to `misaki[ja]` (needs Visual Studio Build Tools). Dependency resolution checked on Linux only; Windows wheels confirmed to exist on PyPI for cp312. Still needs a real Windows retest.
- [x] 1c. Real Windows test: Japanese add-on installed but fugashi uses the `unidic` package first (verified in fugashi source), and its dictionary was not downloaded -> "Failed initializing MeCab". Now detected: card offers "Download the Japanese dictionary" (`python -m unidic download`). Also: starting a second install while one runs no longer errors; the app names the running job and follows its progress. Needs a Windows retest.
- [x] 1d. Full unidic dictionary is a 526 MB download (user measured ~3 h at 48 kB/s). Japanese now uses `unidic-lite` (~47 MB from PyPI) and removes the `unidic` package + any partial folder (fugashi only falls back to unidic-lite on ImportError, so a leftover folder would crash it). Reproduced the user's exact MeCab error in a Linux venv and verified the app's fix repairs it. Japanese pronunciation quality with unidic-lite vs full unidic not compared; judge by ear.
- [x] 2. Delete/remove: Library (videos, uploads, audio, images), Editor media list, Ad packs, and saved voice samples. Always asks first. Deleting a file also removes scenes, clips and tracks that used it.
- [x] 3. Editor live preview: titles/captions, music, voice, per-clip sound, speed and fades all play in the preview before export (`tab-editor.js`, player `P`). Tested in headless Chromium with WebM clips (headless Chromium has no H.264); real MP4 playback is for the user's browser/window.
- [ ] 4. App ads: guided form (no ad.json, no zip packs)
- [x] 5. Editor redesign: dark workspace with media pool (drag onto timeline), live preview, inspector, timeline with ruler/playhead/zoom, tracks (Video, Text, Music/Voice), drag to reorder or trim, Cut here, undo/redo, shortcuts, Export dialog. Export now supports per-clip volume and auto-wrapped captions (same rule in preview and export); text size follows the shorter side so tall videos are readable.
  - Editor not done yet: images as clips, transitions between clips, audio waveforms, thumbnails on timeline clips, multiple video tracks, text animations.
- [ ] 6. Plain-language wording pass over the other tabs
- [x] 1e. Automatic voice setup: on start the app tests that Japanese and Mandarin really convert a word (`engine.language_ok`). If not, it installs/repairs them in the background (`State.check_setup`/`run_setup`, `/api/setup`) and shows a calm banner "Getting your voices ready (one time only)". Turn off with `"auto_setup": false` in settings.json. Offline -> friendly "No internet" card, retried at next start. Tested with fake misaki only; needs a real Windows run. Still to do: bundle the add-ons in the installer so even this step is unnecessary.
- [x] 3b. Editor round 2: pictures / logos / GIFs / watermarks on screen (`overlays`: file, start, end, x, y, w, opacity; drag to move, corner handles to resize, "Make it a watermark", 9-spot quick place, drop from the pool onto the preview or timeline); wheel on timeline zooms around the mouse (Shift+wheel = sideways, Alt+wheel = up/down); Ctrl+click multi-select, group move/remove, Ctrl+A; preview start is held until the video has loaded and play() now starts inside the click (could not reproduce the user's "won't start from 0" exactly; these are defensive fixes — ask the user to retest). Export: ffmpeg overlay chain (looped still / `-ignore_loop 0` GIF, alpha + opacity), checked by extracting frames. NOT done: dragging text on screen (text still uses Top/Middle/Bottom), animated WebP.
- [x] 3c. Editor fixes: ROOT CAUSE of "pause stops working / red bar frozen / music keeps looping": at Play the rAF timestamp can be slightly earlier than performance.now(), giving t = -0.01; `clipAt(-0.01)` returned -1 and `sync` threw, killing the tick loop and also `pause()` before it stopped the audio. Fixed: t clamped at 0, `clipAt` never returns -1, `pause()` stops all media FIRST, tick/sync wrapped so one hiccup can't freeze playback; start-wait only in the first 6 s (the earlier "hold" could also freeze the clock and make the music repeat). Random-action browser test (60 actions x3) now clean. Text can be dragged on the preview (`x`,`y` fractions; Where = "Where you dragged it"; export uses same spot). The user's 4th item ("preview video is cut at the ...") was truncated; frame fits stage at 1500x950 and 1280x640 — ask the user what was cut.
- [x] 3d. Editor: toolbar rebuilt as tidy pill groups (wraps cleanly, Export button separate); taller screen area (.ed height max(850px, 100vh-120px), preview row min 470px, narrower side panels so a wide video gets more width) — old layout let the middle row overflow the box when the toolbar wrapped, which cut the picture at the bottom; Copy / Paste buttons + Ctrl+C / Ctrl+X / Ctrl+V on the timeline (clips insert at the red line, text/pictures/audio keep their spacing starting at the red line; multi-select works; undo works). Tested at 1500x950, 1280x720, 1100x800.
