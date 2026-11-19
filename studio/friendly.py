"""Turns technical failures into plain-language messages anyone can understand.

explain(lines, what) -> {"title", "what", "fix", "action", "details"}
  title   short headline
  what    one or two plain sentences: what went wrong
  fix     what the person can do next
  action  optional button the app can offer, e.g. {"type": "install_lang", "lang": "j", "label": "..."}
  details the technical text (hidden by default, can be copied and sent to the developer)
"""
from __future__ import annotations
import re

LANG_NAMES = {"j": "Japanese", "z": "Mandarin Chinese", "h": "Hindi", "e": "Spanish", "f": "French",
              "i": "Italian", "p": "Portuguese"}
# pip packages that add a language to Kokoro (names follow the "misaki" language add-ons)
LANG_PACKAGES = {"z": ["misaki[zh]"]}
# Japanese: the official "pyopenjtalk" has NO prebuilt Windows download (PyPI ships source only), so pip tries to
# compile it and fails on PCs without a C++ compiler. "lemon-pyopenjtalk-prebuilt" is a third-party build of the same
# module with ready-made Windows wheels, so we install that first and the other add-ons without the [ja] shortcut.
JA_PREBUILT = ["lemon-pyopenjtalk-prebuilt"]
# The full "unidic" dictionary is a 526 MB download (very slow on some connections). The small "unidic-lite" (about 47 MB,
# from PyPI) works with misaki and loads automatically ONLY if the full "unidic" package is not installed (fugashi tries
# unidic first), so the install removes unidic.
JA_REST = ["misaki", "fugashi", "jaconv", "mojimoji", "unidic-lite"]
JA_COMPILED = ["misaki[ja]"]   # fallback: needs a C++ compiler
LANG_MODULES = {
    "j": ("pyopenjtalk", "fugashi", "unidic", "jaconv", "mojimoji", "cutlet", "mecab"),
    "z": ("jieba", "pypinyin", "cn2an", "ordered_set", "ordered-set", "pypinyin_dict"),
}
WHAT = {"voice": "making the voice", "video": "drawing the video", "ad": "making the ad",
        "export": "exporting the video", "manhwa": "building the manhwa video", "step": "running a step"}

def _tail(lines, n=40):
    return "\n".join(lines[-n:])

def explain(lines: list[str], what: str = "step", voice: str = "") -> dict:
    text = "\n".join(lines)
    low = text.lower()
    doing = WHAT.get(what, WHAT["step"])
    details = _tail(lines)
    lang = voice[:1] if voice[:1] in LANG_NAMES else ""

    def out(title, what_, fix, action=None):
        return {"title": title, "what": what_, "fix": fix, "action": action, "details": details}

    # 0) Japanese add-on is installed but its dictionary is missing (real error seen on Windows)
    if "failed initializing mecab" in low or "mecabrc" in low or ("unidic" in low and "dicdir" in low):
        return out("The Japanese dictionary is missing",
                   "The Japanese add-on is installed, but the dictionary file it needs is missing. The full dictionary is a very large "
                   "download (526 MB). A smaller dictionary (about 47 MB) works too.",
                   "Click “Install the small Japanese dictionary”. It takes a minute or two. Then listen to the voice again.",
                   {"type": "install_lang", "lang": "j", "part": "lite", "label": "Install the small Japanese dictionary"})
    # 1) a language add-on is missing (Japanese, Mandarin)
    m = re.search(r"no module named ['\"]?([\w\.\-]+)", low)
    missing = m.group(1).split(".")[0] if m else ""
    for code, mods in LANG_MODULES.items():
        if missing in mods or (lang == code and ("modulenotfounderror" in low or "importerror" in low)):
            name = LANG_NAMES[code]
            return out(f"{name} voices need an extra add-on",
                       f"The {name} voice add-on is not installed on this computer yet, so the voice could not be made.",
                       f"Click “Install {name} support”. It downloads a small add-on (you need internet, and it can take a few minutes). Then try again.",
                       {"type": "install_lang", "lang": code, "label": f"Install {name} support"})
    # 1b) pip tried to build software from source and this PC has no C++ compiler
    if any(k in low for k in ("no cmake_c_compiler", "no cmake_cxx_compiler", "microsoft visual c++", "vcvarsall", "cl.exe",
                              "failed building wheel", "getting requirements to build wheel", "building wheel for")):
        return out("This add-on needs a build tool that is not on your computer",
                   "The add-on had to be built on your PC, and that needs Microsoft’s free C++ build tools, which are not installed. "
                   "This is a Windows setup issue, not a problem with your files.",
                   "Easiest fix: install “Build Tools for Visual Studio” from visualstudio.microsoft.com/downloads (scroll to “All downloads” → "
                   "“Build Tools”), tick “Desktop development with C++”, finish the install, restart this app, and click Install again. "
                   "It is a big download (several GB).")
    # 2) the voice or its model needs a download and there is no internet
    if any(k in low for k in ("max retries", "connectionerror", "urlopen error", "getaddrinfo", "huggingface", "name resolution", "nameresolution", "failed to resolve", "timed out")):
        return out("No internet connection",
                   "The voice needs to download a file the first time you use it, but the internet could not be reached.",
                   "Connect to the internet, then try again. After the first download it works offline.")
    # 3) espeak (Spanish, French, Hindi, Italian, Portuguese)
    if "espeak" in low:
        name = LANG_NAMES.get(lang, "this language")
        return out(f"{name} voices need extra speech software",
                   f"Voices for {name} need a free helper program called eSpeak NG, which is not installed on this computer.",
                   "Install eSpeak NG from github.com/espeak-ng/espeak-ng/releases (download the .msi file and run it), then restart this app and try again.")
    # 4) the chosen voice does not exist in this Kokoro version
    if re.search(r"voices?[/\\]\w+\.pt", low) or ("voice" in low and "not found" in low) or "no such voice" in low:
        return out("This voice is not available",
                   "The voice you picked is not included in the Kokoro version installed on this computer.",
                   "Pick a different voice (the American and British ones always work), then try again.")
    # 5) FFmpeg missing
    if "ffmpeg" in low and ("not found" in low or "not recognized" in low or "no such file" in low or "winerror 2" in low):
        return out("FFmpeg is missing",
                   "FFmpeg is the free tool that creates the video file. The app could not find it.",
                   "Install FFmpeg (ffmpeg.org/download.html) and restart this app. The installer version of this app includes it.")
    # 6) disk full / file in use / no permission
    if "no space left" in low or "errno 28" in low:
        return out("Your disk is full", f"There is not enough free space to finish {doing}.",
                   "Free up some space (delete old videos in the Library tab or other files), then try again.")
    if "winerror 32" in low or "being used by another process" in low:
        return out("A file is open in another program",
                   "A file the app needs is open in another program, such as a video player.",
                   "Close any video or audio players that are showing your files, then try again.")
    if "permissionerror" in low or "permission denied" in low:
        return out("The app is not allowed to write there",
                   "Windows did not allow the app to save a file.",
                   "Make sure your Documents folder is not read-only or protected by an antivirus, then try again.")
    # 7) out of memory
    if "memoryerror" in low or "out of memory" in low or "cuda" in low and "memory" in low:
        return out("The computer ran out of memory",
                   f"There was not enough memory to finish {doing}.",
                   "Close other programs, choose a smaller video size or lower quality, or use fewer scenes at once, then try again.")
    # 8) fallback: still friendly, with the technical text one click away
    return out("Something went wrong",
               f"The app stopped while {doing}, and it could not tell exactly why.",
               "Try once more. If it keeps happening, click “Copy details” below and send them to the developer.")
