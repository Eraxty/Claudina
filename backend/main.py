import json
import os

from dotenv import load_dotenv
from ollama import chat

from db import conn
from available import get_status
from state import get_state
from voice import make_voice_memo
from memory import save_memory, top_memories

import random

load_dotenv()

MODEL = os.environ["OLLAMA_MODEL"]


def ask_model(system_prompt, messages):
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = chat(model = MODEL, messages = full_messages, format = "json", think = False)

    try:
        return json.loads(response.message.content)
    
    except json.JSONDecodeError:
        return {"message": "wait my brain glitched"}


messages = []
while True:
    
    try:
        text = input("you: ")
    except (EOFError, KeyboardInterrupt):
        break

    messages.append({"role": "user", "content": text})
    
    conn.execute(
        "INSERT INTO messages (role, content, created_at) VALUES (?, ?, datetime('now'))",
        ("user", text),
    )
    
    conn.commit()

    state = get_state()
    status = get_status()

    known = top_memories()
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
        "When he shares something, REACT first (damn, no way, omg, yep fr) then ask ONE follow-up question about it "
        "so the convo keeps going. Never let a topic die. Vary your openers, never the same one twice. "
        "Examples of yours: he says 'i benched 60kg today' -> you say 'damn 60 on day one? tell me more'; "
        "he says 'i aced my exam' -> you say 'no wayy ik im so proud,' then 'what was it on'. "
        "Reply ONLY as JSON: {\"reply\": \"...\", \"memory\": \"<very short fact about him from this message, or empty string if nothing worth remembering>\"}."
        " Be short and casual, like texting."
    )
    result = ask_model(system_prompt, messages)
    reply = result.get("reply", "i dont feel soo good smh")

    fact = result.get("memory", "")
    if fact:
        save_memory(fact)

    memo = None
    if state["affection"] >= 0.3 and status["available"] and random.random() < 0.4:
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7:
            mood = "sweet"
        else:
            mood = "playful"
        memo = make_voice_memo(reply, mood)

    if memo:
        print("claudina: [voice memo]")
        os.system(f"mpv --no-video {memo} >/dev/null 2>&1")
    else:
        print(f"claudina: {reply}")

    messages.append({"role": "assistant", "content": reply})

    conn.execute(
        "INSERT INTO messages (role, content, created_at) VALUES (?, ?, datetime('now'))",
        ("assistant", reply),
    )
    conn.commit()
