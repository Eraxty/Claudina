import os
import json
import urllib.request
from datetime import datetime

VOICE_ID = "pFZP5JQG7iQjIQuC4Bku"
MEMOS_DIR = os.path.join(os.path.dirname(__file__), "voice_memos")


def make_voice_memo(text, mood = None):
    key = os.environ.get("11labs")

    if not key or not text.strip():
        return None

    opener = {
        "playful": "[laughs] ",
        "sweet": "[giggles] ",
        "annoyed": "[sighs] ",
        "busy": "[whispers] ",
        "excited": "[gasps] ",
    }.get(mood, "")

    try:
        os.makedirs(MEMOS_DIR, exist_ok = True)

        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            data = json.dumps({
                "text": opener + text,
                "model_id": "eleven_v3",
            }).encode(),
            
            headers = {"xi-api-key": key, "Content-Type": "application/json"},
            method = "POST",
        
        )
        audio = urllib.request.urlopen(req, timeout = 30).read()

        if not audio.startswith(b"ID3") and audio[:2] != b"\xff\xfb":
            return None

        path = os.path.join(MEMOS_DIR, f"claudina_{datetime.now().timestamp():.0f}.mp3")
        
        with open(path, "wb") as f:
            f.write(audio)

        return path
    
    except Exception:
        return None
