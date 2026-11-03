import os
import subprocess
import time

from datetime import datetime

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from main import respond

load_dotenv()

USERNAME = os.environ.get("INSTA_USERNAME", "")
PASSWORD = os.environ.get("INSTA_PASSWORD", "")

SESSION_FILE = os.path.join(os.path.dirname(__file__), "insta_session.json")


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


def run():
    cl = login()
    started = datetime.now()
    last_seen = {}
    last_read = {}

    print(f"logged in as @{USERNAME}")

    while True:
        try:
            threads = cl.direct_threads(amount = 20, thread_message_limit = 10) + cl.direct_pending_inbox(amount = 20)

            for thread in threads:
                if thread.is_group or len(thread.users) != 1:
                    continue

                user = thread.users[0]
                since = last_seen.get(thread.id, started)

                new = [
                    m for m in thread.messages
                    if str(m.user_id) == str(user.pk) and m.item_type == "text" and m.timestamp > since
                ]

                if not new:
                    continue

                session = f"insta:{user.pk}"

                # Mark ordinary inbox messages read as soon as we notice them,
                # even if the simulated reply delay has not elapsed yet.
                if not thread.pending:
                    newest = max(m.timestamp for m in new)
                    if newest > last_read.get(thread.id, started):
                        cl.direct_send_seen(thread.id)
                        last_read[thread.id] = newest

                new.sort(key = lambda m: m.timestamp)

                last_seen[thread.id] = new[-1].timestamp

                text = "\n".join(m.text for m in new)

                print(f"{user.username}: {text}")

                bubbles, memo = respond(text, session = session, name = user.username)

                if not bubbles:
                    continue

                if thread.pending:
                    cl.direct_pending_approve(thread.id)

                cl.direct_send_seen(thread.id)

                # the voice note says the last bubble, so that one doesn't get typed
                for bubble in bubbles[:-1] if memo else bubbles:
                    cl.direct_send(bubble, thread_ids = [thread.id])
                    print(f"claudina: {bubble}")

                if memo:
                    try:
                        # instagram only takes voice notes as m4a
                        m4a = memo.replace(".wav", ".m4a")
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", memo, m4a], check = True)
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

        time.sleep(1)


if __name__ == "__main__":
    run()
