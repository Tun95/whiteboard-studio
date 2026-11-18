"""Fake Kokoro for testing the app without the real voice model (makes a quiet tone per sentence)."""
import numpy as np
class KPipeline:
    def __init__(self, lang_code): pass
    def __call__(self, text, voice, speed):
        n = int(24000 * max(0.6, 0.06 * len(text)) / speed)
        t = np.arange(n) / 24000
        yield None, None, (0.2 * np.sin(2 * np.pi * 220 * t)).astype("float32")
