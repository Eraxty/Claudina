"use client";

import { FormEvent, useState, useSyncExternalStore } from "react";

type Message = {
  who: "mine" | "theirs";
  text: string;
};

const SEED_MESSAGES: Message[] = [
  { who: "theirs", text: "hey, how are you?" },
  { who: "mine", text: "i'm good. how was your day?" },
  { who: "theirs", text: "pretty calm. i just wanted to talk to you." },
];

const STORAGE_KEY = "claudina-chat";

function loadMessages(): Message[] {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.filter(
          (message): message is Message =>
            typeof message?.text === "string" &&
            (message.who === "mine" || message.who === "theirs")
        );
      }
    }
  } catch {
    // unreadable saved chat (JSON error etc.) — fall back to the seed
  }
  return SEED_MESSAGES;
}

/**
 * The conversation lives in localStorage and React subscribes to it through
 * useSyncExternalStore. That way the chat is rendered safely on the server
 * (seed messages) and switched to the saved history right after hydration.
 */
const chatStore = {
  listeners: new Set<() => void>(),
  snapshot: null as Message[] | null,

  subscribe(listener: () => void) {
    chatStore.listeners.add(listener);
    return () => chatStore.listeners.delete(listener);
  },

  getSnapshot(): Message[] {
    if (chatStore.snapshot === null) {
      chatStore.snapshot = loadMessages();
    }
    return chatStore.snapshot;
  },

  // No storage on the server — render the seed conversation for SSR.
  getServerSnapshot(): Message[] {
    return SEED_MESSAGES;
  },

  set(messages: Message[]) {
    chatStore.snapshot = messages;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // storage full or blocked — chat still works, just won't persist
    }
    for (const listener of chatStore.listeners) listener();
  },
};

export default function Home() {
  const messages = useSyncExternalStore(
    chatStore.subscribe,
    chatStore.getSnapshot,
    chatStore.getServerSnapshot
  );
  const [text, setText] = useState<string>("");

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!text.trim()) return;
    chatStore.set([...chatStore.getSnapshot(), { who: "mine", text: text.trim() }]);
    setText("");
  }

  return (
    <main>
      <header>
        <div className="avatar">C</div>
        <div>
          <h1>Claudina</h1>
          <small>Active now</small>
        </div>
      </header>

      <div className="chat">
        {messages.map((message, index) => (
          <p className={message.who === "mine" ? "mine" : ""} key={index}>
            {message.text}
          </p>
        ))}
      </div>

      <form onSubmit={send}>
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Message Claudina..."
          name="message"
        />
        <button type="submit">Send</button>
      </form>
    </main>
  );
}
