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
