import json
import os

from dotenv import load_dotenv
from ollama import chat

load_dotenv()

MODEL = os.environ["OLLAMA_MODEL"]


def ask_model(system_prompt, messages):
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = chat(model = MODEL, messages = full_messages, format = "json", think = False)
    
    try:
        return json.loads(response.message.content)
    
    except json.JSONDecodeError:
        return {"message": "wait my brain glitched"}

print(ask_model(
    "You are Claudina, texting your boyfriend. Reply ONLY as JSON: {\"reply\": \"...\"}. "
    "Example: user says 'yo', you reply {\"reply\": \"heyyy\"}.",
    [{"role": "user", "content": "yo"}],
))