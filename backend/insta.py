import json
import os
import random
import subprocess
import time

from datetime import datetime, timedelta

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from available import get_status
from main import respond
from state import get_state, is_minor

load_dotenv()

USERNAME = os.environ.get("INSTA_USERNAME", "")
PASSWORD = os.environ.get("INSTA_PASSWORD", "")

SESSION_FILE = os.path.join(os.path.dirname(__file__), "insta_session.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), "insta_state.json")


class InstaClient(Client):
    def password_publickeys(self):
        resp = self.private.post(
            "https://i.instagram.com/api/v1/launcher/sync/",
            data = {"id": self.uuid, "server_config_retrieval": "1"},
        )

        return int(resp.headers["ig-set-password-encryption-key-id"]), resp.headers["ig-set-password-encryption-pub-key"]


def login():
    cl = InstaClient()

    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)

    cl.login(USERNAME, PASSWORD)
    cl.dump_settings(SESSION_FILE)

    return cl


def load_seen():
    try:
        with open(STATE_FILE) as f:
            saved = json.load(f).get("last_seen")
    except (OSError, ValueError, AttributeError):
        return {}

    if not isinstance(saved, dict):
        return {}

    seen = {}

    for thread_id, stamp in saved.items():
        seen[thread_id] = datetime.fromisoformat(stamp)

    return seen


def save_seen(last_seen):
    saved = {}

    for thread_id, stamp in last_seen.items():
        saved[thread_id] = stamp.isoformat()

    with open(STATE_FILE, "w") as f:
        json.dump({"last_seen": saved}, f)


def misses(thread, session):
    interest = get_state(session)["affection"]

    if interest < 0.45 or is_minor(session) or thread.pending or not thread.messages:
        return False

    last = thread.messages[0]

    for m in thread.messages:
        if m.timestamp > last.timestamp:
            last = m

    if str(last.user_id) != str(thread.users[0].pk) and interest < 0.85:
        return False

    if datetime.now() - last.timestamp <= timedelta(hours = 6):
        return False

    return random.random() < interest / 100


def sent_at(message):
    return message.timestamp


def affection(thread):
    if not thread.users:
        return 0

    return get_state(f"insta:{thread.users[0].pk}")["affection"]


def run():
    cl = login()
    last_seen = load_seen()
    last_read = {}
    next_open = 0
    was_free = False

    print(f"logged in as @{USERNAME}")

    while True:
        status = get_status()

        # check msgs in morning if shes sleeping
        if status["doing"] == "sleeping":
            time.sleep(60)
            continue

        # checks phone when free
        if status["available"] and not was_free:
            next_open = 0

        was_free = status["available"]

        if time.time() < next_open:
            time.sleep(5)
            continue

        if status["available"]:
            next_open = time.time() + random.randint(30, 300)
        else:
            next_open = time.time() + random.randint(900, 2700)

        try:
            threads = cl.direct_threads(amount = 20, thread_message_limit = 10) + cl.direct_pending_inbox(amount = 20)
            threads.sort(key = affection, reverse = True)

            for thread in threads:
                if thread.is_group or len(thread.users) != 1:
                    continue

                user = thread.users[0]

                # reply to whatever came after her last text, skip stuff older than 2 days
                since = last_seen.get(thread.id, datetime.now() - timedelta(days = 2))

                for m in thread.messages:
                    if str(m.user_id) != str(user.pk):
                        since = max(since, m.timestamp)

                new = []

                for m in thread.messages:
                    if str(m.user_id) == str(user.pk) and m.item_type == "text" and m.timestamp > since:
                        new.append(m)

                session = f"insta:{user.pk}"

                if new:
                    new.sort(key = sent_at)
                    newest = new[-1].timestamp

                    if not thread.pending and newest > last_read.get(thread.id, datetime.min):
                        cl.direct_send_seen(thread.id)
                        last_read[thread.id] = newest

                    last_seen[thread.id] = newest
                    save_seen(last_seen)
                    lines = []

                    for m in new:
                        lines.append(m.text)

                    text = "\n".join(lines)
                    print(f"{user.username}: {text}")

                elif status["available"] and misses(thread, session):
                    text = None
                    print(f"texting {user.username} first")

                else:
                    continue

                bubbles, memo = respond(text, session = session, name = user.username)

                if not bubbles:
                    continue

                if thread.pending:
                    cl.direct_pending_approve(thread.id)

                cl.direct_send_seen(thread.id)

                # the voice note says the last bubble, so that one doesn't get typed
                typed = bubbles

                if memo:
                    typed = bubbles[:-1]

                for bubble in typed:
                    time.sleep(1 + len(bubble) / 10)
                    cl.direct_send(bubble, thread_ids = [thread.id])
                    print(f"claudina: {bubble}")

                if memo:
                    try:
                        # instagram only takes voice notes as m4a
                        m4a = memo.replace(".wav", ".m4a")
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", memo, m4a], check = True)
                        time.sleep(2 + len(bubbles[-1]) / 15)
                        cl.direct_send_voice(m4a, thread_ids = [thread.id])
                        print(f"claudina: [voice note] {bubbles[-1]}")
                    except Exception as e:
                        print(f"voice note didnt send, texting it instead: {e}")
                        cl.direct_send(bubbles[-1], thread_ids = [thread.id])

        except LoginRequired:
            cl.relogin()
            cl.dump_settings(SESSION_FILE)

        except Exception as e:
            print(f"error: {e}")
            time.sleep(15)

        time.sleep(5)


if __name__ == "__main__":
    run()
