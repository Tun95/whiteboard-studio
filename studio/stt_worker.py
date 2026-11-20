"""Runs INSIDE the transcription add-on environment (not the main app).

  transcribe: speech -> text with faster-whisper (open source, MIT licence, runs fully offline after the first model download)
  export:     writes a Word (.docx) or PDF file from a transcript
"""
import argparse, json, os, sys, unicodedata

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def load_wav(path):
    """Reads the 16 kHz mono sound file ourselves, so the speech engine never has to use its own video library
    (some computers have an older one that crashes with: open() got an unexpected keyword argument 'metadata_errors')."""
    import wave
    import numpy as np
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise RuntimeError("Unexpected sound format")
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != 16000 and len(x):
        t = np.linspace(0, len(x) - 1, int(len(x) * 16000 / rate))
        x = np.interp(t, np.arange(len(x)), x).astype("float32")
    return x


def cmd_transcribe(a):
    from faster_whisper import WhisperModel
    print("Loading the speech model. The first time, this downloads it: please wait...", flush=True)
    threads = min(8, max(2, (os.cpu_count() or 4) - 1))
    model = WhisperModel(a.model, device="cpu", compute_type="int8", download_root=a.models_dir, cpu_threads=threads)
    print("MODEL_READY", flush=True)
    segments, info = model.transcribe(load_wav(a.audio), language=a.language or None, task=a.task, beam_size=5,
                                      vad_filter=True, condition_on_previous_text=False)
    dur = float(info.duration or 0)
    print(f"LANGUAGE {info.language} {float(info.language_probability):.2f}", flush=True)
    out = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            out.append({"start": round(float(seg.start), 2), "end": round(float(seg.end), 2), "text": text})
        if dur:
            print(f"PROGRESS {min(1.0, float(seg.end) / dur):.3f}", flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"language": info.language, "duration": dur, "segments": out}, f, ensure_ascii=False, indent=1)
    print(f"Done: {len(out)} pieces of text.", flush=True)


# ------------------------------------------------------------------ export
def _norm(t):
    return unicodedata.normalize("NFC", t)

def export_docx(d, out):
    from docx import Document
    from docx.shared import Pt, RGBColor
    doc = Document()
    doc.add_heading(_norm(d["title"]), level=1)
    if d.get("meta"):
        p = doc.add_paragraph(); r = p.add_run(_norm(d["meta"])); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    for label, text in d["blocks"]:
        p = doc.add_paragraph()
        if label:
            r = p.add_run(f"[{label}]  "); r.bold = True; r.font.color.rgb = RGBColor(0x1F, 0x6F, 0x8B)
        p.add_run(_norm(text))
    doc.save(out)

_FONTS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),   # free font shipped with the app (no licence limits)
    r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
]

def _scripts(text):
    cjk = kana = hangul = other = False
    for c in text:
        o = ord(c)
        if 0x3040 <= o <= 0x30FF: kana = True
        elif 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF: hangul = True
        elif 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF: cjk = True
    return cjk, kana, hangul

def export_pdf(d, out):
    from xml.sax.saxutils import escape
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    title = _norm(d["title"]); blocks = [(l, _norm(t)) for l, t in d["blocks"]]
    alltext = title + " " + (d.get("meta") or "") + " " + " ".join(t for _, t in blocks)
    cjk, kana, hangul = _scripts(alltext)
    font = None
    if cjk or kana or hangul:   # Japanese, Chinese, Korean: built-in PDF fonts (the PDF viewer supplies the glyphs)
        name = "HeiseiMin-W3" if kana else "HYSMyeongJo-Medium" if hangul else "STSong-Light"
        pdfmetrics.registerFont(UnicodeCIDFont(name)); font = name
    else:
        for path in _FONTS:
            if os.path.isfile(path):
                try:
                    f = TTFont("DocFont", path); pdfmetrics.registerFont(f)
                except Exception:
                    continue
                missing = {c for c in alltext if not c.isspace() and c.isprintable() and ord(c) not in f.face.charToGlyph}
                if missing:
                    print("ERROR_PDF_SCRIPT " + "".join(sorted(missing))[:40], flush=True); sys.exit(3)
                font = "DocFont"; break
        if not font:
            if all(ord(c) < 256 for c in alltext):
                font = "Helvetica"
            else:
                print("ERROR_PDF_FONT", flush=True); sys.exit(4)
    body = ParagraphStyle("b", fontName=font, fontSize=11, leading=16, spaceAfter=7)
    head = ParagraphStyle("h", fontName=font, fontSize=18, leading=22, spaceAfter=6)
    meta = ParagraphStyle("m", fontName=font, fontSize=9, leading=12, textColor="#666666", spaceAfter=12)
    story = [Paragraph(escape(title), head)]
    if d.get("meta"): story.append(Paragraph(escape(_norm(d["meta"])), meta))
    for label, text in blocks:
        t = escape(text).replace("\n", "<br/>")
        story.append(Paragraph((f'<font color="#1F6F8B">[{escape(label)}]</font>&nbsp;&nbsp;' if label else "") + t, body))
    SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm, title=title).build(story)

def cmd_export(a):
    d = json.load(open(a.inp, encoding="utf-8"))
    (export_docx if a.format == "docx" else export_pdf)(d, a.out)
    print("Saved " + a.out, flush=True)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe"); t.add_argument("--audio", required=True); t.add_argument("--model", default="small")
    t.add_argument("--models-dir", required=True); t.add_argument("--out", required=True)
    t.add_argument("--language", default=""); t.add_argument("--task", default="transcribe", choices=["transcribe", "translate"])
    e = sub.add_parser("export"); e.add_argument("--in", dest="inp", required=True); e.add_argument("--format", required=True, choices=["docx", "pdf"]); e.add_argument("--out", required=True)
    a = ap.parse_args()
    cmd_transcribe(a) if a.cmd == "transcribe" else cmd_export(a)

if __name__ == "__main__":
    main()
