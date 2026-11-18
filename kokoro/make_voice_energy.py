# make_voice_energy.py  -  Kokoro voice-over with an "energy" mode (calm / normal / energetic)
#
# Usage (run with the Kokoro Python, from the folder that holds your script file):
#   python make_voice_energy.py --script script.txt --out ..\2-audio\ad-energetic --voice am_puck --mode energetic
#
# script.txt: one scene per block, scenes separated by a blank line.
# Writes intro-01.wav, intro-02.wav ... (or use --prefix scene)
import argparse, os, re
import numpy as np
import soundfile as sf
from kokoro import KPipeline

MODES = {   # speed, pause between sentences (seconds), "!" speed boost, "?" speed boost
    "calm":      dict(speed=0.92, pause=0.45, bang=0.00, ask=0.00),
    "normal":    dict(speed=1.00, pause=0.30, bang=0.03, ask=0.00),
    "energetic": dict(speed=1.10, pause=0.14, bang=0.08, ask=0.03),
    "hype":      dict(speed=1.20, pause=0.08, bang=0.10, ask=0.05),   # adverts, launches, big announcements
}
SR = 24000

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="am_puck")
    ap.add_argument("--lang", default=None, help="a = American, b = British (default: from voice name)")
    ap.add_argument("--mode", default="normal", choices=MODES)
    ap.add_argument("--speed", type=float, default=None, help="override the mode's base speed")
    ap.add_argument("--prefix", default="intro")
    ap.add_argument("--tail", type=float, default=0.5, help="silence at the end of each clip")
    a = ap.parse_args()

    m = MODES[a.mode]
    base = a.speed if a.speed else m["speed"]
    lang = a.lang or ("b" if a.voice.startswith(("bf_", "bm_")) else "a")
    text = open(a.script, encoding="utf-8-sig").read().replace("\r\n", "\n")
    scenes = [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]
    os.makedirs(a.out, exist_ok=True)
    pipe = KPipeline(lang_code=lang)

    for i, scene in enumerate(scenes, 1):
        scene = " ".join(scene.split())
        pieces = []
        sents = split_sentences(scene)
        for j, s in enumerate(sents):
            sp = base
            if s.endswith("!"): sp += m["bang"]
            if s.endswith("?"): sp += m["ask"]
            if a.mode in ("energetic", "hype") and j % 2 == 1:
                sp += 0.03                      # small speed variation so it never sounds like a metronome
            sp = max(0.7, min(1.4, sp))
            for _, _, audio in pipe(s, voice=a.voice, speed=sp):
                pieces.append(np.asarray(audio, dtype=np.float32))
            if j < len(sents) - 1:
                pieces.append(np.zeros(int(m["pause"] * SR), dtype=np.float32))
        pieces.append(np.zeros(int(a.tail * SR), dtype=np.float32))
        clip = np.concatenate(pieces)
        peak = float(np.max(np.abs(clip))) or 1.0
        clip = clip * (0.89 / peak)          # level every clip to about -1 dB
        path = os.path.join(a.out, f"{a.prefix}-{i:02d}.wav")
        sf.write(path, clip, SR)
        print("saved", path, f"({len(clip)/SR:.1f}s)")

if __name__ == "__main__":
    main()
