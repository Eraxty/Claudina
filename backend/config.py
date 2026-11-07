import os
import re

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

HER_NAME = os.environ.get("HER_NAME") or "Claudina"
HER_LIFE = os.environ.get("HER_LIFE") or "second year psych student in New York who lives in a dorm with her roommate Maya"

try:
    HER_AGE = int(os.environ.get("HER_AGE") or "20")
except ValueError:
    raise SystemExit("HER_AGE in backend/.env has to be a number")

if HER_AGE < 18:
    raise SystemExit("HER_AGE in backend/.env has to be 18 or older")

HER_TIMEZONE = os.environ.get("HER_TIMEZONE") or "America/New_York"

try:
    ZoneInfo(HER_TIMEZONE)
except (ZoneInfoNotFoundError, ValueError):
    raise SystemExit(f"HER_TIMEZONE in backend/.env isn't a real timezone, use one like America/New_York or Europe/London")


UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)


OFF_LIMITS = re.compile(
    re.IGNORECASE,
)

REFUSAL = re.compile(
    r"(?:cant|can'?t|can not|won'?t|will not)\s+(?:continue|do this|keep going)"
    r"|not comfortable\s+(?:with|talking|continuing)"
    r"|i'?d rather not (?:continue|talk about)"
    r"|i'?m sorry,?\s+but\s+i\s+(?:cant|can'?t)",
    re.IGNORECASE,
)

