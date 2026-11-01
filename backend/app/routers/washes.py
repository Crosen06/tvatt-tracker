from datetime import timedelta

from starlette.exceptions import HTTPException
from starlette.routing import Route

from app import clock
from app.db import open_db
from app.models import WashIn
from app.routers.garments import SELECT, garment_json
from app.web import ok, parse, path_id, publish

MSG_RUNNING = "En tvätt är redan igång."


def _wash_json(conn, w, now) -> dict:
    items = conn.execute(
        f"SELECT * FROM ({SELECT}) g JOIN wash_item wi ON wi.garment_id = g.id WHERE wi.wash_id=? ORDER BY g.id",
        (w["id"],),
    )
    return {
        "id": w["id"],
        "program_id": w["program_id"],
        "name": w["name"],
        "duration_min": w["duration_min"],
        "temp": w["temp"],
        "spin": w["spin"],
        "started_at": w["started_at"],
        "ends_at": w["ends_at"],
        "status": w["status"],
        "is_done": now >= clock.from_iso(w["ends_at"]),
        "items": [garment_json(r) for r in items],
    }


def _running(conn):
    return conn.execute("SELECT * FROM wash WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()


async def current(request):
    now = clock.utcnow()
    with open_db(request) as conn:
        w = _running(conn)
        wash = _wash_json(conn, w, now) if w else None
    return ok({"wash": wash, "server_now": clock.to_iso(now)})


async def start_wash(request):
    body = await parse(request, WashIn)
    now = clock.utcnow()
    with open_db(request) as conn:
        if _running(conn):
            raise HTTPException(409, MSG_RUNNING)
        prog = conn.execute("SELECT * FROM program WHERE id=? AND archived=0", (body.program_id,)).fetchone()
        if not prog:
            raise HTTPException(400, "Välj ett tvättprogram.")
        ids = sorted(set(body.garment_ids))
        marks = ",".join("?" * len(ids))
        found = conn.execute(
            f"SELECT COUNT(*) FROM garment WHERE id IN ({marks}) AND archived=0 AND in_basket=1", ids
        ).fetchone()[0]
        if found != len(ids):
            raise HTTPException(400, "Några plagg ligger inte i tvättkorgen längre.")
        ends = now + timedelta(minutes=prog["duration_min"])
        cur = conn.execute(
            "INSERT INTO wash (program_id, name, duration_min, temp, spin, started_at, ends_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'running')",
            (prog["id"], prog["name"], prog["duration_min"], body.temp, body.spin, clock.to_iso(now), clock.to_iso(ends)),
        )
        conn.executemany("INSERT INTO wash_item (wash_id, garment_id) VALUES (?, ?)", [(cur.lastrowid, g) for g in ids])
        w = conn.execute("SELECT * FROM wash WHERE id=?", (cur.lastrowid,)).fetchone()
        result = _wash_json(conn, w, now)
    publish(request, "wash", "garments")
    return ok(result, 201)


def _end(request, status: str):
    wid = path_id(request)
    with open_db(request) as conn:
        w = conn.execute("SELECT * FROM wash WHERE id=? AND status='running'", (wid,)).fetchone()
        if not w:
            raise HTTPException(404, "Tvätten finns inte eller är redan avslutad.")
        conn.execute("UPDATE wash SET status=? WHERE id=?", (status, wid))
        if status == "done":
            conn.execute(
                "UPDATE garment SET in_basket=0, basket_since=NULL "
                "WHERE id IN (SELECT garment_id FROM wash_item WHERE wash_id=?)",
                (wid,),
            )
    publish(request, "wash", "garments")
    return ok({"id": wid, "status": status})


async def finish(request):
    return _end(request, "done")


async def cancel(request):
    return _end(request, "cancelled")


routes = [
    Route("/api/washes/current", current, methods=["GET"]),
    Route("/api/washes", start_wash, methods=["POST"]),
    Route("/api/washes/{id:int}/finish", finish, methods=["POST"]),
    Route("/api/washes/{id:int}/cancel", cancel, methods=["POST"]),
]
