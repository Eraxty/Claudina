import os
import re
import threading
import warnings

from datetime import datetime

import numpy as np
import soundfile as sf

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

MEMOS_DIR = "voice_memos"

GROQ_VOICE_MODEL = os.environ.get("GROQ_VOICE_MODEL", "canopylabs/orpheus-v1-english")
GROQ_VOICE = os.environ.get("GROQ_VOICE", "autumn")

MOOD_VOICES = {
    "playful": ("af_heart", 1.03),
    "sweet": ("af_bella", 1.00),
    "annoyed": ("af_nicole", 1.08),
    "busy": ("af_nicole", 0.95),
    "excited": ("af_sky", 1.08),
}

MOOD_VOICES[None] = ("af_heart", 1.0)

lock = threading.Lock()
voice_engine = None


def load_voice_engine():
    global voice_engine

    if voice_engine is not None:
        return voice_engine

    with lock:
        if voice_engine is None:
            from kokoro import KPipeline

            voice_engine = KPipeline(lang_code = "a", repo_id = "hexgrad/Kokoro-82M")

    return voice_engine


def clean_for_speaking(text):
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+", " ", text)

    return re.sub(r"\s+", " ", text).strip()


def groq_voice_memo(text, path):
    if not os.environ.get("GROQ_API_KEY"):
        return False

    try:
        from groq import Groq

        response = Groq().audio.speech.create(
            model = GROQ_VOICE_MODEL,
            voice = GROQ_VOICE,
            input = text,
            response_format = "wav",
        )
        response.write_to_file(path)

    except Exception as e:
        print(f"groq voice failed using kokoro : {e}")
        return False

    return True


def make_voice_memo(text, mood = None):
    text = clean_for_speaking(text)

    if not text:
        return None

    os.makedirs(MEMOS_DIR, exist_ok = True)
    path = os.path.join(MEMOS_DIR, f"claudina_{datetime.now().timestamp():.0f}.wav")

    if groq_voice_memo(text, path):
        return path

    voice_id, speed = MOOD_VOICES.get(mood, MOOD_VOICES[None])
    audio_chunks = []

    try:
        engine = load_voice_engine()

        for spoken in engine(text, voice = voice_id, speed = speed):
            if spoken.audio is None:
                continue

            audio_chunks.append(spoken.audio)

    except Exception:
        return None

    if not audio_chunks:
        return None

    sf.write(path, np.concatenate(audio_chunks), 24000)

    return path
