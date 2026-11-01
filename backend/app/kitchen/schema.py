"""Kitchen tables, fixed vocabularies and first-run seed data (spec §4)."""

import sqlite3

from app.kitchen.seed import SEED_IGNORE, SEED_ITEMS

CATEGORIES = ["Kyl", "Frys", "Skafferi", "Frukt & grönt", "Bröd", "Kryddor", "Dryck", "Hushåll"]
STATUSES = ("in_stock", "low", "out")

KITCHEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS item (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'out',
    count INTEGER,
    staple INTEGER NOT NULL DEFAULT 0,
    counted INTEGER NOT NULL DEFAULT 0,
    match_words TEXT NOT NULL DEFAULT '',
    buy_count INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS item_name_live ON item(name COLLATE NOCASE) WHERE archived=0;
CREATE TABLE IF NOT EXISTS barcode (
    code TEXT PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES item(id),
    product_name TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shopping_entry (
    id INTEGER PRIMARY KEY,
    item_id INTEGER REFERENCES item(id),
    text TEXT NOT NULL,
    note TEXT,
    added_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS shopping_item_once ON shopping_entry(item_id) WHERE item_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS recipe (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    servings INTEGER,
    minutes INTEGER,
    source TEXT NOT NULL DEFAULT 'own',
    source_url TEXT,
    photo TEXT,
    instructions TEXT NOT NULL DEFAULT '',
    cooked_count INTEGER NOT NULL DEFAULT 0,
    last_cooked TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS recipe_url_once ON recipe(source_url) WHERE source_url IS NOT NULL AND archived=0;
CREATE TABLE IF NOT EXISTS recipe_ingredient (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id),
    sort INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    name TEXT NOT NULL,
    item_id INTEGER REFERENCES item(id),
    optional INTEGER NOT NULL DEFAULT 0,
    ignored INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ingredient_map (
    name TEXT PRIMARY KEY,
    item_id INTEGER REFERENCES item(id)
);
CREATE TABLE IF NOT EXISTS item_image (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES item(id),
    file TEXT NOT NULL,
    model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS item_image_item ON item_image(item_id);
"""


def init_kitchen(conn: sqlite3.Connection, now: str) -> None:
    conn.executescript(KITCHEN_SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO item (name, category, staple, counted, match_words, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'out', ?, ?)",
            [(n, c, int(s), int(k), ",".join(w), now, now) for n, c, s, k, w in SEED_ITEMS],
        )
        conn.executemany("INSERT OR IGNORE INTO ingredient_map (name, item_id) VALUES (?, NULL)", [(n,) for n in SEED_IGNORE])
    conn.execute("INSERT OR IGNORE INTO setting (key, value) VALUES ('auto_list', '1')")
