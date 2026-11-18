import os
import numpy as np
import soundfile as sf
from kokoro import KPipeline

TEXT = "Hi there! I turn your script into a doodle video that's ready to share. Send me your script, and let's get started."
VOICES = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "af_nova", "af_aoede", "af_jessica", "bf_emma", "bf_isabella", "bf_alice", "bf_lily"]

os.makedirs("voice-test-f", exist_ok=True)
for lang in ("a", "b"):
    pipeline = KPipeline(lang_code=lang)
    for v in VOICES:
        if v[0] != lang:
            continue
        try:
            chunks = [np.asarray(a) for _, _, a in pipeline(TEXT, voice=v, speed=0.95)]
            sf.write(f"voice-test-f/{v}.wav", np.concatenate(chunks), 24000)
            print("saved", v)
        except Exception as e:
            print("skipped", v, "-", e)
