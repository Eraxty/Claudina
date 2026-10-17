"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  who: "mine" | "theirs";
  text: string;
};

const API = "http://localhost:8000";

const STORAGE_KEY = "claudina-chat";

function loadSavedMessages(): Message[] {
  let saved: string | null = null;

  try {
    saved = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // storage blocked, just start empty
    return [];
  }

  if (saved === null) {
    return [];
  }

  let parsed: unknown;

  try {
    parsed = JSON.parse(saved);
  } catch {
    // saved chat is broken, start empty
    return [];
  }

  if (!Array.isArray(parsed)) {
    return [];
  }

  const validMessages: Message[] = [];

  for (const item of parsed) {
    if (typeof item?.text === "string") {
      if (item.who === "mine" || item.who === "theirs") {
        validMessages.push(item);
      }
    }
  }

  return validMessages;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [conversationLoaded, setConversationLoaded] = useState(false);
  const lastMessageRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    fetch(`${API}/history`)
      .then((r) => r.json())
      .then((data) => {
        if (data.messages?.length) {
          setMessages(data.messages);
        } else {
          setMessages(loadSavedMessages());
        }
      })
      .catch(() => {
        setMessages(loadSavedMessages());
      });
    setConversationLoaded(true);
  }, []);

  // save the conversation every time it changes
  useEffect(() => {
    if (!conversationLoaded) {
      return;
    }

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // storage full or blocked, keep chatting anyway
    }
  }, [messages, conversationLoaded]);

  // keep the newest message visible
  useEffect(() => {
    if (lastMessageRef.current) {
      lastMessageRef.current.scrollIntoView({
        block: "end",
        behavior: "smooth",
      });
    }
  }, [messages]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const message = text.trim();

    if (message === "") {
      return;
    }

    setMessages([...messages, { who: "mine", text: message }]);
    setText("");

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      
      const data = await res.json();
      setMessages((prev) => [...prev, { who: "theirs", text: data.reply }]);

      if (data.voice_url) {
        void new Audio(`${API}${data.voice_url}`).play();
      }} 
      catch {
      setMessages((prev) => [
        ...prev,
        { who: "theirs", text: "you there?? signal dropped" },
      ]);
    }
  }

  return (
    <main>
      <header>
        <div className="avatar">C</div>
        <h1>Claudina</h1>
      </header>

      <div className="chat">
        {messages.map((message, index) => {
          const isLastMessage = index === messages.length - 1;

          return (
            <p
              key={index}
              className={message.who === "mine" ? "mine" : ""}
              ref={isLastMessage ? lastMessageRef : undefined}
            >
              {message.text}
            </p>
          );
        })}
      </div>

      <form onSubmit={send}>
        <input
          name="message"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <button type="submit">Send</button>
      </form>
    </main>
  );
}
