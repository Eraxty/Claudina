import random
import time

from available import current_time
from db import conn
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

            if random.random() < close:
                cl.story_like(story.id)
                print(f"liked {user.username}'s story")
