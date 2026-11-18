"""Tiny stand-in for soundfile (16-bit mono WAV only) for tests."""
import wave, numpy as np
def write(p, d, sr, subtype=None):
    w = wave.open(str(p), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(d, -1, 1) * 32767).astype('<i2').tobytes()); w.close()
def read(p, dtype="float32"):
    w = wave.open(str(p)); d = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype('float32') / 32767
    return d, w.getframerate()
class SoundFile:
    def __init__(s, p, mode, samplerate, channels, subtype=None):
        s.w = wave.open(str(p), 'wb'); s.w.setnchannels(1); s.w.setsampwidth(2); s.w.setframerate(samplerate)
    def write(s, d): s.w.writeframes((np.clip(d, -1, 1) * 32767).astype('<i2').tobytes())
    def __enter__(s): return s
    def __exit__(s, *a): s.w.close()
class _I: pass
def info(p):
    w = wave.open(str(p)); i = _I(); i.duration = w.getnframes() / w.getframerate(); return i
