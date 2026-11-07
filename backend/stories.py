import json
import random
import time

from available import current_time
from db import conn
from main import ask_model, save
from memory import top_memories
from reels import look
from state import get_state, is_minor

conn.execute("""
CREATE TABLE IF NOT EXISTS seen_stories (
    pk TEXT PRIMARY KEY)""")

conn.execute("""
CREATE TABLE IF NOT EXISTS her_stories (
    pk TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    day TEXT NOT NULL)""")

conn.commit()


def posted_today():
    today = current_time().date().isoformat()
    row = conn.execute("SELECT 1 FROM her_stories WHERE day = ?", (today,)).fetchone()

    return row is not None


def remember_story(pk, scene):
    today = current_time().date().isoformat()
    conn.execute("INSERT OR REPLACE INTO her_stories (pk, scene, day) VALUES (?, ?, ?)", (str(pk), scene, today))
    conn.commit()


def story_reply(m):
    share = m.reel_share or {}
    text = str(share.get("text") or m.text or "").strip()
    media = share.get("media") or {}

    row = conn.execute("SELECT scene FROM her_stories WHERE pk = ?", (str(media.get("pk") or ""),)).fetchone()
    story = "your story"

    if row:
        story = f"your story of {row[0]}"

    if share.get("type") == "mention":
        return "[mentioned you in their story]"

    if share.get("type") == "reaction":
        return f"[reacted {text} to {story}]"

    return f"[replied to {story}: {text}]"


def think_about_story(username, close, session, seen):
    if close >= 0.85:
        stage = "you're dating them"
    elif close >= 0.7:
        stage = "you have a crush on them"
    else:
        stage = "you're friends"

    prompt = (
        f"You are Claudina, 20, second year psych student in New York. You're watching {username}'s instagram story and {stage}. "
        "The user message is what's in the story. "
    )

    known = top_memories(session = session)

    if known:
        prompt += "What you know about them: " + "; ".join(known) + ". "

    prompt += (
        "You feel like replying to this one. Say something about what's actually in it like a normal girl would, tiny and lazy, like wait where is this, omg who's that, the fit tho, need, LMAOO. "
        "Only leave reply empty if there's really nothing to say about it. "
        'Reply ONLY as JSON: {"reply": "<your reply or empty string>", "like": <true or false>}'
    )

    return ask_model(prompt, [{"role": "user", "content": seen}])


def reply_to_story(cl, thread_id, story, text):
    media_type = "photo"

    if story.media_type == 2:
        media_type = "video"

    token = cl.generate_mutation_token()

    data = {
        "action": "send_item",
        "client_context": token,
        "mutation_token": token,
        "offline_threading_id": token,
        "device_id": cl.android_device_id,
        "_uuid": cl.uuid,
        "thread_ids": json.dumps([int(thread_id)]),
        "media_id": story.id,
        "reel_id": str(story.user.pk),
        "text": text,
        "entry": "reel",
    }

    cl.private_request(
        f"direct_v2/threads/broadcast/reel_share/?media_type={media_type}",
        data = cl.with_default_data(data),
        with_signature = False,
    )


def watch_stories(cl, threads):
    watched = 0

    for thread in threads:
        if watched >= 6:
            break

        if thread.is_group or thread.pending or len(thread.users) != 1:
            continue

        user = thread.users[0]

        session = f"insta:{user.pk}"

        close = get_state(session)["affection"]

        if close < 0.3 or is_minor(session):
            continue

        watched += 1

        for story in cl.user_stories(user.pk, amount = 3):

            seen = conn.execute("SELECT 1 FROM seen_stories WHERE pk = ?", (str(story.pk),)).fetchone()

            if seen:
                continue

            conn.execute("INSERT INTO seen_stories (pk) VALUES (?)", (str(story.pk),))
            conn.commit()

            time.sleep(random.randint(3, 10))
            cl.story_seen([story.pk])

            print(f"watched {user.username}'s story")

            like = random.random() < close

            if close >= 0.45 and random.random() < 0.3:
                seen = look(story.thumbnail_url, story.video_url)
                result = think_about_story(user.username, close, session, seen)
                text = str(result.get("reply") or "").strip().lower()
                like = str(result.get("like")).lower() == "true"

                if text:
                    time.sleep(random.randint(3, 12))

                    try:
                        reply_to_story(cl, thread.id, story, text)
                        save("assistant", f"[you replied to their story of {seen}: {text}]", session)
                        print(f"replied to {user.username}'s story: {text}")
                    except Exception as e:
                        print(f"couldnt reply to their story: {e}")

            if like:
                cl.story_like(story.id)
                print(f"liked {user.username}'s story")
