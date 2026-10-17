# Claudina

A local AI girlfriend that lives in your browser

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org) [![Next.js](https://img.shields.io/badge/next.js-16-black.svg)](https://nextjs.org) [![Ollama](https://img.shields.io/badge/local%20model-ollama-white.svg)](https://ollama.com)

[Features](#features) • [Install](#installation) • [Usage](#usage) • [How it works](#how-it-works) • [Chat backup](#backing-up-the-chat) • [Credits](#credits)

---

## Why Claudina

In today's world of loneliness,all a man wants is a companion who is a star in his galaxy But in nowadays finding the right companion just became a lot harder.To solve this problem we have created an AI which is exactly your type so you don't have to worry about finding your perfect match.Although she can be a handful sometimes but you will find her pretty sweet.

## Features

- Chat UI that actually feels like textng,bubbles and resposive texts
- Replies come through a model running through Ollama,` no cloud is involved
- The conversations will be saved in your browser,you close the tab and it will still be there when you come back

## Installation

- Python 3.10+
- Node.js
```
git clone https://github.com/Eraxty/Claudina
cd Claudina

backend:
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

frontend:
cd ../reactive-ai-gf
npm install
```


## Usage

Run the two halves in separate terminals:

```
# terminal 1, from backend/
source .venv/bin/activate
python main.py

# terminal 2,from reactive-ai-gf/
npm run dev
```

Open `http://localhost:3000`,type something,hit send.

### Chat history

Every message keeps getting saved to your browser's localStorage under the claudina chat key.Refresh,close the tab,reboot and the conversation is still there.If you clear your browser data the chat starts fresh,which is also the reset button if she remembers something you'd rather forget.

### Making her yours

The whole personality is one string in backend/main.py.The backend forces the model to reply as JSON (`{"reply": "..."}`),so the frontend only ever sees the clean reply text, even when the model starts rambling around it.

## How it works

Short version:

1. You type a message in the browser,it shows up as your bubble
2. The backend sends the conversation to Ollama with a system prompt and asks for a JSON reply
3. The reply is parsed and lands back in the chat as her bubble

The frontend never talks to the model directly,it only knows about the backend.The backend never talks to the internet,it only knows about Ollama.

## Backing up the chat

There's no database here,chats live in your browser's local storage.If you want to keep one,open devtools,go to Application>Local Storage,and copy the claudina-chat key somewhere safe.Pasting it back restores the conversation.

## Limitation

- Replies are only as fast as your device,since the model runs locally.Good on a GPU,slow on CPU.
- Ollama needs to be running before you start the backend,otherwise the first message just hangs.
- One conversation for now,no personas,no memory beyond the current chat.Voice replies are planned,the ElevenLabs package is already sitting in package.json waiting.

## Credits

Built by [Eraxty](https://github.com/Eraxty) and [Xorim](https://github.com/Xorim).The frontend was bootstrapped with create next app,styled with Tailwind,icons from lucide.Everything else is mine.

## License

[MIT](LICENSE).
