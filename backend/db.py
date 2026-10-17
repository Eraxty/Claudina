import sqlite3

conn = sqlite3.connect("claudina.db", check_same_thread = False)

conn.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS relationship_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    trust REAL NOT NULL DEFAULT 0.5,
    affection REAL NOT NULL DEFAULT 0.5,
    annoyance REAL NOT NULL DEFAULT 0.0
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    importance REAL NOT NULL,
    created_at TEXT NOT NULL
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS show_progress (
    show TEXT PRIMARY KEY,
    episodes_watched INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL
)
""")
conn.execute("INSERT OR IGNORE INTO relationship_state (id) VALUES (1)")

for table in ("messages", "relationship_state", "memories"):
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN session TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass
