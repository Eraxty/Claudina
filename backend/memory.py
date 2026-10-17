import os

from db import conn


def save_memory(content):
    clean = content.strip().rstrip(",.!?")

    if not clean:
        return False

    dup = conn.execute(
        "SELECT 1 FROM memories WHERE LOWER(content) = LOWER(?) LIMIT 1",
        (clean,),
    ).fetchone()

    if dup:
        return False

    conn.execute(
        "INSERT INTO memories (content, importance, created_at) VALUES (?, 0.6, datetime('now'))",
        (clean,),
    )
    conn.commit()
    _dump_txt()

    return True


def top_memories(limit = 10):
    rows = conn.execute(
        "SELECT content FROM memories ORDER BY importance DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()

    return [row[0] for row in rows]


def _dump_txt():
    rows = conn.execute(
        "SELECT content, importance, created_at FROM memories ORDER BY id DESC"
    ).fetchall()

    with open(os.path.join(os.path.dirname(__file__), "memory.txt"), "w") as f:
        for content, importance, created in rows:
            f.write(f"{importance:.1f} | {created} | {content}\n")
