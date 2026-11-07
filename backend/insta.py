import json
import os
import random
import re
import subprocess
import time

from datetime import datetime, timedelta

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import AccountSuspended, ChallengeRequired, FeedbackRequired, LoginRequired, PleaseWaitFewMinutes
from ollama import generate, ps

from available import get_status
from config import SEXUAL_INTENT
from day import her_day
from main import ask_model, respond, save, sexted_recently
from plans import due_plan
from reels import doomscroll, look, watch
from stories import posted_today, remember_story, story_reply, watch_stories
from state import get_state, is_adult_confirmed, is_minor

load_dotenv()

USERNAME = os.environ.get("INSTA_USERNAME", "")
PASSWORD = os.environ.get("INSTA_PASSWORD", "")

SESSION_FILE = os.path.join(os.path.dirname(__file__), "insta_session.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), "insta_state.json")
SELFIES_DIR = os.path.join(os.path.dirname(__file__), "selfies")
SELFIE_SCRIPT = os.path.join(os.path.dirname(__file__), "selfie.py")
SELFIE_PYTHON = os.path.join(os.path.dirname(__file__), "selfie-venv", "bin", "python")


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

    if due_plan(session) and datetime.now() - last.timestamp > timedelta(hours = 1):
        return True

    if str(last.user_id) != str(thread.users[0].pk) and interest < 0.85:
        return False

    if datetime.now() - last.timestamp <= timedelta(hours = 6):
        return False

    return random.random() < interest / 100


def sent_at(message):
    return message.timestamp


def send_pic(cl, thread_id, session, doing, asked, explicit = False):
    if explicit:
        prompt = (
            f"You are Claudina, a fictional adult woman, and {doing}. The person you're texting is a confirmed adult. "
            "Choose a specific consensual nude photo scene that fits what they asked for. Keep the scene short and natural. "
            'Reply ONLY as JSON: {"pic": "<short scene description>", "face": <true if your face is in it, otherwise false>}'
        )
    else:
        prompt = (
            f"You are Claudina, 20, psych student in New York. Someone you text asked for a pic and right now you are {doing}. "
            "Pick what you'd actually snap on your phone rn like a normal girl would, it doesn't have to be your face. "
            "Like a mirror pic of your outfit, your nails, your iced coffee, what you're cooking, your desk while studying, the view outside, or a selfie. "
            "It has to match what you're doing and what they asked for. Keep it casual and fully clothed. "
            'Reply ONLY as JSON: {"pic": "<what the photo shows>", "face": <true if your face is in it, otherwise false>}'
        )

    result = ask_model(prompt, [{"role": "user", "content": asked}])
    scene = str(result.get("pic") or f"selfie while {doing}")
    face = "noface"

    if str(result.get("face")).lower() == "true":
        face = "face"

    path = take_pic(scene, face, explicit)

    if not path:
        return

    cl.direct_send_photo(path, thread_ids = [thread_id])

    save("assistant", f"[sent a pic: {scene}]", session)
    print(f"claudina: [pic] {scene}")


def take_pic(scene, face, explicit = False):
    os.makedirs(SELFIES_DIR, exist_ok = True)
    path = os.path.join(SELFIES_DIR, f"{time.time_ns()}.jpg")

    try:
        for model in ps().models:
            generate(model = model.model, prompt = "", keep_alive = 0)
    except Exception as e:
        print(f"couldn't unload Ollama before image generation: {e}")

    print(f"taking a pic: {scene}")

    mode = "nsfw" if explicit else "sfw"
    
    result = subprocess.run(
        [SELFIE_PYTHON, SELFIE_SCRIPT, mode, scene, face, path],
        capture_output = True,
        text = True,
    )

    if result.returncode != 0:
        print(f"pic didnt work: {result.stderr[-500:]}")
        return None

    return path


def post_story(cl):
    today, _, _ = her_day(ask_model)

    if not today or posted_today() or random.random() > 0.3:
        return

    prompt = (
        f"You are Claudina, 20, psych student in New York. This just happened to you: {today[-1]}. "
        "You're posting it on your instagram story. Pick what the photo shows like a normal girl would post it, "
        "like your iced coffee, your notes, a mirror pic, your food, the view or a selfie. Keep it casual and fully clothed. "
        'Reply ONLY as JSON: {"pic": "<what the photo shows>", "face": <true if your face is in it, otherwise false>}'
    )

    result = ask_model(prompt, [{"role": "user", "content": today[-1]}])
    
    scene = str(result.get("pic") or today[-1])
    
    face = "noface"

    if str(result.get("face")).lower() == "true":
        face = "face"

    path = take_pic(scene, face)

    if not path:
        return

    story = cl.photo_upload_to_story(path)
    
    remember_story(story.pk, scene)
    
    print(f"posted a story: {scene}")


def profile(cl, user_id, profiles):
    if user_id in profiles:
        return profiles[user_id]

    try:
        info = cl.user_info(user_id)
    
    except (AccountSuspended, ChallengeRequired, FeedbackRequired, LoginRequired, PleaseWaitFewMinutes):
        raise
    
    except Exception as e:
        print(f"couldnt look at their profile: {e}")
        profiles[user_id] = ""
        
        return ""

    about = f"name {info.full_name}, bio: {' '.join((info.biography or '').split())}"

    if info.profile_pic_url:
        about += f", pfp: {look(info.profile_pic_url, None)}"

    profiles[user_id] = about

    return about


def affection(thread):
    if not thread.users:
        return 0

    return get_state(f"insta:{thread.users[0].pk}")["affection"]


def run():
    cl = login()
    last_seen = load_seen()
    last_read = {}
    next_open = 0
    next_scroll = 0
    next_stories = time.time() + random.randint(600, 1800)
    feed = []
    profiles = {}
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
            next_open = time.time() + random.randint(10, 60)
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
                    if str(m.user_id) == str(user.pk) and m.timestamp > since:
                        new.append(m)

                session = f"insta:{user.pk}"
                asked = ""

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
                        if m.reel_share:
                            line = story_reply(m)
                        else:
                            line = m.text or watch(m)

                        if line:
                            lines.append(line)

                        if m.text:
                            asked += m.text.lower()
                        elif m.item_type == "voice_media" and line:
                            asked += line.lower()

                    if not lines:
                        continue

                    if "reel" in asked:
                        next_scroll = 0

                    text = "\n".join(lines)
                    print(f"{user.username}: {text}")

                elif status["available"] and misses(thread, session):
                    text = None
                    print(f"texting {user.username} first")

                else:
                    continue

                about = profile(cl, user.pk, profiles)
                bubbles, memo = respond(text, session = session, name = user.username, profile = about)

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

                wants_pic = re.search(r"\b(pic|pics|selfie|photo)\b", asked)
                sexual = SEXUAL_INTENT.search(asked) or sexted_recently(session)

                if wants_pic and not sexual and affection(thread) >= 0.45 and os.path.exists(SELFIE_PYTHON):
                    send_pic(cl, thread.id, session, status["doing"], asked)

                if (
                    wants_pic
                    and sexual
                    and affection(thread) >= 0.75
                    and is_adult_confirmed(session)
                    and not is_minor(session)
                    and os.path.exists(SELFIE_PYTHON)
                ):
                    send_pic(cl, thread.id, session, status["doing"], asked, explicit = True)


            if status["available"] and time.time() > next_scroll:
                next_scroll = time.time() + random.randint(3600, 3 * 3600)
                feed = cl.reels(amount = 8)
                print("doomscrolling")

            if feed and status["available"]:
                doomscroll(cl, threads, feed.pop(0))
                next_open = time.time() + random.randint(2, 8)

            if status["available"] and time.time() > next_stories:
                next_stories = time.time() + random.randint(5400, 4 * 3600)
                watch_stories(cl, threads)

                if os.path.exists(SELFIE_PYTHON):
                    post_story(cl)

        except LoginRequired:
            cl.relogin()
            cl.dump_settings(SESSION_FILE)

        except AccountSuspended:
            print("instagram suspended her account, open instagram on your phone, log in as her and appeal it")
            return

        except (ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes) as e:
            print(f"instagram flagged her ({e}), stopping so it doesn't get worse")
            print("open instagram on your phone, log in as her and do whatever it asks, then start her again")
            return

        except Exception as e:
            print(f"error: {e}")
            time.sleep(15)

        time.sleep(5)


if __name__ == "__main__":
    try:
        run()
    except AccountSuspended:
        print("instagram suspended her account, open instagram on your phone, log in as her and appeal it")
    except ChallengeRequired as e:
        print(f"instagram won't let her log in: {e}")
        print("open instagram on your phone, log in as her and do whatever it asks, then start her again")
