"""Turns raw technical failures into plain-language help that anyone can understand."""
from __future__ import annotations
import re

LANG_NAMES = {"j": "Japanese", "z": "Mandarin Chinese"}
JA_MODS = ("pyopenjtalk", "fugashi", "unidic", "jaconv", "mojimoji", "cutlet", "misaki.ja", "misaki[ja]")
ZH_MODS = ("jieba", "pypinyin", "cn2an", "ordered_set", "ordered-set", "pypinyin_dict", "misaki.zh", "misaki[zh]")

def _help(title, explain, fix, details, action=None):
    return {"title": title, "explain": explain, "fix": fix, "action": action, "details": (details or "")[-3500:]}

def explain(raw: str, what: str = "video") -> dict:
    """what: voice | video | ad | edit | install"""
    t = raw or ""
    low = t.lower()
    m = re.search(r"STUDIO_ERROR:LANGPACK:([jz])", t)
    lang = m.group(1) if m else None
    if not lang:
        if any(x in low for x in ("pip install misaki[ja]", *[f"no module named '{x}" for x in JA_MODS])):
            lang = "j"
        elif any(x in low for x in ("pip install misaki[zh]", *[f"no module named '{x}" for x in ZH_MODS])):
            lang = "z"
    if lang:
        n = LANG_NAMES[lang]
        return _help(f"{n} voices need a one-time download",
                     f"The {n} voices need an extra add-on that is not on this computer yet. This is normal and only needed once.",
                     "Click the button below. It needs an internet connection and can take a few minutes.", t,
                     {"type": "install_lang", "lang": lang, "label": f"Install {n} voice support"})
    if "no module named 'kokoro'" in low or "no module named 'soundfile'" in low or "no module named 'torch'" in low:
        return _help("The AI voice is not set up on this computer",
                     "The part of the app that creates AI voices is missing.",
                     "You can still use your own recording for the voice, or choose “No voice”.", t)
    if any(x in low for x in ("huggingface", "max retries", "connection error", "connectionerror", "getaddrinfo", "timed out", "name resolution")):
        return _help("The app needs the internet for a moment",
                     "It tried to download something (such as a voice) and could not reach the internet.",
                     "Check your internet connection and try again.", t)
    if any(x in low for x in ("out of memory", "memoryerror", "cannot allocate", "bad_alloc")):
        return _help("Your computer ran out of memory",
                     "This job is too big for the free memory your computer has right now.",
                     "Close other programs, choose a smaller video size, or make fewer scenes at a time.", t)
    if "permission denied" in low or "being used by another process" in low:
        return _help("A file is open in another program",
                     "The app could not save because the file is being used somewhere else.",
                     "Close the video or audio player that has the file open, then try again.", t)
    if any(x in low for x in ("invalid data found", "moov atom not found", "error opening input", "does not contain any stream", "could not find codec", "conversion failed")):
        return _help("One of your files could not be read",
                     "A video or audio file looks damaged, or it is in a format the app cannot open.",
                     "Try a different file, or save it again as MP4 (video) or MP3 or WAV (audio).", t)
    if "no space left" in low or "disk full" in low:
        return _help("Your computer is full",
                     "There is no free space left to save this file.",
                     "Free up some space on your drive, then try again.", t)
    if "filenotfounderror" in low or "no such file" in low or "cannot find the file" in low:
        return _help("A file is missing",
                     "The app could not find a file it needs. It may have been moved or deleted.",
                     "Add the picture or audio again, then try again.", t)
    verb = {"voice": "making the voice", "ad": "making the ad", "edit": "exporting your video", "install": "installing"}.get(what, "making your video")
    return _help(f"Something went wrong while {verb}",
                 "The app could not finish this step. Your files are safe.",
                 "Try again. If it keeps happening, open “Technical details”, copy them, and send them to support.", t)
