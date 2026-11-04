import json
import random
import os

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


WEEKDAY = [
    (0, 1, "in bed on her phone", True),
    (1, 8, "sleeping", False),
    (8, 9, "getting ready for class", True),
    (9, 13, "in class", False),
    (13, 14, "eating lunch with friends", True),
    (14, 16, "in class", False),
    (16, 18, "at the gym", False),
    (18, 20, "studying", True),
    (20, 24, "free", True),
]

WEEKEND = [
    (0, 3, "out with friends", True),
    (3, 11, "sleeping", False),
    (11, 13, "lazy in bed", True),
    (13, 19, "out with friends", True),
    (19, 24, "chilling at home", True),
]

OFFSET_FILE = os.path.join(os.path.dirname(__file__), "clock_offset.json")

SPONTANEOUS = ["napping", "in the shower", "on a call with her mom", "out getting food"]


def _load_offset():
    try:
        with open(OFFSET_FILE) as f:
            return json.load(f).get("hours", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def skip_time(hours = 0):
    offset = _load_offset() + hours
    
    with open(OFFSET_FILE, "w") as f:
        json.dump({"hours": offset}, f)

    return offset


def current_time():
    # she lives in new york so follow NY time
    return datetime.now(ZoneInfo("America/New_York")).replace(tzinfo = None) + timedelta(hours = _load_offset())


def get_status(now = None):
    now = now or current_time()
    schedule = WEEKDAY

    if now.weekday() >= 5:
        schedule = WEEKEND

    roll = random.Random(now.strftime("%Y-%m-%d %H"))

    for start, end, activity, available in schedule:
        if start <= now.hour < end:
            if available and roll.random() < 0.2:
                return {"available": False, "doing": roll.choice(SPONTANEOUS)}

            return {"available": available, "doing": activity}

    return {"available": True, "doing": "free"}
