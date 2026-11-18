import os
import numpy as np
import soundfile as sf
from kokoro import KPipeline

TEXT = "Hi there! I turn your script into a doodle video that's ready to share. Send me your script, and let's get started."
VOICES = ["am_michael", "am_adam", "am_eric", "am_onyx", "am_liam", "am_puck", "bm_george", "bm_daniel"]

os.makedirs("voice-test", exist_ok=True)
for lang in ("a", "b"):
    pipeline = KPipeline(lang_code=lang)
    for v in VOICES:
        if v[0] != lang:
            continue
        try:
            chunks = [np.asarray(a) for _, _, a in pipeline(TEXT, voice=v, speed=0.95)]
            sf.write(f"voice-test/{v}.wav", np.concatenate(chunks), 24000)
            print("saved", v)
        except Exception as e:
            print("skipped", v, "-", e)
