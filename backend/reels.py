import base64
import os
import subprocess
import tempfile
import time

import requests

from ollama import chat

from config import HER_AGE, HER_LIFE, HER_NAME
from gpu_lock import GPU_LOCK
from main import ask_model, groq, save
from memory import top_memories
from state import get_state, is_away, is_minor

VISION_MODEL = os.environ.get("VISION_MODEL", "gemma3:4b")
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
HEARING_MODEL = os.environ.get("HEARING_MODEL", "whisper-large-v3-turbo")

LOOK_PROMPT = "in one short sentence with no intro, say what's in this or what happens and any text on screen"


def look_groq(frames):
    content = [{"type": "text", "text": LOOK_PROMPT}]

    for frame in frames:
        with open(frame, "rb") as f:
            data = base64.b64encode(f.read()).decode()

        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}})

    response = groq.chat.completions.create(
        model = GROQ_VISION_MODEL,
        messages = [{"role": "user", "content": content}],
        reasoning_effort = "none",
    )

    return response.choices[0].message.content


def look(image, video):
    try:
        with tempfile.TemporaryDirectory() as folder:
            
            if video:
                subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", "fps=1/4,scale=512:-1", "-frames:v", "4", f"{folder}/%d.jpg"], check = True)
            else:
                with open(f"{folder}/1.jpg", "wb") as f:
                    f.write(requests.get(str(image), timeout = 20).content)

            frames = sorted(f"{folder}/{name}" for name in os.listdir(folder))
            seen = None

            if groq:
                try:
                    seen = look_groq(frames)
                except Exception as e:
                    print(f"groq couldnt see it running locally: {e}")

            if not seen:
                with GPU_LOCK:
                    response = chat(model = VISION_MODEL, messages = [{
                        "role": "user",
                        "content": LOOK_PROMPT,
                        "images": frames,
                    }])

                seen = response.message.content

        return " ".join(seen.split())

    except Exception as e:
        print(f"couldnt watch it: {e}")
        
        return "couldnt load it"


def hear(url):
    if not groq:
        return None

    try:
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/voice.m4a"

            with open(path, "wb") as f:
                f.write(requests.get(str(url), timeout = 20).content)

            with open(path, "rb") as f:
                heard = groq.audio.transcriptions.create(file = f, model = HEARING_MODEL)

        return " ".join(heard.text.split())

    except Exception as e:
        print(f"couldnt hear it: {e}")

        return None


def watch(m):
    if m.item_type == "voice_media" and m.media and m.media.audio_url:
        heard = hear(m.media.audio_url)

        if heard:
            return f"[sent you a voice note saying: {heard}]"

        return "[sent you a voice note but it wouldnt play]"

    if m.clip or m.media_share:
        shared = m.clip or m.media_share
        return f"[sent you a reel: {look(shared.thumbnail_url, shared.video_url)}, caption: {shared.caption_text[:200]}]"

    if m.xma_share:
        return f"[sent you a reel: {look(m.xma_share.preview_url, None)}]"

    if m.media and m.item_type != "voice_media":
        return f"[sent you a pic: {look(m.media.thumbnail_url, m.media.video_url)}]"

    return None


def doomscroll(cl, threads, reel):
    people = {}
    lines = []

    for thread in threads:
        if thread.is_group or thread.pending or len(thread.users) != 1:
            continue

        user = thread.users[0]
        
        session = f"insta:{user.pk}"
        
        close = get_state(session)["affection"]

        if close < 0.45 or is_minor(session) or is_away(session):
            continue

        people[user.username] = (thread.id, session)
        
        lines.append(f"{user.username} (closeness {close:.2f}): " + "; ".join(top_memories(session = session)))

    prompt = (
        f"You are {HER_NAME}, {HER_AGE}, {HER_LIFE}. You're lying in bed doomscrolling reels, the user message is the one you're watching rn. "
        "These are people you text and what you know about them:\n" + "\n".join(lines) + "\n"
        "Only send it to someone if it's actually funny, scary accurate to them or something you'd love to share with them. Most reels you just scroll past. "
        "If you send it, you can add a tiny text like this is so u, LMAOO or us fr. Like it if you actually enjoyed it. "
        'Reply ONLY as JSON: {"like": <true or false>, "send": [{"to": "<username>", "text": "<text or empty>"}]}, or {"like": false, "send": []} to scroll past.'
    )

    about = f"{look(reel.thumbnail_url, reel.video_url)}, caption: {reel.caption_text[:200]}"

    result = ask_model(prompt, [{"role": "user", "content": about}])

    if str(result.get("like")).lower() == "true":
        cl.media_like(reel.id)
        
        print(f"liked a reel: {about}")

    for pick in result.get("send") or []:
        
        if not isinstance(pick, dict) or pick.get("to") not in people:
            continue

        thread_id, session = people[pick["to"]]
        
        text = str(pick.get("text") or "").lower()

        cl.direct_media_share(reel.id, thread_ids = [thread_id], media_type = "video")
        
        save("assistant", f"[sent a reel: {about}]", session)
        
        print(f"claudina -> {pick['to']}: [reel] {about}")

        if text:
            time.sleep(2 + len(text) / 10)
            cl.direct_send(text, thread_ids = [thread_id])
            
            save("assistant", text, session)
            
            print(f"claudina -> {pick['to']}: {text}")


def scroll(cl, threads):
    
    print("doomscrolling")

    for reel in cl.reels(amount = 8):
    
        try:
            doomscroll(cl, threads, reel)
    
        except Exception as e:
            print(f"error while scrolling: {e}")

    print("done scrolling yayayya")
