import json
import random
import os

from datetime import datetime, timedelta

SCHEDULE = [
    (0, 8, "sleeping", False),
    (8, 10, "getting ready", True),
    (10, 12, "at the gym", False),
    (12, 17, "college classes", False),
    (17, 23, "free", True),
]

OFFSET_FILE = os.path.join(os.path.dirname(__file__), "clock_offset.json")

SPONTANEOUS = ["doomscrolling insta", "napping", "out with friends"]


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
    return datetime.now() + timedelta(hours = _load_offset())


def get_status(now = None):
    hour = (now or current_time()).hour

    for start, end, activity, available in SCHEDULE:
    
        if start <= hour < end:
   
            if available and random.random() < 0.3:
                return {"available": False, "doing": random.choice(SPONTANEOUS)}
   
            return {"available": available, "doing": activity}

    return {"available": True, "doing": "free"}
