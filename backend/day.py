import json

from datetime import timedelta

from available import WEEKDAY, WEEKEND, current_time
from db import conn

conn.execute("""
CREATE TABLE IF NOT EXISTS her_days (
    day TEXT PRIMARY KEY,
    events TEXT NOT NULL
)
""")
conn.commit()


def load_day(day):
    row = conn.execute("SELECT events FROM her_days WHERE day = ?", (day,)).fetchone()

    if row is None:
        return None

    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return []


def event_hour(event):
    return event["hour"]


def make_day(now, yesterday, ask):
    schedule = WEEKDAY

    if now.weekday() >= 5:
        schedule = WEEKEND

    plan = []

    for start, end, activity, available in schedule:
        plan.append(f"{start}:00-{end}:00 {activity}")

    prompt = (
        "You are writing the day of Claudina, 20, second year psych student in New York who lives in a dorm with her roommate Maya. "
        f"Today is {now:%A %B %d}. Her schedule today: " + ", ".join(plan) + ". "
        "Come up with 3 or 4 small normal things that happen to her today, the kind of stuff a girl would mention when someone asks how her day was. "
        "Like a quiz going badly, Maya eating her leftovers, the barista spelling her name wrong, a cute guy at the gym, her professor being weird, a funny tiktok. "
        "Nothing huge, no new family members, exes or trips. Each one has to fit what she's doing at that hour. "
    )

    if yesterday:
        what_happened = []

        for event in yesterday:
            what_happened.append(event["what"])

        prompt += "Yesterday: " + "; ".join(what_happened) + ". One of today's things can continue something from yesterday. "

    prompt += 'Reply ONLY as JSON: {"events": [{"hour": <0 to 23>, "what": "<one short sentence in third person>"}]}'

    result = ask(prompt, [{"role": "user", "content": "what happens today"}])
    events = []

    for event in result.get("events") or []:
        if not isinstance(event, dict):
            continue

        try:
            hour = int(event.get("hour"))
        except (TypeError, ValueError):
            continue

        what = str(event.get("what") or "").strip()

        if what and 0 <= hour <= 23:
            events.append({"hour": hour, "what": what})

    events.sort(key = event_hour)

    return events


def her_day(ask):
    now = current_time()
    today = now.date().isoformat()
    
    yesterday = (now.date() - timedelta(days = 1)).isoformat()

    yesterday_events = load_day(yesterday) or []
    today_events = load_day(today)

    if today_events is None:
        today_events = make_day(now, yesterday_events, ask)

        if today_events:
            conn.execute(
                "INSERT OR REPLACE INTO her_days (day, events) VALUES (?, ?)",
                (today, json.dumps(today_events)),
            )
            conn.commit()

    so_far = []

    for event in today_events:
        if event["hour"] <= now.hour:
            so_far.append(event["what"])

    before = []

    for event in yesterday_events:
        before.append(event["what"])

    return so_far, before
