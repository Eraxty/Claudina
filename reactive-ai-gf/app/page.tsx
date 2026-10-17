"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  who: "mine" | "theirs";
  text: string;
  voice?: string;
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
  const [herTyping, setHerTyping] = useState(false);
  const [conversationLoaded, setConversationLoaded] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const lastMessageRef = useRef<HTMLParagraphElement | null>(null);

  function toggleMemo(url: string) {
    if (playing === url) {
      audio.current?.pause();
      setPlaying(null);
      return;
    }

    audio.current?.pause();
    const el = new Audio(`${API}${url}`);
    audio.current = el;
    el.onended = () => setPlaying(null);
    setPlaying(url);
    void el.play();
  }

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
    setHerTyping(true);
    const startedAt = Date.now();

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();

      if (data.voice_url) {
        const wait = Math.max(0, 2500 - (Date.now() - startedAt));

        setTimeout(() => {
          setHerTyping(false);
          const url = `${API}${data.voice_url}`;
          setMessages((prev) => [
            ...prev,
            { who: "theirs", text: "Voice memo", voice: data.voice_url },
          ]);
          const el = new Audio(url);
          audio.current = el;
          el.onended = () => setPlaying(null);
          setPlaying(data.voice_url);
          void el.play();
        }, wait);
      } 
      
      else {
        const reply = data.reply ?? "you there??";
        const typingFor = 1200 + reply.length * 60 + Math.random() * 1500;
        const wait = Math.max(200, typingFor - (Date.now() - startedAt));

        setTimeout(() => {
          setHerTyping(false);
          setMessages((prev) => [...prev, { who: "theirs", text: reply }]);
        }, wait);
      }
    } catch {
      setHerTyping(false);
      setMessages((prev) => [
        ...prev,
        { who: "theirs", text: "you there?? signal dropped" },
      ]);
    }
  }

  return (
    <main>
      <header>
        <img src="/avatar.png" alt="" className="avatar" />
        <h1>Claudina</h1>
      </header>

      <div className="chat">
        {messages.map((message, index) => {
          const isLastMessage = index === messages.length - 1;

          if (message.voice) {
            return (
              <p
                key={index}
                className={`memo${playing === message.voice ? " playing" : ""}`}
                onClick={() => toggleMemo(message.voice as string)}
                ref = {isLastMessage ? lastMessageRef : undefined}
              >
                <span className="chip"></span>Voice memo
              </p>
            );
          }

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

        {herTyping && (
          <p className="typing">
            <span></span>
            <span></span>
            <span></span>
          </p>
        )}
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
