from app.kitchen.suggest import evaluate, sort_key

ITEMS = {
    1: {"id": 1, "name": "Pasta", "status": "in_stock", "staple": False},
    2: {"id": 2, "name": "Grädde", "status": "out", "staple": False},
    3: {"id": 3, "name": "Salt", "status": "out", "staple": True},
    4: {"id": 4, "name": "Ost", "status": "low", "staple": False},
}


def ing(i, name, item_id=None, optional=False, ignored=False):
    return {"id": i, "name": name, "item_id": item_id, "optional": optional, "ignored": ignored}


def test_evaluate_counts():
    ev = evaluate([
        ing(1, "pasta", 1), ing(2, "vispgrädde", 2), ing(3, "salt", 3), ing(4, "riven ost", 4),
        ing(5, "purjolök"), ing(6, "persilja", None, optional=True), ing(7, "vatten", None, ignored=True),
        ing(8, "gammal vara", 99),
    ], ITEMS)
    assert ev["total"] == 6
    assert ev["have"] == 3  # pasta, salt (staple), ost (low)
    assert ev["missing"] == [{"id": 2, "name": "vispgrädde", "item_id": 2}]
    assert ev["unknown"] == [{"id": 5, "name": "purjolök"}, {"id": 8, "name": "gammal vara"}]
    assert ev["low_used"] == 1


def test_sort_order():
    a = ({"title": "B", "last_cooked": None}, {"missing": [], "unknown": [], "low_used": 0})
    b = ({"title": "A", "last_cooked": None}, {"missing": [1], "unknown": [], "low_used": 0})
    c = ({"title": "C", "last_cooked": None}, {"missing": [], "unknown": [], "low_used": 2})
    d = ({"title": "D", "last_cooked": "2026-10-01"}, {"missing": [], "unknown": [], "low_used": 0})
    e = ({"title": "E", "last_cooked": "2026-09-01"}, {"missing": [], "unknown": [], "low_used": 0})
    ordered = sorted([a, b, c, d, e], key=lambda x: sort_key(*x))
    assert [r["title"] for r, _ in ordered] == ["C", "B", "E", "D", "A"]
