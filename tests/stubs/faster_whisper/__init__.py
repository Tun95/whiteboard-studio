# TEST STUB of faster-whisper (the real model cannot be downloaded in the test sandbox)
import os, wave
class _Seg:
    def __init__(s,a,b,t): s.start=a; s.end=b; s.text=t
class _Info:
    def __init__(s,d,l): s.duration=d; s.language=l; s.language_probability=0.97
class WhisperModel:
    def __init__(self, model, device="cpu", compute_type="int8", download_root=None, cpu_threads=0, local_files_only=False):
        if local_files_only and not os.path.isdir(os.path.join(download_root,"models--Systran--faster-whisper-"+model)): raise OSError("model not on disk")
        if os.environ.get("STUB_OFFLINE"): raise ConnectionError("Max retries exceeded with url: /Systran/faster-whisper-%s (huggingface.co)" % model)
        d=os.path.join(download_root,"models--Systran--faster-whisper-"+model,"snapshots","abc123"); os.makedirs(d,exist_ok=True); open(os.path.join(d,"model.bin"),"w").write("x")
    def transcribe(self, audio, language=None, task="transcribe", **kw):
        dur=(len(audio)/16000.0) if hasattr(audio,'__len__') and not isinstance(audio,str) else 1.0
        lang=language or "en"; pre="[translated] " if task=="translate" else ""
        lines=["Hello and welcome to the show.","Today we talk about Ẹ kú àárọ̀ and how to say it.","This is the last sentence of the test file."]
        n=len(lines); segs=[_Seg(i*dur/n, (i+1)*dur/n-0.2, " "+pre+t) for i,t in enumerate(lines)]
        return iter(segs), _Info(dur, lang)
