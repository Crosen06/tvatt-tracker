from app.db import connect, init_db
from app.kitchen.schema import CATEGORIES, STATUSES


def test_seed_items_once(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_db(conn)
    first = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM item").fetchone()[0] == first
    assert first >= 55
    assert {r[0] for r in conn.execute("SELECT DISTINCT status FROM item")} == {"out"}


def test_seed_categories_valid(conn):
    cats = {r[0] for r in conn.execute("SELECT DISTINCT category FROM item")}
    assert cats <= set(CATEGORIES)
    assert CATEGORIES == ["Kyl", "Frys", "Skafferi", "Frukt & grönt", "Bröd", "Kryddor", "Dryck", "Hushåll"]
    assert STATUSES == ("in_stock", "low", "out")


def test_staples_seeded(conn):
    rows = {r["name"]: r for r in conn.execute("SELECT * FROM item WHERE staple=1")}
    assert {"Salt", "Svartpeppar", "Matolja", "Olivolja", "Vetemjöl", "Strösocker"} <= set(rows)
    assert "peppar" in rows["Svartpeppar"]["match_words"].split(",")


def test_ignore_map_seeded(conn):
    rows = dict(conn.execute("SELECT name, item_id FROM ingredient_map").fetchall())
    for n in ["vatten", "kallt vatten", "ljummet vatten", "kokande vatten"]:
        assert n in rows and rows[n] is None
