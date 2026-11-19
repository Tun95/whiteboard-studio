"""The Kokoro voice library shown in the Voices tab (names follow Kokoro's own voice ids)."""
GROUPS = [
    ("American English, female", "a", "female", ["af_heart","af_alloy","af_aoede","af_bella","af_jessica","af_kore","af_nicole","af_nova","af_river","af_sarah","af_sky"]),
    ("American English, male",   "a", "male",   ["am_adam","am_echo","am_eric","am_fenrir","am_liam","am_michael","am_onyx","am_puck","am_santa"]),
    ("British English, female",  "b", "female", ["bf_alice","bf_emma","bf_isabella","bf_lily"]),
    ("British English, male",    "b", "male",   ["bm_daniel","bm_fable","bm_george","bm_lewis"]),
    ("Spanish",   "e", "mixed",  ["ef_dora","em_alex","em_santa"]),
    ("French",    "f", "female", ["ff_siwis"]),
    ("Hindi",     "h", "mixed",  ["hf_alpha","hf_beta","hm_omega","hm_psi"]),
    ("Italian",   "i", "mixed",  ["if_sara","im_nicola"]),
    ("Japanese",  "j", "mixed",  ["jf_alpha","jf_gongitsune","jf_nezumi","jf_tebukuro","jm_kumo"]),
    ("Portuguese (Brazil)", "p", "mixed", ["pf_dora","pm_alex","pm_santa"]),
    ("Mandarin Chinese", "z", "mixed", ["zf_xiaobei","zf_xiaoni","zf_xiaoxiao","zf_xiaoyi","zm_yunjian","zm_yunxi","zm_yunxia","zm_yunyang"]),
]
SAMPLE_TEXT = {
    "a": "Hello, and welcome. This is how I sound. I can read your script clearly and naturally.",
    "b": "Hello, and welcome. This is how I sound. I can read your script clearly and naturally.",
    "e": "Hola, bienvenido. Así es como sueno. Puedo leer tu guion con claridad.",
    "f": "Bonjour et bienvenue. Voici ma voix. Je peux lire votre texte clairement.",
    "h": "नमस्ते, स्वागत है। यह मेरी आवाज़ है। मैं आपकी स्क्रिप्ट साफ़ पढ़ सकता हूँ।",
    "i": "Ciao e benvenuto. Questa è la mia voce. Posso leggere il tuo testo con chiarezza.",
    "j": "こんにちは、ようこそ。これが私の声です。",
    "p": "Olá e bem-vindo. Esta é a minha voz. Posso ler o seu roteiro com clareza.",
    "z": "你好，欢迎。这是我的声音。我可以清楚地朗读你的文稿。",
}
def library() -> list[dict]:
    out = []
    for title, lang, gender, ids in GROUPS:
        for vid in ids:
            g = "female" if len(vid) > 1 and vid[1] == "f" else "male"
            out.append({"id": vid, "name": vid.split("_", 1)[1].capitalize(), "group": title, "lang": lang,
                        "gender": g, "sample": SAMPLE_TEXT[lang]})
    return out
def lang_of(voice_id: str) -> str:
    return voice_id[0] if voice_id[:1] in "abefhijpz" else "a"
