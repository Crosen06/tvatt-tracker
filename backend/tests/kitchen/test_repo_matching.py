from app.kitchen import repo


def add_recipe(conn, lines):
    cur = conn.execute("INSERT INTO recipe (title, created_at) VALUES ('R', '2026-01-01T00:00:00+00:00')")
    rid = cur.lastrowid
    for i, (text, name) in enumerate(lines):
        conn.execute(
            "INSERT INTO recipe_ingredient (recipe_id, sort, text, name) VALUES (?, ?, ?, ?)", (rid, i, text, name)
        )
    return rid


def test_link_and_rematch(conn):
    rid = add_recipe(conn, [("2 dl vispgrädde", "vispgrädde"), ("1 dl vatten", "vatten"), ("1 st halloumi", "halloumi")])
    repo.link_ingredients(conn, rid)
    rows = conn.execute("SELECT name, item_id, ignored FROM recipe_ingredient ORDER BY sort").fetchall()
    gradde = conn.execute("SELECT id FROM item WHERE name='Grädde'").fetchone()[0]
    assert [(r["name"], r["item_id"], r["ignored"]) for r in rows] == [
        ("vispgrädde", gradde, 0), ("vatten", None, 1), ("halloumi", None, 0),
    ]
    hid = repo.create_item(conn, name="Halloumi", category="Kyl")
    assert conn.execute("SELECT item_id FROM recipe_ingredient WHERE name='halloumi'").fetchone()[0] == hid
