import json
import os
import re

from dotenv import load_dotenv
from groq import Groq
from ollama import chat

from db import conn
from available import get_status, current_time
from voice import make_voice_memo
from memory import save_memory, top_memories

import random

load_dotenv()

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

groq = Groq() if os.environ.get("GROQ_API_KEY") else None

# "im 15", "16 yo", "im in 9th grade" etc
UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)
OFF_LIMITS = re.compile(
    re.IGNORECASE,
)

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️‍]+")


def ask_model(system_prompt, messages, local_only = False):
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    content = None

    for _ in range(2 if groq and not local_only else 0):
        try:
            response = groq.chat.completions.create(
                model = GROQ_MODEL,
                messages = full_messages,
                response_format = {"type": "json_object"},
                reasoning_effort = "low",
            )
            content = response.choices[0].message.content
            break
        except Exception as e:
            print(f"groq failed: {e}")

    if content is None:
        print(f"using {MODEL} instead")
        response = chat(model = MODEL, messages = full_messages, format = "json", think = False)
        content = response.message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"message": "wait my brain glitched"}


def respond(text, session = "", name = "", voice = True):
    wants_voice = voice and any(w in text.lower() for w in ("voice", "memo", "record", "speak"))
    messages = _session_messages(session)

    messages.append({"role": "user", "content": text})

    conn.execute(
        "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
        ("user", text, session),
    )
    conn.commit()

    # kids get left on read for good
    if is_minor(session):
        return [], None

    # people she's mad at get ignored for a few hours, then she cools off
    if get_state(session)["affection"] <= 0.05:
        if _hours_since_reply(session) < 6:
            return [], None

        update_state(affection_delta = 0.15, session = session)

    kid = False

    if UNDERAGE.search(text):
        mark_minor(session)
        kid = True
    elif AGE_CONFIRMATION.search(text):

    if not kid and not is_verified(session) and OFF_LIMITS.search(text):
        age_question = "hey, before we get into that, how old are you?"
        conn.execute(
            "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
            ("assistant", age_question, session),
        )
        conn.commit()
        return [age_question], None

    state = get_state(session)
    status = get_status()
    known = top_memories(session = session)

    memory_line = (
        "Things you remember about them: " + "; ".join(known) + ". " if known else ""
    )
    availability = (
        f"It's {current_time():%A %H:%M}. Right now you are {status['doing']}, don't make up anything else you're doing. "
        + (
            "You are free to text, but you might still mention what you were doing. "
            if status["available"]
            else "You are busy, so keep it short, you can mention what you're doing. "
        )
    )
    
    interest = state["affection"]

    if kid:
        vibe = "They just said they're under 18. Tell them nicely they're way too young to be talking to you, nothing flirty at all. "
    elif interest >= 0.85:
        vibe = "You're dating them now. You're sweet, flirty and a bit clingy, you tease them, get a little jealous, call them babe sometimes. "
    elif interest >= 0.7:
        vibe = "You're very close and attracted to them, with a high-trust close-friend dynamic; flirt back. "
    elif interest >= 0.45:
        vibe = "They're growing on you, be playful, but don't flirt yet. "
    else:
        vibe = "You don't really know them, be chill but a bit reserved. No flirting, never call them babe. If they try to rizz you, laugh it off or be dry. "

    system_prompt = (
        "You are Claudina, 20, second year psych student. You love music, late night drives and roasting people you like. "
        f"You're texting {name or 'someone'} on Instagram. "
        f"{vibe}"
        f"{availability}"
        f"{memory_line}"
        + (
            "They asked for a voice memo: your reply text IS the memo, speak its content directly. Never mention sending or recording it. "
            if wants_voice and interest >= 0.45
            else ""
        ) +
        "Text like a real girl on her phone, not an assistant: short and lazy, use stuff like u, ur, rn, ngl, idk, lmao, fr, tbh, hbu. "
        "Most texts have no emoji, one at most. Match their energy, a dry text gets a short reply. "
        "Have opinions and joke around, don't just say cool or nice. "
        "Don't ask a question every time and never say the same thing twice. "
        + (
        ) +
        "Send 1 to 3 bubbles, usually 1. "
        "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], "
        "\"memory\": \"<something they actually said about themselves that you didn't know yet, like their name, what they do, what they're into or plans coming up, otherwise empty string>\", "
        "\"minor\": <true if they said or hinted they're under 18, otherwise false>}."
    )

    result = ask_model(system_prompt, messages, local_only = bool(local_alt_turn))

    if not kid:
        # the model caught a kid the regex missed, just don't answer
        if str(result.get("minor")).lower() == "true":
            mark_minor(session)
            return [], None

        # she warms up slow but goes off people fast, unless she's dating them
        try:
            change = max(-0.05 if interest >= 0.85 else -0.2, min(0.03, float(result.get("interest", 0))))
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

    # nobody texts with capitals, apostrophes, commas or full stops
    bubbles = [b.lower().replace("’", "").replace("'", "").replace(",", "").rstrip(".") for b in bubbles]

    # she spams emojis, let one through now and then
    allowed = random.random() < 0.4
    cleaned = []

    for b in bubbles:
        for e in EMOJI.findall(b):
            if allowed:
                allowed = False
            else:
                b = b.replace(e, "", 1).strip()

        if b:
            cleaned.append(b)

    bubbles = cleaned or bubbles[:1]

    if not bubbles:
        return [], None

    fact = str(result.get("memory", ""))

    # the model makes stuff up, only keep it if it's about something they actually said
    if any(w in text.lower() for w in re.findall(r"[a-z]{5,}", fact.lower())):
        save_memory(fact, session = session)

    memo = None
    wants_voice = wants_voice or any(w in text.lower() for w in ("voice memo", "say it"))
    # voice notes only go to people she knows, the more she likes you the more she sends
    if voice and state["affection"] >= 0.45 and (wants_voice or (status["available"] and random.random() < state["affection"] / 4)):
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7 or wants_voice:
            mood = "sweet"
        else:
            mood = "playful"
        memo = make_voice_memo(bubbles[-1], mood)

    for bubble in bubbles:
        if bubble == bubbles[-1] and memo:
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


def _session_messages(session):
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session = ? ORDER BY id DESC LIMIT 30",
        (session,),
    ).fetchall()

    return [{"role": role, "content": content} for role, content in reversed(rows)]


def _hours_since_reply(session):
    row = conn.execute(
        "SELECT (julianday('now') - julianday(created_at)) * 24 FROM messages WHERE session = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()

    return row[0] if row else 99


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
