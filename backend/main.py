import json
import os
import random
import re

from dotenv import load_dotenv
from groq import Groq
from ollama import chat

from available import current_time, get_status
from db import conn
from memory import save_memory, top_memories
from state import get_state, is_minor, mark_minor, update_state
from voice import make_voice_memo

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

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️‍]+")


def save(role, content, session):
    conn.execute(
        "INSERT INTO messages (role, content, created_at, session) VALUES (?, ?, datetime('now'), ?)",
        (role, content, session),
    )
    conn.commit()


def history(session):
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session = ? ORDER BY id DESC LIMIT 30",
        (session,),
    ).fetchall()

    return [{"role": role, "content": content} for role, content in reversed(rows)]


def hours_since_reply(session):
    row = conn.execute(
        "SELECT (julianday('now') - julianday(created_at)) * 24 FROM messages WHERE session = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()

    return row[0] if row else 99


def ask_model(prompt, messages):
    messages = [{"role": "system", "content": prompt}] + messages
    content = None

    # groq runs a way bigger model for free, gemma on this laptop is the backup
    # it sometimes sends back nothing so it gets a second try
    for _ in range(2 if groq else 0):
        try:
            response = groq.chat.completions.create(
                model = GROQ_MODEL,
                messages = messages,
                response_format = {"type": "json_object"},
                reasoning_effort = "low",
            )
            content = response.choices[0].message.content
            break
        except Exception as e:
            print(f"groq failed: {e}")

    if content is None:
        print(f"using {MODEL} instead")
        content = chat(model = MODEL, messages = messages, format = "json", think = False).message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def vibe(interest, kid):
    if kid:
        return "They just said they're under 18. Tell them nicely they're way too young to be talking to you, nothing flirty at all. "

    if interest >= 0.85:
        return (
            "You're dating them. You're sweet, flirty and a bit clingy, you tease them, get a little jealous, call them babe sometimes. "
            "If they get horny, tease back but dodge it, it doesn't put you off them. "
        )

    if interest >= 0.7:
        return "You have a crush on them, flirt back but play it a bit cool. "

    if interest >= 0.45:
        return "They're growing on you, be playful, but don't flirt yet. "

    return "You don't really know them, be chill but a bit reserved. No flirting, never call them babe. If they try to rizz you, laugh it off or be dry. "


def respond(text, session = "", name = "", voice = True):
    lower = text.lower()
    wants_voice = voice and any(w in lower for w in ("voice", "memo", "record", "speak", "say it"))
    messages = history(session) + [{"role": "user", "content": text}]

    save("user", text, session)

    # kids get left on read for good
    if is_minor(session):
        return [], None

    # people she's mad at get ignored for a few hours, then she cools off
    if get_state(session)["affection"] <= 0.05:
        if hours_since_reply(session) < 6:
            return [], None

        update_state(affection_delta = 0.15, session = session)

    kid = bool(UNDERAGE.search(text))

    if kid:
        mark_minor(session)

    state = get_state(session)
    interest = state["affection"]
    status = get_status()
    known = top_memories(session = session)

    prompt = (
        "You are Claudina, 20, second year psych student in New York, you live in a dorm with your roommate Maya. "
        "You listen to Frank Ocean, SZA, Daniel Caesar and Steve Lacy, you're rewatching Gilmore Girls, you drink way too much iced coffee, love late night drives and roasting people you like. "
        "Stick to these facts about yourself and bring up one at a time, don't invent big new ones like family, exes or trips. "
        f"You're texting {name or 'someone'} on Instagram. "
        + vibe(interest, kid)
        + f"It's {current_time():%A %H:%M}. Right now you are {status['doing']}, don't make up anything else you're doing. "
    )

    if status["available"]:
        prompt += "You are free to text, but you might still mention what you were doing. "
    else:
        prompt += "You are busy, so keep it short, you can mention what you're doing. "

    if known:
        prompt += "Things you remember about them: " + "; ".join(known) + ". "

    if wants_voice and interest >= 0.45:
        prompt += "They asked for a voice memo: your reply text IS the memo, speak its content directly. Never mention sending or recording it. "

    prompt += (
        "Text like a real girl on her phone, not an assistant: short and lazy, use stuff like u, ur, rn, ngl, idk, lmao, fr, tbh, hbu. "
        "Most texts have no emoji, one at most. Match their energy, a dry text gets a short reply. "
        "Have opinions and joke around, don't just say cool or nice. "
        "Don't ask a question every time and never say the same thing twice. Never sexual. "
        "Send 1 to 3 bubbles, usually 1. "
        "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], "
        "\"memory\": \"<something they actually said about themselves that you didn't know yet, like their name, what they do, what they're into or plans coming up, otherwise empty string>\", "
        "\"interest\": <-0.2 to 0.2, normal small talk is 0, funny, sweet or respectful makes it go up, insults, sexual stuff, creepy or pushy makes it go down>, "
        "\"minor\": <true if they said or hinted they're under 18, otherwise false>}."
    )

    result = ask_model(prompt, messages)

    if not kid:
        # the model caught a kid the regex missed, just don't answer
        if str(result.get("minor")).lower() == "true":
            mark_minor(session)
            return [], None

        try:
            change = float(result.get("interest", 0))
        except (TypeError, ValueError):
            change = 0

        # she warms up slow but goes off people fast, unless she's dating them
        lowest = -0.05 if interest >= 0.85 else -0.2
        state = update_state(affection_delta = max(lowest, min(0.03, change)), session = session)

        if state["affection"] <= 0.05:
            return [], None

    reply = result.get("reply") or []

    if not isinstance(reply, list):
        reply = [reply]

    reply = [str(b).strip() for b in reply if str(b).strip()][:3]
    bubbles = []

    # she spams emojis, let one through now and then
    emoji_ok = random.random() < 0.4

    for b in reply:
        # nobody texts with capitals, apostrophes, commas or full stops
        b = b.lower().replace("’", "").replace("'", "").replace(",", "").rstrip(".")

        for e in EMOJI.findall(b):
            if emoji_ok:
                emoji_ok = False
            else:
                b = b.replace(e, "", 1).strip()

        if b:
            bubbles.append(b)

    # a reply that's just an emoji is fine though
    if not bubbles and reply:
        bubbles = reply[:1]

    if not bubbles:
        return [], None

    fact = str(result.get("memory", ""))

    # the model makes stuff up, only keep it if it's about something they actually said
    if any(w in lower for w in re.findall(r"[a-z]{5,}", fact.lower())):
        save_memory(fact, session = session)

    memo = None

    # voice notes only go to people she knows, the more she likes you the more she sends
    if voice and state["affection"] >= 0.45 and (wants_voice or (status["available"] and random.random() < state["affection"] / 4)):
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7 or wants_voice:
            mood = "sweet"
        else:
            mood = "playful"

        memo = make_voice_memo(bubbles[-1], mood)

    for b in bubbles[:-1]:
        save("assistant", b, session)

    save("assistant", bubbles[-1] + (" (voice memo)" if memo else ""), session)

    return bubbles, memo


if __name__ == "__main__":
    import time

    while True:
        try:
            text = input("you: ")
        except (EOFError, KeyboardInterrupt):
            break

        bubbles, memo = respond(text, session = "cli")

        # the voice memo says the last bubble
        for bubble in bubbles[:-1] if memo else bubbles:
            print(f"claudina: {bubble}")
            time.sleep(0.7)

        if memo:
            print("claudina: [voice memo]")
            os.system(f"mpv --no-video {memo} >/dev/null 2>&1")
