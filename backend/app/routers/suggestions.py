from dataclasses import asdict

from starlette.routing import Route

from app.db import open_db
from app.grouping import Item, Prog, check_selection, group_items
from app.models import CheckIn
from app.routers.garments import SELECT
from app.routers.settings import read_settings
from app.web import ok, parse


def _basket(conn) -> list:
    sql = f"SELECT * FROM ({SELECT}) WHERE archived=0 AND in_basket=1 AND in_wash=0 ORDER BY id"
    return list(conn.execute(sql))


def _items(rows) -> list[Item]:
    return [
        Item(r["id"], r["person_id"], r["max_temp"], r["color"], r["max_spin"], r["care"], bool(r["tumble_dry"]))
        for r in rows
    ]


def _programs(conn) -> list[Prog]:
    rows = conn.execute("SELECT * FROM program WHERE archived=0 ORDER BY sort, id")
    return [Prog(r["id"], r["name"], r["temp"], r["care"]) for r in rows]


def _group_json(group, person_of: dict) -> dict:
    d = asdict(group)
    d["person_ids"] = sorted({person_of[i] for i in group.item_ids})
    return d


async def suggestions(request):
    with open_db(request) as conn:
        rows = _basket(conn)
        split = read_settings(conn)["split_hot"]
        groups = group_items(_items(rows), _programs(conn), split_hot=split)
    person_of = {r["id"]: r["person_id"] for r in rows}
    return ok([_group_json(g, person_of) for g in groups])


async def check(request):
    body = await parse(request, CheckIn)
    with open_db(request) as conn:
        rows = _basket(conn)
        split = read_settings(conn)["split_hot"]
        progs = _programs(conn)
    basket = _items(rows)
    wanted = set(body.garment_ids)
    selected = [i for i in basket if i.id in wanted]
    sel = check_selection(selected, basket, progs, split_hot=split)
    person_of = {r["id"]: r["person_id"] for r in rows}
    return ok({
        "group": _group_json(sel.group, person_of) if sel.group else None,
        "compatible_ids": sel.compatible_ids,
        "conflicts": sel.conflicts,
    })


routes = [
    Route("/api/suggestions", suggestions, methods=["GET"]),
    Route("/api/suggestions/check", check, methods=["POST"]),
]
