"""Database helpers for the kitchen. Takes a sqlite3 connection; no web imports."""

import sqlite3

from app import clock

FREQUENT_MAX = 24


class NotFound(Exception):
    pass


def _now() -> str:
    return clock.to_iso(clock.utcnow())


def item_json(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "status": r["status"],
        "count": r["count"],
        "staple": bool(r["staple"]),
        "counted": bool(r["counted"]),
        "match_words": [w for w in r["match_words"].split(",") if w],
        "buy_count": r["buy_count"],
        "on_list": bool(r["on_list"]),
    }


ITEM_SELECT = """
SELECT i.*, EXISTS(SELECT 1 FROM shopping_entry s WHERE s.item_id = i.id) AS on_list
FROM item i
"""


def list_items(conn) -> list[dict]:
    rows = conn.execute(ITEM_SELECT + " WHERE i.archived=0 ORDER BY i.name COLLATE NOCASE")
    return [item_json(r) for r in rows]


def fetch_item(conn, item_id: int):
    row = conn.execute(ITEM_SELECT + " WHERE i.id=? AND i.archived=0", (item_id,)).fetchone()
    if not row:
        raise NotFound("Varan finns inte.")
    return row


def name_taken(conn, name: str, except_id: int | None = None) -> bool:
    row = conn.execute(
        "SELECT id FROM item WHERE name=? COLLATE NOCASE AND archived=0 AND id IS NOT ?", (name, except_id)
    ).fetchone()
    return row is not None


def create_item(conn, *, name, category, staple=False, counted=False, match_words=(), status="out", count=None) -> int:
    if counted and count is not None:
        status = "out" if count == 0 else ("in_stock" if status == "out" else status)
    now = _now()
    cur = conn.execute(
        "INSERT INTO item (name, category, staple, counted, match_words, status, count, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, category, int(staple), int(counted), ",".join(match_words), status, count, now, now),
    )
    rematch_unknown(conn)
    return cur.lastrowid


def update_item(conn, item_id: int, changes: dict) -> None:
    for field in ("name", "category", "staple", "counted", "match_words"):
        if field in changes:
            value = changes[field]
            if field in ("staple", "counted"):
                value = int(value)
            if field == "match_words":
                value = ",".join(value)
            conn.execute(f"UPDATE item SET {field}=?, updated_at=? WHERE id=?", (value, _now(), item_id))
    if "name" in changes or "match_words" in changes:
        rematch_unknown(conn)


def set_status(conn, item_id: int, status: str | None = None, count: int | None = None) -> int | None:
    """Change status and/or count. Returns the id of a list entry created because the item ran out."""
    row = fetch_item(conn, item_id)
    old = row["status"]
    new_status = status or old
    new_count = row["count"]
    if count is not None:
        new_count = count
        if status is None:
            if count == 0:
                new_status = "out"
            elif old == "out":
                new_status = "in_stock"
    elif row["counted"]:
        if status == "out":
            new_count = 0
        elif not new_count:
            new_count = 1
    conn.execute(
        "UPDATE item SET status=?, count=?, updated_at=? WHERE id=?", (new_status, new_count, _now(), item_id)
    )
    if new_status == "out" and old != "out" and auto_list_on(conn):
        return add_to_list(conn, item_id=item_id)
    return None


def auto_list_on(conn) -> bool:
    row = conn.execute("SELECT value FROM setting WHERE key='auto_list'").fetchone()
    return row is None or row["value"] == "1"


def add_to_list(conn, *, item_id: int | None = None, text: str | None = None, note: str | None = None) -> int | None:
    if item_id is not None:
        row = fetch_item(conn, item_id)
        if row["on_list"]:
            return None
        text = row["name"]
        conn.execute("UPDATE item SET buy_count = buy_count + 1 WHERE id=?", (item_id,))
    cur = conn.execute(
        "INSERT INTO shopping_entry (item_id, text, note, added_at) VALUES (?, ?, ?, ?)",
        (item_id, text, note, _now()),
    )
    return cur.lastrowid


def list_entries(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT s.*, i.category FROM shopping_entry s LEFT JOIN item i ON i.id = s.item_id ORDER BY s.id"
    )
    return [
        {"id": r["id"], "item_id": r["item_id"], "text": r["text"], "note": r["note"],
         "added_at": r["added_at"], "category": r["category"]}
        for r in rows
    ]


def frequent(conn) -> list[dict]:
    rows = conn.execute(
        ITEM_SELECT + " WHERE i.archived=0 AND i.buy_count > 0 ORDER BY i.buy_count DESC, i.name COLLATE NOCASE LIMIT ?",
        (FREQUENT_MAX,),
    )
    return [item_json(r) for r in rows]


def delete_entry(conn, entry_id: int) -> None:
    if conn.execute("DELETE FROM shopping_entry WHERE id=?", (entry_id,)).rowcount == 0:
        raise NotFound("Raden finns inte på listan.")


def unpack(conn, entry_ids: list[int]) -> None:
    for eid in dict.fromkeys(entry_ids):
        row = conn.execute("SELECT * FROM shopping_entry WHERE id=?", (eid,)).fetchone()
        if not row:
            continue
        if row["item_id"] is not None:
            item = conn.execute("SELECT * FROM item WHERE id=?", (row["item_id"],)).fetchone()
            count = item["count"]
            if item["counted"]:
                count = (count or 0) + 1
            conn.execute(
                "UPDATE item SET status='in_stock', count=?, updated_at=? WHERE id=?", (count, _now(), item["id"])
            )
        conn.execute("DELETE FROM shopping_entry WHERE id=?", (eid,))


def archive_item(conn, item_id: int) -> None:
    fetch_item(conn, item_id)
    conn.execute("DELETE FROM shopping_entry WHERE item_id=?", (item_id,))
    conn.execute("UPDATE recipe_ingredient SET item_id=NULL WHERE item_id=?", (item_id,))
    conn.execute("DELETE FROM ingredient_map WHERE item_id=?", (item_id,))
    conn.execute("UPDATE item SET archived=1, updated_at=? WHERE id=?", (_now(), item_id))
    rematch_unknown(conn)


def rematch_unknown(conn: sqlite3.Connection) -> None:
    """Re-link recipe lines without an item. Replaced by real matching in the recipes step."""
