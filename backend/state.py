import sqlite3

from db import conn

conn.execute("""
CREATE TABLE IF NOT EXISTS user_state (
    session TEXT PRIMARY KEY,
    trust REAL NOT NULL DEFAULT 0.3,
    affection REAL NOT NULL DEFAULT 0.3,
    annoyance REAL NOT NULL DEFAULT 0.1
)
""")

if not conn.execute("SELECT 1 FROM user_state WHERE session = ''").fetchone():
    old = conn.execute("SELECT trust, affection, annoyance FROM relationship_state WHERE id = 1").fetchone()

    if old:
        conn.execute(
            "INSERT INTO user_state (session, trust, affection, annoyance) VALUES ('', ?, ?, ?)",
            (old[0], old[1], old[2]),
        )
    else:
        conn.execute("INSERT INTO user_state (session) VALUES ('')")

    conn.commit()


try:
    conn.execute("ALTER TABLE user_state ADD COLUMN minor INTEGER NOT NULL DEFAULT 0")
    conn.commit()
except sqlite3.OperationalError:
    pass

try:
    conn.execute("ALTER TABLE user_state ADD COLUMN away_until TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass


def get_state(session = ""):
    row = conn.execute(
        "SELECT trust, affection, annoyance FROM user_state WHERE session = ?",
        (session,),
    ).fetchone()

    if row is None:
        conn.execute("INSERT INTO user_state (session) VALUES (?)", (session,))
        conn.commit()
        row = (0.3, 0.3, 0.1)

    return {"trust": row[0], "affection": row[1], "annoyance": row[2]}


def update_state(trust_delta = 0.0, affection_delta = 0.0, annoyance_delta = 0.0, session = ""):
    state = get_state(session)
    trust = min(1.0, max(0.0, state["trust"] + trust_delta))
    affection = min(1.0, max(0.0, state["affection"] + affection_delta))
    annoyance = min(1.0, max(0.0, state["annoyance"] + annoyance_delta))

    conn.execute(
        "UPDATE user_state SET trust = ?, affection = ?, annoyance = ? WHERE session = ?",
        (trust, affection, annoyance, session),
    )

    conn.commit()

    return {"trust": trust, "affection": affection, "annoyance": annoyance}


def is_minor(session = ""):
    row = conn.execute("SELECT minor FROM user_state WHERE session = ?", (session,)).fetchone()

    return bool(row and row[0])


def mark_minor(session = ""):
    get_state(session)
    conn.execute("UPDATE user_state SET minor = 1 WHERE session = ?", (session,))
    conn.commit()


def go_away(session, minutes):
    get_state(session)
    conn.execute(
        "UPDATE user_state SET away_until = datetime('now', ?) WHERE session = ?",
        (f"+{minutes} minutes", session),
    )
    conn.commit()


def is_away(session):
    row = conn.execute(
        "SELECT away_until > datetime('now') FROM user_state WHERE session = ?",
        (session,),
    ).fetchone()

    return bool(row and row[0])


conn.execute("""
CREATE TABLE IF NOT EXISTS routines (
    session TEXT NOT NULL,
    kind TEXT NOT NULL,
    day TEXT NOT NULL,
    PRIMARY KEY (session, kind, day))""")

conn.commit()


def did_routine(session, kind, day):
    row = conn.execute("SELECT 1 FROM routines WHERE session = ? AND kind = ? AND day = ?", (session, kind, day)).fetchone()

    return row is not None


def mark_routine(session, kind, day):
    conn.execute("INSERT OR IGNORE INTO routines (session, kind, day) VALUES (?, ?, ?)", (session, kind, day))
    conn.commit()


def come_back(session):
    conn.execute("UPDATE user_state SET away_until = NULL WHERE session = ?", (session,))
    conn.commit()
