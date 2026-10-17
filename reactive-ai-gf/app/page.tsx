"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  who: "mine" | "theirs";
  text: string;
  ts?: string;
  voice?: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PFP = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/avatar.png`;

const OFFLINE: { keys: string[]; bubbles: string[][] }[] = [
  { keys: ["hi", "hello", "hey", "yo", "sup"], bubbles: [["heyy 🥺", "hi babe", "wyd?"]] },
  { keys: ["love", "miss"], bubbles: [["i love you more 😭💕", "like actually so much", "when do i get to see u"]] },
  { keys: ["hackathon", "busy", "work", "code"], bubbles: [["damn the grind 😤", "ok but dont forget to eat", "proud of u fr 🥹"]] },
  { keys: ["gn", "sleep", "tired"], bubbles: [["nooo stay up w me 🥺", "jk go sleep babe", "dream of me or else 😌"]] },
  { keys: ["food", "eat", "hungry"], bubbles: [["omg food talk 😋", "order me something too", "im craving pasta rn"]] },
  { keys: ["??"], bubbles: [["hmm 🤔", "lemme think", "ok u first 👀"]] },
];

const OFFLINE_DEFAULT: string[][] = [
  ["hii 😊", "what r u up to"],
  ["fr?? 👀", "tell me more"],
  ["lmaooo 😂", "ur so dumb", "i love it"],
  ["ok that's kinda cute ngl 🥺", "go on"],
  ["wait really 😳", "u better not be lying to me 😤"],
];

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
  const sessionRef = useRef("");
  const keyRef = useRef("");
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
    let sessionId = "";

    try {
      sessionId = window.localStorage.getItem("claudina-session") || crypto.randomUUID();
      window.localStorage.setItem("claudina-session", sessionId);

      keyRef.current = window.localStorage.getItem("claudina-key") || "";
    } catch {
      sessionId = "anon";
    }

    if (!keyRef.current) {
      keyRef.current = window.prompt("your elevenlabs api key (your voice memos, your quota — press Cancel to skip)") || "";
      try {
        window.localStorage.setItem("claudina-key", keyRef.current);
      } catch {
        // storage blocked, fine
      }
    }

    sessionRef.current = sessionId;
    fetch(`${API}/history?session_id=${encodeURIComponent(sessionId)}`)
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

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  async function reveal(bubbles: string[]) {
    const startedAt = Date.now();

    for (const [i, bubble] of bubbles.entries()) {
      const typingFor = 900 + bubble.length * 50 + Math.random() * 1200;
      const wait = Math.max(200, typingFor - (Date.now() - startedAt));

      setHerTyping(true);
      await sleep(wait);

      setHerTyping(false);
      setMessages((prev) => [
        ...prev,
        { who: "theirs", text: bubble, ts: new Date().toISOString() },
      ]);

      if (i < bubbles.length - 1) {
        await sleep(500 + Math.random() * 1300);
      }
    }
  }

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
        body: JSON.stringify({ message, session_id: sessionRef.current, api_key: keyRef.current }),
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
        const bubbles: string[] = Array.isArray(data.bubbles) && data.bubbles.length
          ? data.bubbles
          : [data.reply ?? "you there??"];

        void reveal(bubbles);
      }
    } catch {
      setRead((r) => new Set(r).add(myIndex));

      const pool = OFFLINE.find((entry) =>
        entry.keys.some((key) => message.toLowerCase().includes(key)),
      );
      const groups = pool ? pool.bubbles : OFFLINE_DEFAULT;

      void reveal(groups[Math.floor(Math.random() * groups.length)] ?? ["hii 😊"]);
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
          <img src={PFP} alt="" className="mini" />
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
        <img src={PFP} alt="" className="mini" />
        <p ref={isLastMessage ? lastMessageRef : undefined}>{message.text}</p>
      </div>
    );
  });

  return (
    <main>
      <header>
        <img src={PFP} alt="" className="avatar" />
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
