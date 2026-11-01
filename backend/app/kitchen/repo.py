"""Database helpers for the kitchen. Takes a sqlite3 connection; no web imports."""

import sqlite3

from app import clock
from app.kitchen.ingredients import ItemRef, match

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


def item_refs(conn) -> list[ItemRef]:
    rows = conn.execute("SELECT id, name, match_words FROM item WHERE archived=0 ORDER BY id")
    return [ItemRef(r["id"], r["name"], [w for w in r["match_words"].split(",") if w]) for r in rows]


def ingredient_mapping(conn) -> dict[str, int | None]:
    return {r["name"]: r["item_id"] for r in conn.execute("SELECT name, item_id FROM ingredient_map")}


def _link_rows(conn, rows) -> None:
    refs, mapping = item_refs(conn), ingredient_mapping(conn)
    for r in rows:
        iid, ignored = match(r["name"], refs, mapping)
        conn.execute(
            "UPDATE recipe_ingredient SET item_id=?, ignored=? WHERE id=?", (iid, int(ignored), r["id"])
        )


def link_ingredients(conn, recipe_id: int) -> None:
    """(Re)match every line of one recipe."""
    _link_rows(conn, conn.execute("SELECT id, name FROM recipe_ingredient WHERE recipe_id=?", (recipe_id,)).fetchall())


def rematch_unknown(conn: sqlite3.Connection) -> None:
    """Try again for lines that have no item yet and that nobody chose to ignore."""
    rows = conn.execute(
        "SELECT ri.id, ri.name FROM recipe_ingredient ri JOIN recipe r ON r.id = ri.recipe_id "
        "WHERE ri.item_id IS NULL AND ri.ignored = 0 AND r.archived = 0"
    ).fetchall()
    if rows:
        _link_rows(conn, rows)


# ---------- recipes ----------

def _steps(text: str) -> list[str]:
    return [" ".join(s.split()) for s in (text or "").splitlines() if s.strip()]


def set_ingredients(conn, recipe_id: int, lines: list[str]) -> None:
    from app.kitchen.ingredients import parse_line

    conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id=?", (recipe_id,))
    sort = 0
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        conn.execute(
            "INSERT INTO recipe_ingredient (recipe_id, sort, text, name, optional, ignored) VALUES (?, ?, ?, ?, ?, ?)",
            (recipe_id, sort, p.text, p.name, int(p.optional), int(not p.name)),
        )
        sort += 1
    rows = conn.execute(
        "SELECT id, name FROM recipe_ingredient WHERE recipe_id=? AND name != ''", (recipe_id,)
    ).fetchall()
    _link_rows(conn, rows)


def create_recipe(conn, *, title, servings=None, minutes=None, ingredients=(), steps=(), source="own",
                  source_url=None, photo=None) -> int:
    cur = conn.execute(
        "INSERT INTO recipe (title, servings, minutes, source, source_url, photo, instructions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, servings, minutes, source, source_url, photo, "\n".join(steps), _now()),
    )
    set_ingredients(conn, cur.lastrowid, list(ingredients))
    return cur.lastrowid


def fetch_recipe(conn, recipe_id: int):
    row = conn.execute("SELECT * FROM recipe WHERE id=? AND archived=0", (recipe_id,)).fetchone()
    if not row:
        raise NotFound("Receptet finns inte.")
    return row


def recipe_by_url(conn, url: str):
    return conn.execute("SELECT id FROM recipe WHERE source_url=? AND archived=0", (url,)).fetchone()


def items_by_id(conn) -> dict[int, dict]:
    rows = conn.execute("SELECT id, name, status, staple FROM item WHERE archived=0")
    return {r["id"]: {"id": r["id"], "name": r["name"], "status": r["status"], "staple": bool(r["staple"])} for r in rows}


def ingredient_rows(conn, recipe_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM recipe_ingredient WHERE recipe_id=? ORDER BY sort, id", (recipe_id,))
    return [
        {"id": r["id"], "text": r["text"], "name": r["name"], "item_id": r["item_id"],
         "optional": bool(r["optional"]), "ignored": bool(r["ignored"])}
        for r in rows
    ]


def recipe_json(r, ev: dict) -> dict:
    photo = r["photo"]
    return {
        "id": r["id"], "title": r["title"], "servings": r["servings"], "minutes": r["minutes"],
        "source": r["source"], "source_url": r["source_url"],
        "photo_url": f"/photos/{photo}" if photo else None,
        "thumb_url": f"/photos/thumb/{photo}" if photo else None,
        "cooked_count": r["cooked_count"], "last_cooked": r["last_cooked"], "eval": ev,
    }


def list_recipes(conn) -> list[dict]:
    from app.kitchen.suggest import evaluate, sort_key

    items = items_by_id(conn)
    out = []
    for r in conn.execute("SELECT * FROM recipe WHERE archived=0"):
        ev = evaluate(ingredient_rows(conn, r["id"]), items)
        out.append((sort_key(dict(r), ev), recipe_json(r, ev)))
    return [x for _, x in sorted(out, key=lambda t: t[0])]


def recipe_detail(conn, recipe_id: int) -> dict:
    from app.kitchen.suggest import evaluate, line_state

    r = fetch_recipe(conn, recipe_id)
    items = items_by_id(conn)
    ings = ingredient_rows(conn, recipe_id)
    out = recipe_json(r, evaluate(ings, items))
    out["ingredients"] = [
        {**i, "state": line_state(i, items), "item_name": items[i["item_id"]]["name"] if i["item_id"] in items else None}
        for i in ings
    ]
    out["steps"] = _steps(r["instructions"])
    return out


def link_ingredient(conn, recipe_id: int, ing_id: int, *, item_id=None, ignored=None) -> None:
    row = conn.execute(
        "SELECT * FROM recipe_ingredient WHERE id=? AND recipe_id=?", (ing_id, recipe_id)
    ).fetchone()
    if not row:
        raise NotFound("Ingrediensen finns inte.")
    name = row["name"]
    if item_id is not None:
        fetch_item(conn, item_id)
        conn.execute("UPDATE recipe_ingredient SET item_id=?, ignored=0 WHERE id=?", (item_id, ing_id))
        if name:
            conn.execute("INSERT OR REPLACE INTO ingredient_map (name, item_id) VALUES (?, ?)", (name, item_id))
            # Other recipes' lines with the same name follow the user's choice.
            conn.execute(
                "UPDATE recipe_ingredient SET item_id=?, ignored=0 WHERE name=? AND (item_id IS NULL OR item_id != ?)",
                (item_id, name, item_id),
            )
    elif ignored:
        conn.execute("UPDATE recipe_ingredient SET item_id=NULL, ignored=1 WHERE id=?", (ing_id,))
        if name:
            conn.execute("INSERT OR REPLACE INTO ingredient_map (name, item_id) VALUES (?, NULL)", (name,))
    else:
        conn.execute("UPDATE recipe_ingredient SET ignored=0 WHERE id=?", (ing_id,))
        if name:
            conn.execute("DELETE FROM ingredient_map WHERE name=?", (name,))
            conn.execute("UPDATE recipe_ingredient SET ignored=0 WHERE name=? AND item_id IS NULL", (name,))
    rematch_unknown(conn)


def missing_to_list(conn, recipe_id: int) -> int:
    from app.kitchen.suggest import evaluate

    r = fetch_recipe(conn, recipe_id)
    ev = evaluate(ingredient_rows(conn, recipe_id), items_by_id(conn))
    note = f"till {r['title']}"[:60]
    added = 0
    for m in ev["missing"]:
        if add_to_list(conn, item_id=m["item_id"], note=note) is not None:
            added += 1
    texts = {e["text"].lower() for e in list_entries(conn)}
    for u in ev["unknown"]:
        text = u["name"][:1].upper() + u["name"][1:60]
        if text.lower() not in texts:
            add_to_list(conn, text=text, note=note)
            texts.add(text.lower())
            added += 1
    return added


def mark_cooked(conn, recipe_id: int, updates: list[tuple[int, str]]) -> None:
    fetch_recipe(conn, recipe_id)
    for item_id, status in updates:
        set_status(conn, item_id, status)
    conn.execute(
        "UPDATE recipe SET cooked_count = cooked_count + 1, last_cooked=? WHERE id=?", (_now(), recipe_id)
    )
