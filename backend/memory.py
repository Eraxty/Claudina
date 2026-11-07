
from db import conn


def save_memory(content, session = ""):
    clean = content.strip().rstrip(",.!?")

    if not clean:
        return False

    dup = conn.execute(
        "SELECT 1 FROM memories WHERE session = ? AND LOWER(content) = LOWER(?) LIMIT 1",
        (session, clean),
    ).fetchone()

    if dup:
        return False

    conn.execute(
        "INSERT INTO memories (content, importance, created_at, session) VALUES (?, 0.6, datetime('now'), ?)",
        (clean, session),
    )
    conn.commit()
    _dump_txt()

    return True


def top_memories(limit = 10, session = ""):
    rows = conn.execute(
        "SELECT content FROM memories WHERE session = ? ORDER BY importance DESC, id DESC LIMIT ?",
        (session, limit),
    ).fetchall()

    memories = []

    for row in rows:
        memories.append(row[0])

    return memories


def _dump_txt():
    rows = conn.execute(
        "SELECT content, importance, created_at, session FROM memories ORDER BY id DESC"
    ).fetchall()

    with open("memory.txt", "w") as f:
        for content, importance, created, session in rows:
            f.write(f"{importance:.1f} | {created} | [{session or 'owner'}] {content}\n")
