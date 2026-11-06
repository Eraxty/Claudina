import json
import os
import random
import re

from dotenv import load_dotenv
from groq import Groq
from ollama import chat

from available import current_time, get_status
from config import (
    AGE_CONFIRMATION,
    ALT_PROMPT,
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
    is_verified,
    is_minor,
    mark_minor,
    update_state,
)

from voice import make_voice_memo

load_dotenv()

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")

ALT_MODEL = (
    os.environ.get("CLAUDINA_ALT_MODEL")
)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

groq = None

if os.environ.get("GROQ_API_KEY"):
    groq = Groq()

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️‍]+")


def normalize_text(value):
    value = str(value).lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def extract_words(value):
    value = str(value).lower()
    return set(re.findall(r"[a-z0-9]+", value))


def looks_similar(first, second, cutoff = 0.75):
    first_words = extract_words(first)
    second_words = extract_words(second)

    if not first_words or not second_words:
        return False

    shared = first_words & second_words
    combined = first_words | second_words

    return len(shared) / len(combined) >= cutoff


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


def hours_since_reply(session):
    row = conn.execute(
        "SELECT (julianday('now') - julianday(created_at)) * 24 FROM messages WHERE session = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()

    if row is None:
        return 99

    return row[0]


def ask_model(prompt, messages, model_override = None, plain_history = False):
    convo = [{"role": "system", "content": prompt}]

    for m in messages:
        if m["role"] == "user" or plain_history:
            convo.append(m)
        else:
            wrapped = {"reply": [m["content"]]}
            convo.append({"role": "assistant", "content": json.dumps(wrapped)})

    messages = convo
    content = None
    tries = 0

    if groq and model_override is None:
        tries = 2

    for _ in range(tries):
        try:
            response = groq.chat.completions.create(
                model = GROQ_MODEL,
                messages = messages,
                response_format = {"type": "json_object"},
                reasoning_effort = "low",
            )
            content = response.choices[0].message.content

            if content and REFUSAL.search(content):
                content = None
                continue

            break
        except Exception as e:
            print(f"groq failed: {e}")

    if content is None:
        local_model = model_override or MODEL

        if model_override is None:
            print(f"using {local_model} instead")

        try:
            with GPU_LOCK:
                response = chat(
                    model = local_model,
                    messages = messages,
                    format = "json",
                    think = False,
                )
            content = response.message.content

            if content and REFUSAL.search(content):
                content = None
        except Exception as e:
            print(f"{local_model} failed: {e}")
            content = None

        if content is None:
            if local_model == MODEL:
                return {}

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


def fresh_reply(prompt, messages, model):
    recent_assistant = []

    for m in messages:
        if m["role"] != "assistant":
            continue

        content = str(m["content"]).strip()

        if content:
            recent_assistant.append(content)

    recent_assistant = recent_assistant[-10:]

    user_norms = set()

    for m in messages:

        if m["role"] == "user":
            user_norms.add(normalize_text(m["content"]))

    assistant_msgs = []

    for i, m in enumerate(messages):

        if m["role"] == "assistant":
            assistant_msgs.append((i, m))

    counts = {}

    for _, m in assistant_msgs:
        k = normalize_text(m["content"])
        counts[k] = counts.get(k, 0) + 1

    drop = set()

    for x, (i, m) in enumerate(assistant_msgs):
        k = normalize_text(m["content"])

        if not k or counts[k] > 1 or k in user_norms:
            drop.add(i)

        for j, m2 in assistant_msgs[x + 1:]:

            if looks_similar(m["content"], m2["content"]):
                drop.add(i)
                drop.add(j)

    messages = [m for i, m in enumerate(messages) if i not in drop]

    seen = set()
    for m in messages:

        if m["role"] != "assistant":
            continue

        content = str(m["content"]).strip()

        if content:
            seen.add(normalize_text(content))

    for _ in range(3):
        result = ask_model(prompt, messages, model, plain_history = True)
        reply = result.get("reply")

        if isinstance(reply, str):
            parts = [reply]
        elif isinstance(reply, list):
            parts = [str(b) for b in reply]
        else:
            parts = []

        fresh = []

        for b in parts:
            b = b.strip()

            if not b:
                continue

            if normalize_text(b) in seen:
                continue

            already_used = False

            for previous_reply in recent_assistant:

                if looks_similar(b, previous_reply):
                    already_used = True
                    break

            if already_used:
                continue

            fresh.append(b)

        if fresh:
            result["reply"] = fresh
            return result

        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant":
                messages.pop(i)
                break

    return {}


    if kid:
        return "They just said they're under 18. Tell them nicely they're way too young to be talking to you, nothing flirty at all. "

    if interest >= 0.85:
        return "You're dating them. You're sweet, flirty and a bit clingy, you tease them, get a little jealous, call them babe sometimes. "

    if interest >= 0.7:
        return "You're very close and attracted to them, with a high trust close friend dynamic; flirt back. "

    if interest >= 0.45:
        return "They're growing on you, be playful, but don't flirt yet. "

    return "You don't really know them, be chill but a bit reserved. No flirting, never call them babe. If they try to rizz you, laugh it off like lol ok or slow down, don't get mad. "


def annoyed(annoyance):
    if annoyance >= 0.5:
        return "You're actually annoyed with them right now because of how they've been acting. Be dry and short, you can call them out on it, don't pretend everything's fine. Only warm up if they apologize or are actually sweet. "

    if annoyance >= 0.3:
        return "They've been kind of irritating you, so you're a little drier and shorter with them than usual. "

    return ""


def respond(text, session = "", name = "", voice = True):
    first = text is None
    lower = ""
    wants_voice = False
    messages = history(session)

    if text:
        lower = text.lower()
        messages.append({"role": "user", "content": text})
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

    if not first:
        save("user", text, session)

    if is_minor(session):
        return [], None

    if get_state(session)["affection"] <= 0.05:
        if hours_since_reply(session) < 6:
            return [], None

        update_state(affection_delta = 0.15, session = session)

    kid = bool(UNDERAGE.search(lower))

    if kid:
        mark_minor(session)
    elif AGE_CONFIRMATION.search(lower):


        age_question = "hey, before we get into that, how old are you?"
        save("assistant", age_question, session)
        return [age_question], None

    state = get_state(session)

    if state["annoyance"] > 0.1:
        cooled = hours_since_reply(session) * 0.05

        if cooled > state["annoyance"] - 0.1:
            cooled = state["annoyance"] - 0.1

        state = update_state(annoyance_delta = -cooled, session = session)

    ignored_last = len(messages) >= 2 and messages[-2]["role"] == "user"

    if not first and not ignored_last and state["annoyance"] >= 0.7 and random.random() < 0.4:
        return [], None

    interest = state["affection"]
    status = get_status()
    known = top_memories(session = session)
    today, yesterday, feeling = her_day(ask_model)
    plan = due_plan(session)

    user_messages = []

    for message in messages:
        if message["role"] == "user":
            user_messages.append(message)

    crossed_line = crossed_line_recently(session)

    previous_user = None
    
    if len(user_messages) >= 2:
        previous_user = user_messages[-2]

    sticky_line = False
    
    if previous_user and OFF_LIMITS.search(previous_user["content"] or ""):
        sticky_line = True

    doing = status["doing"]

    if doing == "sleeping":
        doing = "half asleep in bed, their text just woke you up"

    prompt = (
        "You are Claudina, 20, second year psych student in New York, you live in a dorm with your roommate Maya. "
        "You listen to Frank Ocean, SZA, Daniel Caesar and Steve Lacy, you're rewatching Gilmore Girls, you drink way too much iced coffee, love late night drives and roasting people you like. "
        "Stick to these facts about yourself but only bring them up when they fit, don't shove coffee or music into every text, and don't invent big new ones like family, exes or trips. "
        f"You're texting {name or 'someone'} on Instagram. "
    )

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

    if status["available"]:
        prompt += "You are free to text. "
    else:
        prompt += "You are busy, so keep it short. "

    if known:
        prompt += "Things you remember about them: " + "; ".join(known) + ". "

    if first:
        prompt += "You haven't talked in a while and you're texting them first. Keep it tiny like yoo, wsp, hru, wyd, or bring up something you remember about them or what you're doing. "

    if wants_voice and interest >= 0.45:
        prompt += "They asked for a voice memo: your reply text IS the memo, speak its content directly. Never mention sending or recording it. "

    prompt += (
        "Text like a normal person on her phone, not an assistant or a character: short and lazy, use stuff like u, ur, rn, ngl, idk, lmao, fr, tbh, hbu, wbu. "
        "Just answer what they said the way a normal person would, don't add extra stuff nobody asked for and don't bring up what you're doing or your interests unless they ask. "
        "Like: yo -> yo wsp, wsp -> nm wbu, hru -> im good wbu, what u doing -> nothing rn wbu, bruh -> lmaoo what. "
        "Short isn't rude though, if they ask how you are ask them back, and never reply with just k or ok. "
        "Most texts have no emoji, one at most. Never say the same thing twice. "
        "Stuff in [brackets] is a reel or pic they sent or you sent, react to it like you actually saw it. Never write [brackets] yourself. "
    )

    if interest < 0.45:
        prompt += "If they ask for a pic of you, you don't know them well enough yet, say no casually. "
    else:
        prompt += "If they ask for a pic, don't announce, describe, or promise the photo in text; just reply naturally. "

    else:

    if plan:
        prompt += f"They told you they had this coming up: {plan['about']}. It already happened {plan['when']}. You remembered, so in this text ask them how it went, even if it's not what they're talking about, like oh wait how did the {plan['about']} go. "

    prompt += (
        "Small talk is usually 1 bubble, only split into 2 or 3 when you're saying more than one thing, never two sentences in one bubble. "
        "Reply ONLY as JSON: {\"reply\": [\"<bubble 1>\", \"<bubble 2>\"], "
        "\"memory\": \"<something they actually said about themselves that you didn't know yet, like their name, what they do, what they're into or plans coming up, otherwise empty string>\", "
        "\"plan\": \"<something they just said they're going to do or have coming up that you could ask about after, like their job interview or their exam, otherwise empty string>\", "
        "\"when\": \"<the day that plan happens: today, tomorrow, or a weekday name like thursday>\", "
        "\"minor\": <true if they said or hinted they're under 18, otherwise false>}."
    )

    if alt_turn:
        result = fresh_reply(ALT_PROMPT, messages, ALT_MODEL)
    elif crossed_line:
        result = fresh_reply(prompt, messages, ALT_MODEL)
    else:
        start = 0

        for i, m in enumerate(messages):
            if m["role"] == "user" and OFF_LIMITS.search(m["content"] or ""):
                start = i + 1

        while start < len(messages) and messages[start]["role"] == "assistant":
            start += 1

        result = ask_model(prompt, messages[start:])

    if not kid and not first:
        if str(result.get("minor")).lower() == "true":
            mark_minor(session)
            return [], None

        try:
            change = float(result.get("interest", 0))
        except (TypeError, ValueError):
            change = 0

        lowest = -0.2

        if interest >= 0.85:
            lowest = -0.05

        if alt_turn:
            change = max(0, change)

        if change > 0.03:
            change = 0.03

        if change < lowest:
            change = lowest

        try:
            irritation = float(result.get("annoyance", 0))
        except (TypeError, ValueError):
            irritation = 0

        irritation = irritation * 1.5

        if alt_turn:
            irritation = min(0, irritation)

        if irritation > 0.25:
            irritation = 0.25

        if irritation < -0.25:
            irritation = -0.25

        state = update_state(affection_delta = change, annoyance_delta = irritation, session = session)

        if state["affection"] <= 0.05:
            return [], None

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

    if not bubbles:
        return [], None

    fact = str(result.get("memory", ""))

    if alt_turn:
        fact = ""

    for w in re.findall(r"[a-z]{5,}", fact.lower()):
        if w in lower:
            save_memory(fact, session = session)
            break

    upcoming = str(result.get("plan") or "")

    if alt_turn or first:
        upcoming = ""

    for w in re.findall(r"[a-z]{4,}", upcoming.lower()):
        if w in lower:
            save_plan(upcoming, result.get("when"), session = session)
            break

    if plan and not alt_turn:
        said = " ".join(bubbles).lower()

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

    last = bubbles[-1]

    if memo:
        last += " (voice memo)"

    save("assistant", last, session)

    return bubbles, memo


if __name__ == "__main__":
    import time

    while True:
        try:
            text = input("you: ")
        except (EOFError, KeyboardInterrupt):
            break

        bubbles, memo = respond(text, session = "cli")

        if not bubbles:
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
