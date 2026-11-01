"""SQLite schema, connection helper and seed data."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS garment (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(id),
    name TEXT NOT NULL,
    photo TEXT,
    max_temp INTEGER NOT NULL,
    color TEXT NOT NULL,
    max_spin INTEGER NOT NULL,
    care TEXT NOT NULL,
    tumble_dry INTEGER NOT NULL DEFAULT 1,
    in_basket INTEGER NOT NULL DEFAULT 0,
    basket_since TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS program (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    temp INTEGER NOT NULL,
    care TEXT NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wash (
    id INTEGER PRIMARY KEY,
    program_id INTEGER REFERENCES program(id),
    name TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    temp INTEGER NOT NULL,
    spin INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wash_item (
    wash_id INTEGER NOT NULL REFERENCES wash(id),
    garment_id INTEGER NOT NULL REFERENCES garment(id),
    PRIMARY KEY (wash_id, garment_id)
);
CREATE TABLE IF NOT EXISTS setting (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SEED_PEOPLE = [
    ("Charlie", "#5b8def"),
    ("Kiki", "#e5689b"),
    ("Magnus", "#4fbf8b"),
]

SEED_PROGRAMS = [
    ("Bomull 40°", 180, 40, "normal"),
    ("Bomull 60°", 200, 60, "normal"),
    ("Syntet 40°", 120, 40, "synthetic"),
    ("Fintvätt 30°", 60, 30, "delicate"),
    ("Ull 30°", 45, 30, "wool"),
    ("Snabbtvätt 30°", 30, 30, "normal"),
]

DEFAULT_SETTINGS = {"split_hot": "1"}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM person").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO person (name, color, sort) VALUES (?, ?, ?)",
            [(n, c, i) for i, (n, c) in enumerate(SEED_PEOPLE)],
        )
        conn.executemany(
            "INSERT INTO program (name, duration_min, temp, care, sort) VALUES (?, ?, ?, ?, ?)",
            [(*p, i) for i, p in enumerate(SEED_PROGRAMS)],
        )
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO setting (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


@contextmanager
def open_db(request):
    """Yield a connection for one request; commit on success."""
    conn = connect(request.app.state.db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
