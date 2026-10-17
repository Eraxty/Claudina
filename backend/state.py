from db import conn


def get_state(session = ""):
    marker = conn.execute(
        "SELECT trust, affection, annoyance FROM relationship_state WHERE session = ?",
        (session,),
    ).fetchone()

    if marker is None:
        conn.execute(
            "INSERT INTO relationship_state (trust, affection, annoyance, session) VALUES (0.3, 0.3, 0.1, ?)",
            (session,),
        )
        conn.commit()

        return {"trust": 0.3, "affection": 0.3, "annoyance": 0.1}

    return {"trust": marker[0], "affection": marker[1], "annoyance": marker[2]}


def update_state(trust_delta = 0.0, affection_delta = 0.0, annoyance_delta = 0.0, session = ""):
    state = get_state(session)
    trust = min(1.0, max(0.0, state["trust"] + trust_delta))
    affection = min(1.0, max(0.0, state["affection"] + affection_delta))
    annoyance = min(1.0, max(0.0, state["annoyance"] + annoyance_delta))

    conn.execute(
        "UPDATE relationship_state SET trust = ?, affection = ?, annoyance = ? WHERE session = ?",
        (trust, affection, annoyance, session),
    )

    conn.commit()

    return {"trust": trust, "affection": affection, "annoyance": annoyance}
