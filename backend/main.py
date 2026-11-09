import json
import os
import random
import re

from datetime import datetime, timezone

from dotenv import load_dotenv
from groq import Groq
from ollama import chat

from available import current_time, get_status
from config import (
    HER_AGE,
    HER_LIFE,
    HER_NAME,
    REFUSAL,
    OFF_LIMITS,
    UNDERAGE,
)
from gpu_lock import GPU_LOCK

from day import her_day
from db import conn
from memory import save_memory, top_memories
from plans import due_plan, mark_asked, save_plan

from state import (
    get_state,
    go_away,
    is_minor,
    mark_minor,
    update_state,
)

from voice import make_voice_memo

load_dotenv()

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_BACKUP_MODEL = os.environ.get("GROQ_BACKUP_MODEL", "openai/gpt-oss-120b")

groq = None

if os.environ.get("GROQ_API_KEY"):
    groq = Groq()

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

    messages = []

    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})

    return messages


def crossed_line_recently(session, hours = 3):
    rows = conn.execute(
        "SELECT content FROM messages WHERE session = ? AND role = 'user' AND created_at >= datetime('now', ?)",
        (session, f"-{hours} hours"),
    ).fetchall()

    for (content,) in rows:
        if OFF_LIMITS.search(content or ""):
            return True

    return False


def hours_ago(created_at):
    sent = datetime.fromisoformat(created_at + "+00:00")
    gap = datetime.now(timezone.utc) - sent

    return gap.total_seconds() / 3600


def hours_since_reply(session):
    row = conn.execute(
        "SELECT created_at FROM messages WHERE session = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()

    if row is None:
        return 99

    return hours_ago(row[0])


def hours_since_last(session):
    row = conn.execute(
        "SELECT created_at FROM messages WHERE session = ? ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()

    if row is None:
        return None

    return hours_ago(row[0])


def ask_model(prompt, messages):
    convo = [{"role": "system", "content": prompt}]

    for m in messages:
        if m["role"] == "user":
            convo.append(m)
        else:
            reacted = re.fullmatch(r"\[you reacted (.+) to their text\]", m["content"])

            if reacted:
                wrapped = {"reply": [], "react": reacted.group(1)}
            else:
                wrapped = {"reply": [m["content"]]}

            convo.append({"role": "assistant", "content": json.dumps(wrapped)})

    messages = convo
    content = None
    groq_models = []

    if groq:
        groq_models = [GROQ_MODEL, GROQ_MODEL, GROQ_BACKUP_MODEL]

    for groq_model in groq_models:
        effort = "low"

        if groq_model.startswith("qwen"):
            effort = "none"

        try:
            response = groq.chat.completions.create(
                model = groq_model,
                messages = messages,
                response_format = {"type": "json_object"},
                reasoning_effort = effort,
                max_completion_tokens = 600,
            )
            content = response.choices[0].message.content

            if content and REFUSAL.search(content):
                content = None
                continue

            break
        except Exception as e:
            print(f"{groq_model} failed: {e}")

    if content is None:
        print(f"using {MODEL} instead")

        try:
            with GPU_LOCK:
                response = chat(
                    model = MODEL,
                    messages = messages,
                    format = "json",
                    think = False,
                )
            content = response.message.content
        except Exception as e:
            print(f"{MODEL} failed: {e}")
            return {}

        if content and REFUSAL.search(content):
            return {}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def vibe(interest, kid):
    if kid:
        return "They just said they're under 18. Tell them nicely they're way too young to be talking to you, nothing flirty at all. "

    if interest >= 0.85:
        return "You're dating them. You're sweet, flirty and a bit clingy, you tease them, get a little jealous, call them babe sometimes. When they flirt or say something sweet it actually gets to you, so mix it up: sometimes flustered like stoppp, omg im blushing, why would u say that, sometimes flirt right back, never the same line twice in a row. "

    if interest >= 0.7:
        return "You're very close and attracted to them, with a high trust close friend dynamic; flirt back. When they flirt or say something sweet you get a little flustered sometimes like stoppp or why are u like this, other times flirt right back, never the same line twice in a row. "

    if interest >= 0.45:
        return "They're growing on you, be playful, but don't flirt yet. "

    return "You don't really know them, be chill but a bit reserved. No flirting, never call them babe. If they try to rizz you, laugh it off like lol ok or slow down, don't get mad. "


def annoyed(annoyance):
    if annoyance >= 0.5:
        return "You're actually annoyed with them right now because of how they've been acting. Be dry and short, you can call them out on it, don't pretend everything's fine. Only warm up if they apologize or are actually sweet. "

    if annoyance >= 0.3:
        return "They've been kind of irritating you, so you're a little drier and shorter with them than usual. "

    return ""


def respond(text, session = "", name = "", voice = True, profile = "", nudge = False, routine = ""):
    first = text is None
    lower = ""
    wants_voice = False
    messages = history(session)

    if text:
        lower = text.lower()
        messages.append({"role": "user", "content": text})
    elif nudge:
        messages.append({"role": "user", "content": "(they went quiet in the middle of the chat, you're double texting them)"})
    elif routine == "morning":
        messages.append({"role": "user", "content": "(you just woke up, you're texting them good morning)"})
    elif routine == "night":
        messages.append({"role": "user", "content": "(you're going to sleep, you're texting them goodnight)"})
    elif routine == "evening":
        messages.append({"role": "user", "content": "(it's evening, you're checking up on them)"})
    else:
        messages.append({"role": "user", "content": "(they haven't texted, you're texting them first)"})

    for w in ("voice", "memo", "record", "speak", "say it"):
        if voice and w in lower:
            wants_voice = True

    filtered_messages = []
    
    for message in messages:
    
        if message["role"] == "assistant" and REFUSAL.search(message["content"] or ""):
            continue
        filtered_messages.append(message)
    
    messages = filtered_messages

    gap = hours_since_last(session)

    if not first:
        save("user", text, session)

    if is_minor(session):
        return [], None, ""

    if get_state(session)["affection"] <= 0.05:
        if hours_since_reply(session) < 6:
            return [], None, ""

        update_state(affection_delta = 0.15, session = session)

    kid = bool(UNDERAGE.search(lower))

    if kid:
        mark_minor(session)

    state = get_state(session)

    if state["annoyance"] > 0.1:
        cooled = hours_since_reply(session) * 0.05

        if cooled > state["annoyance"] - 0.1:
            cooled = state["annoyance"] - 0.1

        state = update_state(annoyance_delta = -cooled, session = session)

    ignored_last = len(messages) >= 2 and messages[-2]["role"] == "user"

    if not first and not ignored_last and state["annoyance"] >= 0.7 and random.random() < 0.4:
        return [], None, ""

    interest = state["affection"]
    status = get_status()
    known = top_memories(limit = 50, session = session)
    mine = top_memories(limit = 50, session = "self")
    today, yesterday, feeling = her_day(ask_model)
    plan = due_plan(session)

    doing = status["doing"]

    if doing == "sleeping":
        doing = "half asleep in bed, their text just woke you up"

    prompt = (
        f"You are {HER_NAME}, {HER_AGE}, {HER_LIFE}. "
        "You listen to Frank Ocean, SZA, Daniel Caesar and Steve Lacy, you're rewatching Gilmore Girls, you drink way too much iced coffee, love late night drives and roasting people you like. "
        "Stick to these facts about yourself but only bring them up when they fit, don't shove coffee or music into every text, and don't invent big new ones like family, exes or trips. "
        f"You're texting {name or 'someone'} on Instagram. "
    )

    if profile:
        prompt += f"Their instagram profile: {profile}. You've seen it, bring it up only if it fits. "

    prompt += vibe(interest, kid)
    prompt += annoyed(state["annoyance"])
    prompt += f"It's {current_time():%A %H:%M}. Right now you are {doing}, don't make up anything else you're doing. "

    if today:
        prompt += "Stuff that happened to you today so far: " + "; ".join(today) + ". "

    if yesterday:
        prompt += "Yesterday: " + "; ".join(yesterday) + ". "

    if today or yesterday:
        prompt += "Only bring these up if they ask about your day or it actually fits, and stick to them instead of making up other stuff. "

    if feeling:
        prompt += f"Your mood right now: {feeling}. Let it show a little in how you text, but don't announce it unless they ask how you are. "

    if gap is not None and gap >= 20:
        days = round(gap / 24)

        if days <= 1:
            prompt += "You last talked to them yesterday. "
        else:
            prompt += f"You last talked to them {days} days ago, so it's been a while, you can notice that like omg u disappeared or long time no see. "

    if status["available"]:
        prompt += "You are free to text. "
    else:
        prompt += "You are busy, so keep it short. "

    if known:
        prompt += "Things you remember about them: " + "; ".join(known) + ". "

    if mine:
        prompt += "Stuff you already told people about yourself, never contradict it: " + "; ".join(mine) + ". "

    recent = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session = ? AND created_at >= datetime('now', '-2 hours')",
        (session,),
    ).fetchone()[0]

    if recent >= 40:
        prompt += "You've been texting them for a while now. "

    if routine == "morning":
        prompt += "You just woke up. Say good morning to them like gm, goood morning, just woke up, or something about your day ahead. "
    elif routine == "night":
        prompt += "You're about to go to sleep. Say goodnight to them like gn, nightt, going to bed gn, sleep well. "
    elif routine == "evening" and first:
        prompt += "It's evening and you're checking up on them because you care about them, like did u eat, hows ur day going, u good?, did u get home. "
    elif nudge:
        prompt += "They stopped answering a little while ago in the middle of the chat and you're double texting. Keep it tiny like hellooo??, u there, ??? or add one more thing to what you were saying, don't be needy about it. "
    elif first and not routine:
        prompt += "You haven't talked in a while and you're texting them first. Keep it tiny like yoo, wsp, hru, wyd, or bring up something you remember about them or what you're doing. "

    if wants_voice and interest >= 0.45:
        prompt += "They asked for a voice memo: your reply text IS the memo, speak its content directly. Never mention sending or recording it. "

    prompt += (
        "Text like a normal person on her phone, not an assistant or a character: short and lazy, use stuff like u, ur, rn, ngl, idk, lmao, fr, tbh, hbu, wbu. "
        "Just answer what they said the way a normal person would, don't add extra stuff nobody asked for and don't bring up what you're doing or your interests unless they ask. "
        "Like: yo -> yo wsp, wsp -> nm wbu, hru -> im good wbu, what u doing -> nothing rn wbu, bruh -> lmaoo what. "
        "Short isn't rude though, if they ask how you are ask them back, and never reply with just k or ok. "
        "Most texts have no emoji, one at most. Never say the same thing twice. "
        "Stuff in [brackets] is a reel, pic or voice note they sent or you sent, react to it like you actually saw or heard it. Never write [brackets] yourself. "
    )

    if interest < 0.45:
        prompt += "If they ask for a pic of you, you don't know them well enough yet, say no casually. "
    else:
        prompt += "If they ask for a pic, don't announce, describe, or promise the photo in text; just reply naturally. "


    if plan:
        prompt += f"They told you they had this coming up: {plan['about']}. It already happened {plan['when']}. You remembered, so in this text ask them how it went, even if it's not what they're talking about, like oh wait how did the {plan['about']} go. "

    hour = current_time().hour

    if hour >= 22 or hour < 5:
        prompt += "Don't keep every chat going forever. When it fits, like you're getting sleepy, the chat is dying or you've been texting a long time, end it yourself like gn, ok im sleeping, going to bed, but never in the middle of something real. "
    else:
        prompt += "Don't keep every chat going forever. When it fits, like you're busy, the chat is dying or you've been texting a long time, end it yourself like gtg, ttyl, ill text u later, but never in the middle of something real. It's daytime for you, so don't say gn or tell them to go to sleep. "

    prompt += "Never tell them to go to sleep or say gn to them unless they said they're tired or going to bed, you don't know what time it is for them. "

    prompt += (
        "Sometimes react to their last text with an emoji like people do, ❤️ if it's sweet, 😂 if it's funny, 😭 if it's cute or sad, but most texts get no reaction. "
        "If their text doesn't need an answer, like a meme, lol, gn or ok, you can leave reply empty and only react. "
        "Small talk is usually 1 bubble, only split into 2 or 3 when you're saying more than one thing, never two sentences in one bubble. "
        "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], "
        "\"memory\": \"<something they actually said about themselves that you didn't know yet, like their name, what they do, what they're into or plans coming up, otherwise empty string>\", "
        "\"self\": \"<a new detail about your own life you just said in this reply that you'd need to keep straight later, like your class schedule, a pet, a friend's name or where you're from, written like 'i have a cat named mochi', otherwise empty string>\", "
        "\"plan\": \"<something they just said they're going to do or have coming up that you could ask about after, like their job interview or their exam, otherwise empty string>\", "
        "\"when\": \"<the day that plan happens: today, tomorrow, or a weekday name like thursday>\", "
        "\"react\": \"<one emoji to react to their last text with, otherwise empty string>\", "
        "\"bye\": <true if this text ends the chat for now, otherwise false>, "
        "\"minor\": <true if they said or hinted they're under 18, otherwise false>}."
    )

    result = ask_model(prompt, messages)

    if not kid and not first:
        if str(result.get("minor")).lower() == "true":
            mark_minor(session)
            return [], None, ""

        try:
            change = float(result.get("interest", 0))
        except (TypeError, ValueError):
            change = 0

        lowest = -0.2

        if interest >= 0.85:
            lowest = -0.05

        if change > 0.03:
            change = 0.03

        if change < lowest:
            change = lowest

        try:
            irritation = float(result.get("annoyance", 0))
        except (TypeError, ValueError):
            irritation = 0

        irritation = irritation * 1.5

        if irritation > 0.25:
            irritation = 0.25

        if irritation < -0.25:
            irritation = -0.25

        state = update_state(affection_delta = change, annoyance_delta = irritation, session = session)

        if state["affection"] <= 0.05:
            return [], None, ""

    reply = result.get("reply")

    if not reply:
        reply = []
    elif not isinstance(reply, list):
        reply = [reply]

    cleaned = []
    for b in reply:
        b = str(b).strip()

        if b:
            cleaned.append(b)

    reply = cleaned[:3]
    bubbles = []

    emoji_ok = random.random() < 0.4

    for b in reply:
        b = b.lower().replace("’", "").replace("'", "").replace(",", "")
        b = b.replace("(voice memo)", "").replace("(voice note)", "")
        b = re.sub(r"\[[^\]]*\]", "", b).strip()

        for e in EMOJI.findall(b):
            if emoji_ok:
                emoji_ok = False
            else:
                b = b.replace(e, "", 1).strip()

        if not wants_voice:
            b = b.replace(". ", "\n").replace("? ", "?\n").replace("! ", "!\n")

        for part in b.split("\n"):
            part = part.rstrip(".").strip()

            if part:
                bubbles.append(part)

    if not bubbles and reply:
        bubbles = reply[:1]

    react = ""
    found = EMOJI.search(str(result.get("react") or ""))

    if found and not first:
        react = found.group()
        save("assistant", f"[you reacted {react} to their text]", session)

    if not bubbles:
        return [], None, react

    fact = str(result.get("memory", ""))

    for w in re.findall(r"[a-z]{5,}", fact.lower()):
        if w in lower:
            save_memory(fact, session = session)
            break

    if not first and str(result.get("bye")).lower() == "true":
        go_away(session, random.randint(60, 180))

    about_me = str(result.get("self") or "")

    said = " ".join(bubbles).lower()

    for w in re.findall(r"[a-z]{4,}", about_me.lower()):
        if w in said:
            save_memory(about_me, session = "self")
            break

    upcoming = str(result.get("plan") or "")

    if first:
        upcoming = ""

    for w in re.findall(r"[a-z]{4,}", upcoming.lower()):
        if w in lower:
            save_plan(upcoming, result.get("when"), session = session)
            break

    if plan:
        for w in re.findall(r"[a-z]{4,}", plan["about"].lower()):
            if w in said:
                mark_asked(plan["id"])
                break

    memo = None
    send_memo = wants_voice

    if status["available"] and random.random() < state["affection"] / 4:
        send_memo = True

    if voice and state["affection"] >= 0.45 and send_memo:
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7 or wants_voice:
            mood = "sweet"
        else:
            mood = "playful"

        memo = make_voice_memo(bubbles[-1], mood)

    for b in bubbles[:-1]:
        save("assistant", b, session)

    save("assistant", bubbles[-1], session)

    return bubbles, memo, react


if __name__ == "__main__":
    import time

    while True:
        try:
            text = input("you: ")
        except (EOFError, KeyboardInterrupt):
            break

        bubbles, memo, react = respond(text, session = "cli")

        if react:
            print(f"claudina: [reacted {react}]")

        if not bubbles and not react:
            print("(left on seen)")

        typed = bubbles

        if memo:
            typed = bubbles[:-1]

        for bubble in typed:
            print(f"claudina: {bubble}")
            time.sleep(0.7)

        if memo:
            print("claudina: [voice memo]")
            os.system(f"mpv --no-video {memo} >/dev/null 2>&1")
