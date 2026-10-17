from db import conn


def get_state():
    row = conn.execute("SELECT trust, affection, annoyance FROM relationship_state WHERE id = 1").fetchone()
    
    return {"trust": row[0], "affection": row[1], "annoyance": row[2]}


def update_state(trust_delta = 0.0, affection_delta = 0.0, annoyance_delta = 0.0):
    state = get_state()
    trust = min(1.0, max(0.0, state["trust"] + trust_delta))
    affection = min(1.0, max(0.0, state["affection"] + affection_delta))
    annoyance = min(1.0, max(0.0, state["annoyance"] + annoyance_delta))

    conn.execute(
        "UPDATE relationship_state SET trust = ?, affection = ?, annoyance = ? WHERE id = 1",
        (trust, affection, annoyance),
    )
    
    conn.commit()
    
    return {"trust": trust, "affection": affection, "annoyance": annoyance}
