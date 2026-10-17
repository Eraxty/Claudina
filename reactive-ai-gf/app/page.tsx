"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  who: "mine" | "theirs";
  text: string;
  ts?: string;
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
  const [read, setRead] = useState<Set<number>>(new Set());
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

  // keep the newest message visible, insta-style: instant on big jumps, smooth otherwise
  const prevCount = useRef(0);

  useEffect(() => {
    if (!lastMessageRef.current) {
      return;
    }

    const jump = Math.abs(messages.length - prevCount.current);
    prevCount.current = messages.length;

    lastMessageRef.current.scrollIntoView({
      block: "end",
      behavior: jump > 3 ? "auto" : "smooth",
    });
  }, [messages]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const message = text.trim();

    if (message === "") {
      return;
    }

    const myIndex = messages.length;
    setMessages([
      ...messages,
      { who: "mine", text: message, ts: new Date().toISOString() },
    ]);
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
      setRead((r) => new Set(r).add(myIndex));

      if (data.voice_url) {
        const wait = Math.max(0, 2500 - (Date.now() - startedAt));

        setTimeout(() => {
          setHerTyping(false);
          const url = `${API}${data.voice_url}`;
          setMessages((prev) => [
            ...prev,
            { who: "theirs", text: "Voice memo", voice: data.voice_url, ts: new Date().toISOString() },
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
          setMessages((prev) => [
            ...prev,
            { who: "theirs", text: reply, ts: new Date().toISOString() },
          ]);
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

  const rows: React.ReactNode[] = [];
  let lastDay = "";

  messages.forEach((message, index) => {
    const day = new Date(message.ts ?? Date.now()).toLocaleString([], {
      month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
    });

    if (message.ts && day !== lastDay) {
      rows.push(<p key={`d-${index}`} className="day">{day}</p>);
      lastDay = day;
    }

    const isLastMessage = index === messages.length - 1;

    if (message.voice) {
      rows.push(
        <div key={index} className="row">
          <img src="/avatar.png" alt="" className="mini" />
          <p
            className={`memo${playing === message.voice ? " playing" : ""}`}
            onClick={() => toggleMemo(message.voice as string)}
            ref={isLastMessage ? lastMessageRef : undefined}
          >
            <span className="chip"></span>
            <span className="wave">
              {[3, 7, 5, 9, 6, 10, 4, 8, 5, 9, 6, 4].map((h, i) => (
                <i key={i} style={{ height: `${h}px`, animationDelay: `${i * 0.07}s` }}></i>
              ))}
            </span>
          </p>
        </div>
      );
      return;
    }

    if (message.who === "mine") {
      rows.push(
        <div key={index} className="mine-wrap">
          <p className="mine" ref={isLastMessage ? lastMessageRef : undefined}>
            {message.text}
          </p>
          <span className="ticks">{read.has(index) ? "✓✓" : "✓"}</span>
        </div>
      );
      return;
    }

    rows.push(
      <div key={index} className="row">
        <img src="/avatar.png" alt="" className="mini" />
        <p ref={isLastMessage ? lastMessageRef : undefined}>{message.text}</p>
      </div>
    );
  });

  return (
    <main>
      <header>
        <img src="/avatar.png" alt="" className="avatar" />
        <div>
          <h1>Claudina</h1>
          <small>{herTyping ? "typing..." : "Active now"}</small>
        </div>
      </header>

      <div className="chat">
        <div className="list">
          {rows}

          {herTyping && (
            <p className="typing">
              <span></span>
              <span></span>
              <span></span>
            </p>
          )}
        </div>
      </div>

      <form onSubmit={send}>
        <input
          name="message"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Message..."
        />
        <button type="submit">Send</button>
      </form>
    </main>
  );
}
