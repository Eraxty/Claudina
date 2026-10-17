import json
import os

from dotenv import load_dotenv
from ollama import chat

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
    text = input("you: ")
    messages.append({"role": "user", "content": text})

    state = get_state()
    result = ask_model(
        f"You are Claudina, texting your boyfriend. Current trust: {state['trust']}, affection: {state['affection']}, annoyance: {state['annoyance']}. "
        "Reply ONLY as JSON: {\"reply\": \"...\"}. Example: user says 'yo', you reply {\"reply\": \"heyyy\"}.",
        messages,
    )

    reply = result.get("reply", "wait my brain glitched smh")
    
    print(f"claudina: {reply}")
    messages.append({"role": "assistant", "content": reply})