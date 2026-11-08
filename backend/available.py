import random

from datetime import datetime
from zoneinfo import ZoneInfo

from config import HER_TIMEZONE


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

SPONTANEOUS = ["napping", "in the shower", "on a call with her mom", "out getting food"]


def current_time():
    return datetime.now(ZoneInfo(HER_TIMEZONE)).replace(tzinfo = None)


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
