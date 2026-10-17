import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from main import respond
from db import conn

MEMOS_DIR = os.path.join(os.path.dirname(__file__), "voice_memos")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["*"],
    allow_headers = ["*"],
)


class ChatIn(BaseModel):
    message: str
    session_id: str = ""
    api_key: str = ""


@app.post("/chat")
def chat_route(body: ChatIn):
    bubbles, memo = respond(body.message, session = body.session_id, api_key = body.api_key or None)
    voice_url = None

    if memo:
        voice_url = f"/voice/{os.path.basename(memo)}"

    return {"reply": bubbles[0], "bubbles": bubbles, "voice_url": voice_url}


@app.get("/history")
def history_route(session_id: str = ""):
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE session = ? AND content NOT LIKE '%(voice memo)' ORDER BY id ASC",
        (session_id,),
    ).fetchall()

    return {
        "messages": [
            {
                "who": "theirs" if row[0] == "assistant" else "mine",
                "text": row[1],
                "ts": row[2] + "Z",
            }
            for row in rows
        ]
    }


@app.get("/voice/{name}")
def voice_route(name: str):
    path = os.path.join(MEMOS_DIR, os.path.basename(name))

    if os.path.exists(path):
        media = "audio/wav" if name.endswith(".wav") else "audio/mpeg"
        return FileResponse(path, media_type = media)

    return {"error": "no such memo"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host = "0.0.0.0", port = 8000)
