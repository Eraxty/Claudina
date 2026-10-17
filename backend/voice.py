import os
import re
import threading

from datetime import datetime

import numpy as np
import soundfile as sf

MEMOS_DIR = os.path.join(os.path.dirname(__file__), "voice_memos")

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

            voice_engine = KPipeline(lang_code = "a")

    return voice_engine


def clean_for_speaking(text):
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(
        "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+", " ", text
    )

    return re.sub(r"\s+", " ", text).strip()


def make_voice_memo(text, mood = None, api_key = None):
    text = clean_for_speaking(text)

    if not text:
        return None

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

    os.makedirs(MEMOS_DIR, exist_ok = True)

    path = os.path.join(MEMOS_DIR, f"claudina_{datetime.now().timestamp():.0f}.wav")
    sf.write(path, np.concatenate(audio_chunks), 24000)

    return path
