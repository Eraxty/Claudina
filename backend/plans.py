from datetime import datetime, timedelta

from available import current_time
from db import conn

conn.execute("""
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    about TEXT NOT NULL,
    due TEXT NOT NULL,
    asked INTEGER NOT NULL DEFAULT 0
)
""")
conn.commit()


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def days_until(when):
    when = str(when or "").lower()
    today = current_time().weekday()

    if "tomorrow" in when:
        return 1

    for number, name in enumerate(WEEKDAYS):
        if name in when or name[:3] == when[:3]:
            days = (number - today) % 7

            if days == 0 and "next" in when:
                days = 7

            return days

    return 0


def save_plan(about, when, session = ""):
    about = str(about).strip().rstrip(",.!?")

    if not about:
        return

    days = days_until(when)

    dup = conn.execute(
        "SELECT 1 FROM plans WHERE session = ? AND asked = 0 AND LOWER(about) = LOWER(?)",
        (session, about),
    ).fetchone()

    if dup:
        return

    now = current_time()
    day = now.date() + timedelta(days = days)
    due = datetime(day.year, day.month, day.day, 19)

    if due < now:
        due = now + timedelta(hours = 3)

    conn.execute(
        "INSERT INTO plans (session, about, due) VALUES (?, ?, ?)",
        (session, about, due.isoformat()),
    )
    conn.commit()


def due_plan(session = ""):
    now = current_time()
    too_old = now - timedelta(days = 4)

    conn.execute(
        "UPDATE plans SET asked = 1 WHERE session = ? AND asked = 0 AND due < ?",
        (session, too_old.isoformat()),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id, about, due FROM plans WHERE session = ? AND asked = 0 AND due <= ? ORDER BY due LIMIT 1",
        (session, now.isoformat()),
    ).fetchone()

    if row is None:
        return None

    day = datetime.fromisoformat(row[2]).date()

    if day == now.date():
        when = "earlier today"
    elif day == now.date() - timedelta(days = 1):
        when = "yesterday"
    else:
        when = "on " + WEEKDAYS[day.weekday()]

    return {"id": row[0], "about": row[1], "when": when}


def mark_asked(plan_id):
    conn.execute("UPDATE plans SET asked = 1 WHERE id = ?", (plan_id,))
    conn.commit()
