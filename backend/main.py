import json
import os

from dotenv import load_dotenv
from ollama import chat

from db import conn
from available import get_status
from state import get_state

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
        "Reply ONLY as JSON: {\"reply\": \"...\"}. Be short and casual, like texting."
    )
    
    reply = ask_model(system_prompt, messages).get("reply", "i dont feel soo good smh")

    print(f"claudina: {reply}")
    
    messages.append({"role": "assistant", "content": reply})
    
    conn.execute(
        "INSERT INTO messages (role, content, created_at) VALUES (?, ?, datetime('now'))",
        ("assistant", reply),
    )
    conn.commit()
