# long_voice.py - turns a script of ANY length (1 hour or more) into ONE audio file with Kokoro.
#
# Script file rules:
#   - Paragraphs are separated by a blank line (a longer pause is added between paragraphs).
#   - A line that contains only  [pause 2]  adds 2 seconds of silence (any number).
#   - Lines starting with # are notes for you and are NOT read.
# Optional pronounce.txt next to the script: one fix per line,  Nginx=engine-ex   (word=how it should sound)
#
# Safe for long jobs: every paragraph is saved as its own small file in a work folder.
# If the PC sleeps or you close the window, run the same command again and it continues where it stopped.
import argparse, os, re, sys, shutil, subprocess, time
import numpy as np
import soundfile as sf

SR = 24000
MODES = {   # speed, pause between sentences, pause between paragraphs, "!" boost, "?" boost
    "calm":      dict(speed=0.92, sent=0.45, para=1.10, bang=0.00, ask=0.00),
    "normal":    dict(speed=1.00, sent=0.30, para=0.80, bang=0.03, ask=0.00),
    "energetic": dict(speed=1.10, sent=0.14, para=0.50, bang=0.08, ask=0.03),
    "hype":      dict(speed=1.20, sent=0.08, para=0.40, bang=0.10, ask=0.05),
}

def split_sentences(t):
    return [p for p in re.split(r"(?<=[.!?])\s+", t.strip()) if p]

def load_fixes(path):
    fixes = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                a, b = line.split("=", 1)
                fixes.append((re.compile(r"\b" + re.escape(a.strip()) + r"\b", re.I), b.strip()))
    return fixes

def parse(text):
    """-> list of ('speak', text) or ('pause', seconds)"""
    items = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l for l in block.split("\n") if l.strip() and not l.strip().startswith("#")]
        speak = []
        for l in lines:
            m = re.fullmatch(r"\s*\[pause\s+([0-9.]+)\s*\]\s*", l, re.I)
            if m:
                if speak: items.append(("speak", " ".join(" ".join(speak).split()))); speak = []
                items.append(("pause", float(m.group(1))))
            else:
                speak.append(l.strip())
        if speak: items.append(("speak", " ".join(" ".join(speak).split())))
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--name", default="voiceover")
    ap.add_argument("--voice", default="am_liam")
    ap.add_argument("--lang", default=None, help="a US English, b UK English, e Spanish, f French, h Hindi, i Italian, j Japanese, p Portuguese(BR), z Mandarin")
    ap.add_argument("--mode", default="normal", choices=MODES)
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--split", action="store_true", help="one file per paragraph: PREFIX-01.wav, PREFIX-02.wav ... (for ads and manhwa)")
    ap.add_argument("--prefix", default="scene")
    ap.add_argument("--fresh", action="store_true", help="ignore saved progress and start again")
    a = ap.parse_args()

    from kokoro import KPipeline
    m = MODES[a.mode]; base = a.speed or m["speed"]
    lang = a.lang or ("b" if a.voice.startswith(("bf_", "bm_")) else a.voice[0])
    text = open(a.script, encoding="utf-8-sig").read()
    fixes = load_fixes(os.path.join(os.path.dirname(os.path.abspath(a.script)), "pronounce.txt"))
    items = parse(text)
    os.makedirs(a.out, exist_ok=True)
    work = os.path.join(a.out, a.name + "_parts")
    if a.fresh and os.path.isdir(work): shutil.rmtree(work)
    os.makedirs(work, exist_ok=True)
    pipe = KPipeline(lang_code=lang)
    total = len(items); t0 = time.time(); done_s = 0.0
    paths = []
    for i, (kind, val) in enumerate(items, 1):
        p = os.path.join(work, f"{i:05d}.wav"); paths.append((kind, p))
        if os.path.exists(p): continue
        if kind == "pause":
            sf.write(p, np.zeros(int(val * SR), dtype=np.float32), SR); continue
        pieces = []
        sents = split_sentences(val)
        for j, s in enumerate(sents):
            for rx, rep in fixes: s = rx.sub(rep, s)
            sp = base + (m["bang"] if s.endswith("!") else 0) + (m["ask"] if s.endswith("?") else 0)
            if a.mode == "energetic" and j % 2 == 1: sp += 0.03
            sp = max(0.7, min(1.4, sp))
            for _, _, audio in pipe(s, voice=a.voice, speed=sp):
                pieces.append(np.asarray(audio, dtype=np.float32))
            if j < len(sents) - 1: pieces.append(np.zeros(int(m["sent"] * SR), dtype=np.float32))
        clip = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
        tmp = p + ".tmp.wav"; sf.write(tmp, clip, SR); os.replace(tmp, p)
        done_s += len(clip) / SR
        el = time.time() - t0
        print(f"[{i}/{total}] {done_s/60:.1f} min of audio made, {el/60:.1f} min elapsed", flush=True)

    if a.split:
        n = 0
        for kind, p in paths:
            if kind != "speak": continue
            n += 1
            d, _ = sf.read(p, dtype="float32")
            pk = float(np.max(np.abs(d))) if len(d) else 1.0
            sf.write(os.path.join(a.out, f"{a.prefix}-{n:02d}.wav"), d * (0.89 / (pk or 1.0)), SR)
        print(f"Saved {n} files: {a.prefix}-01.wav ...")
        shutil.rmtree(work, ignore_errors=True)
        return
    # pass 1: find the loudest point so the whole file is levelled to about -1 dB
    peak = 0.0
    for _, p in paths:
        d, _ = sf.read(p, dtype="float32"); 
        if len(d): peak = max(peak, float(np.max(np.abs(d))))
    gain = 0.89 / (peak or 1.0)
    # pass 2: join everything, with the paragraph pause after each spoken paragraph
    final = os.path.join(a.out, a.name + ".wav")
    gap = np.zeros(int(m["para"] * SR), dtype=np.float32)
    with sf.SoundFile(final, "w", samplerate=SR, channels=1, subtype="PCM_16") as f:
        for kind, p in paths:
            d, _ = sf.read(p, dtype="float32"); f.write(d * gain)
            if kind == "speak": f.write(gap)
    info = sf.info(final)
    print(f"\nSaved {final}  ({info.duration/60:.1f} minutes)")
    ff = shutil.which("ffmpeg")
    if ff:
        mp3 = os.path.join(a.out, a.name + ".mp3")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", final, "-codec:a", "libmp3lame", "-b:a", "192k", mp3])
        if os.path.exists(mp3): print("Saved", mp3)
    else:
        print("ffmpeg not found: only the WAV was made (WAV is fine for clients).")
    print("You can delete the folder", work, "when you are happy with the result.")

if __name__ == "__main__":
    main()
