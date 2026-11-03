import os
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

                new.sort(key = lambda m: m.timestamp)

                last_seen[thread.id] = new[-1].timestamp

                text = "\n".join(m.text for m in new)

                print(f"{user.username}: {text}")

                bubbles, memo = respond(text, session = f"insta:{user.pk}", name = user.username, voice = False)

                if not bubbles:
                    continue

                if thread.pending:
                    cl.direct_pending_approve(thread.id)

                cl.direct_send_seen(thread.id)

                for bubble in bubbles:
                    time.sleep(1 + len(bubble) / 10)
                    cl.direct_send(bubble, thread_ids = [thread.id])
                    print(f"claudina: {bubble}")

        except LoginRequired:
            cl.relogin()
            cl.dump_settings(SESSION_FILE)

        except Exception as e:
            print(f"error: {e}")

        time.sleep(30)


if __name__ == "__main__":
    run()
