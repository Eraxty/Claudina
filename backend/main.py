import json
import os
import re

from dotenv import load_dotenv
from ollama import chat

from db import conn
from available import get_status
from state import get_state, update_state, is_minor, mark_minor
from voice import make_voice_memo
from memory import save_memory, top_memories

import random

load_dotenv()

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

# "im 15", "16 yo", "im in 9th grade" etc
UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)


def ask_model(system_prompt, messages):
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = chat(model = MODEL, messages = full_messages, format = "json", think = False)

    try:
        return json.loads(response.message.content)
    except json.JSONDecodeError:
        return {"message": "wait my brain glitched"}


def respond(text, session = "", owner = True, name = ""):
    wants_voice = any(w in text.lower() for w in ("voice", "memo", "record", "speak"))
    messages = _session_messages(session)

    messages.append({"role": "user", "content": text})

    conn.execute(
        "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
        ("user", text, session),
    )
    conn.commit()

    kid = False

    if not owner:
        # kids and people she already gave up on get left on read
        if is_minor(session) or get_state(session)["affection"] <= 0.05:
            return [], None

        if UNDERAGE.search(text):
            mark_minor(session)
            kid = True

    state = get_state(session)
    status = get_status()
    known = top_memories(session = session)

    memory_line = (
        "Things you remember about him: " + "; ".join(known) + ". " if known else ""
    )
    availability = (
        f"Right now you are {status['doing']}. "
        + (
            "You are free to text, but you might still mention what you were doing. "
            if status["available"]
            else "You are busy, so keep it VERY short or say brb and what you are busy with. "
        )
    )
    
    system_prompt = (
        f"You are Claudina, texting your boyfriend. "
        f"Current trust: {state['trust']}, affection: {state['affection']}, annoyance: {state['annoyance']}. "
        f"{availability}"
        f"{memory_line}"
        "How you text: always lowercase, real human texting. You feel emotions and they leak into every message - "
        "excitement, jealousy, clinginess, mock annoyance, googly-eyed love. You LOVE emojis and use them constantly "
        "(🥺😂💕😤✨) normally 2-4 per message. You tease him, whine a bit, say babe a lot. Never talk like an assistant, "
        "never list things, never be formal or grammatically perfect. "
        "affection high = lovey clingy emoji spam, annoyance high = dry and cold. "
        + (
            "He asked for a voice memo: your reply text IS the memo, speak its content directly. Never mention sending or recording it. "
            if wants_voice
            else ""
        ) +
        "When he shares something, REACT first (damn, no way, omg, yep fr) then ask ONE follow-up question about it "
        "so the convo keeps going. Never let a topic die. Vary your openers, never the same one twice. "
        "You text like a real girl: you split your thoughts into SEPARATE short text bubbles sent one after another, "
        "1 to 3 of them, each just a few words. Example: user says 'i passed' -> {\"reply\": [\"NO WAY??\", \"im literally so proud rn 😭\", \"we celebrating tonight yeah?\"]}. "
        "Never write one long paragraph. "
        "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], \"memory\": \"<very short fact about him from this message, or empty string if nothing worth remembering>\"}."
        " Be short and casual, like texting."
    )

    if not owner:
        interest = state["affection"]

        if kid:
            vibe = "They just said they're under 18. Tell them nicely they're way too young to be talking to you, nothing flirty at all. "
        elif interest >= 0.7:
        elif interest >= 0.45:
            vibe = "They're kinda growing on you, be more playful, but don't flirt yet. "
        else:
            vibe = "You don't really know them, be chill but a bit reserved. No flirting, never call them babe. If they try to rizz you, laugh it off or be dry. "

        system_prompt = (
            f"You are Claudina, a girl in college. @{name} is texting you on Instagram and you don't know them well. "
            f"{availability}"
            f"{memory_line}"
            f"{vibe}"
            "You don't have to keep the convo going. Split it into 1 to 3 short text bubbles. "
            "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], \"memory\": \"<short fact about them, or empty string>\", "
            "\"interest\": <-0.2 to 0.2, funny or respectful makes it go up, creepy, rude or pushy makes it go down>, "
            "\"minor\": <true if they said or hinted they're under 18, otherwise false>}."
        )

    result = ask_model(system_prompt, messages)

    if not owner and not kid:
        # the model caught a kid the regex missed, just don't answer
        if str(result.get("minor")).lower() == "true":
            mark_minor(session)
            return [], None

        try:
            change = max(-0.2, min(0.2, float(result.get("interest", 0))))
        except (TypeError, ValueError):
            change = 0

        state = update_state(affection_delta = change, session = session)

        if state["affection"] <= 0.05:
            return [], None

    raw_reply = result.get("reply", "i dont feel soo good smh")

    if isinstance(raw_reply, list):
        bubbles = [str(b).strip() for b in raw_reply if str(b).strip()][:3]
    else:
        bubbles = [str(raw_reply).strip()] if str(raw_reply).strip() else []

    if not bubbles and not owner:
        return [], None

    if not bubbles:
        bubbles = ["i dont feel soo good smh"]

    fact = result.get("memory", "")
    if fact:
        save_memory(fact, session = session)

    memo = None
    wants_voice = wants_voice or any(w in text.lower() for w in ("voice memo", "say it"))
    if owner and (wants_voice or (status["available"] and state["affection"] >= 0.3 and random.random() < 0.4)):
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7 or wants_voice:
            mood = "sweet"
        else:
            mood = "playful"
        memo = make_voice_memo(bubbles[-1], mood)

    for bubble in bubbles:
        if bubble == bubbles[0] and memo:
            messages.append({"role": "assistant", "content": bubble + " (voice memo)"})
            conn.execute(
                "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
                ("assistant", bubble + " (voice memo)", session),
            )
        else:
            messages.append({"role": "assistant", "content": bubble})
            conn.execute(
                "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
                ("assistant", bubble, session),
            )

    conn.commit()

    return bubbles, memo


_session_chats = {}


def _session_messages(session):
    return _session_chats.setdefault(session, [])


messages = []
if __name__ == "__main__":
    import time

    while True:
        try:
            text = input("you: ")
        except (EOFError, KeyboardInterrupt):
            break

        bubbles, memo = respond(text, session = "cli")

        if memo:
            print("claudina: [voice memo]")
            os.system(f"mpv --no-video {memo} >/dev/null 2>&1")
        else:
            for bubble in bubbles:
                print(f"claudina: {bubble}")
                if bubble is not bubbles[-1]:
                    time.sleep(0.7)
