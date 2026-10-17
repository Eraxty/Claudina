import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from ollama import chat

from db import conn
from available import get_status
from state import get_state
from voice import make_voice_memo
from memory import save_memory, top_memories

import json
import random

load_dotenv()

MODEL = os.environ["OLLAMA_MODEL"]

MEMOS_DIR = os.path.join(os.path.dirname(__file__), "voice_memos")


def ask_model(system_prompt, messages):
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = chat(model = MODEL, messages = full_messages, format = "json", think = False)

    try:
        return json.loads(response.message.content)
    except json.JSONDecodeError:
        return {"message": "wait my brain glitched"}


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000", "http://localhost:8000"],
    allow_methods = ["*"],
    allow_headers = ["*"],
)


class ChatIn(BaseModel):
    message: str


@app.post("/chat")
def chat_route(body: ChatIn):
    conn.execute(
        "INSERT INTO messages (role, content, created_at) VALUES (?, ?, datetime('now'))",
        ("user", body.message),
    )
    conn.commit()

    rows = conn.execute(
        "SELECT role, content FROM messages ORDER BY id DESC LIMIT 50"
    ).fetchall()
    history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]

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
    result = ask_model(system_prompt, history)
    reply = result.get("reply", "i dont feel soo good smh")

    fact = result.get("memory", "")
    if fact:
        save_memory(fact)

    voice_url = None
    if state["affection"] >= 0.3 and status["available"] and random.random() < 0.4:
        if state["annoyance"] >= 0.4:
            mood = "annoyed"
        elif state["affection"] >= 0.7:
            mood = "sweet"
        else:
            mood = "playful"
        memo = make_voice_memo(reply, mood)
        if memo:
            voice_url = f"/voice/{os.path.basename(memo)}"

    conn.execute(
        "INSERT INTO messages (role, content, created_at) VALUES (?, ?, datetime('now'))",
        ("assistant", reply),
    )
    conn.commit()

    return {"reply": reply, "voice_url": voice_url}


@app.get("/history")
def history_route():
    rows = conn.execute("SELECT role, content FROM messages ORDER BY id ASC").fetchall()

    return {"messages": [{"who": "theirs" if row[0] == "assistant" else "mine", "text": row[1]} for row in rows]}


@app.get("/voice/{name}")
def voice_route(name: str):
    safe = os.path.basename(name)
    path = os.path.join(MEMOS_DIR, safe)

    if os.path.exists(path):
        return FileResponse(path, media_type = "audio/mpeg")

    return {"error": "no such memo"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host = "0.0.0.0", port = 8000)
