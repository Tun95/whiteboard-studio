# Open-source parts of Whiteboard Wave Studio

Everything the app uses is free software that anyone may use, including for commercial work, at no cost and with no account, key or sign-up.

| Part | What it does | Licence | Notes |
|---|---|---|---|
| whiteboard-animator (Masih Sultani) | Draws the whiteboard and ad videos | MIT | Keep the copyright notice |
| Kokoro (text-to-speech model and library) | AI voices | Apache-2.0 | Free for commercial use |
| misaki | Turns text into sounds for Kokoro | Apache-2.0 | |
| espeak-ng | Pronunciation helper used by Kokoro | GPL-3.0 | Free to use. If the installer ships it, the app must also offer its source (a link is enough) |
| unidic-lite (Japanese dictionary) | Japanese voice support | BSD-3-Clause | |
| faster-whisper | Speech to text | MIT | |
| Whisper speech models (OpenAI, converted by Systran) | Speech to text | MIT | Downloaded once, no login or token needed |
| python-docx | Word files | MIT | |
| ReportLab | PDF files | BSD | |
| DejaVu Sans (studio/fonts) | Font for PDFs | Free licence (Bitstream Vera + public domain) | Allows use and sharing; see studio/fonts/DejaVu-LICENSE.txt |
| FFmpeg | Video and audio processing | LGPL-2.1+ or GPL-2+ (depends on the build) | Free to use. Not included in the source code; when we add an installer we must pick a build and credit it |
| NumPy, Pillow | Maths and images | BSD-style | |

Nothing here uses a paid service, an API key, or a "non-commercial only" model.
