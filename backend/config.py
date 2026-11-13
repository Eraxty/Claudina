import base64
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


def hidden(text):
    return base64.b64decode(text).decode()


UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)

OFF_LIMITS = re.compile(hidden("XGIoPzpzZXh8c2V4dCg/OmluZ3xpbik/fGhvcm55fG51ZGVzP3xuYWtlZHxob29rXHMqdXB8c2xlZXBccyt3aXRoXHMreW91fGJvb2JzP3xicmVhc3RzP3x0aXRzP3x0aXR0aWVzfG5pcHBsZXM/fHB1c3N5fGRpY2t8Y29ja3xwZW5pc3x2YWdpbmF8Z2VuaXRhbHN8Y2xpdHxicmF8Ymxvd2pvYnxoYW5kam9ifGZpbmdlcmluZ3xmKD86dWNrfGspKD86aW5nKT98Y3VtKD86bWluZyk/fG9yZ2FzbXxzcXVpcnR8c3dhbGxvd3x0dXJuXHMrbWVccytvbnxjb21lXHMrb3ZlcnxoYXJkZXJ8d2V0fG1vYW4oPzppbmcpPylcYnxcYig/OnRvdWNofGZlZWx8Z3JhYnxzcXVlZXplfGxpY2spXHcqXHMrKD86eW91cnx1cnx1fGhlcnx0aGVpcik/XHMqKD86Y2hlc3R8YXNzfGJ1dHQpXGJ8XGIoPzplYXR8dGFzdGV8cmlkZSlccysoPzppdHxtZXx1fHlvdSlcYnxcYmRlZXBccyp0aHJvYXQoPzppbmcpP1xifFxiKD86d2FudHxuZWVkKVxzKyg/OnV8eW91KVxzKyg/OnNvXHMrYmFkfGJhZHxybnxyaWdodFxzK25vdylcYg=="), re.IGNORECASE)

OFF_LIMITS_REPLY = re.compile(hidden("XGIoPzpzZXh8c2V4eXxzZXh0KD86aW5nKT98aG9ybnl8bnVkZXM/fG5ha2VkfHBvcm5cdyp8Ym9vYnM/fHRpdHM/fHRpdHRpZXN8bmlwcGxlcz98cHVzc3l8ZGlja3xjb2NrfHBlbmlzfHZhZ2luYXxibG93am9ifGhhbmRqb2J8Y3VtKD86bWluZyk/fG9yZ2FzbSlcYg=="), re.IGNORECASE)

REFUSAL = re.compile(
    r"(?:cant|can'?t|cannot|can not|won'?t|will not)\s+(?:continue|fulfill|help with)"
    r"|i'?m sorry,?\s+but\s+i\s+(?:cant|can'?t|cannot)"
    r"|\bas an ai\b|i am an artificial intelligence",
    re.IGNORECASE,
)
