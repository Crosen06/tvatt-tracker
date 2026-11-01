from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.db import open_db
from app.models import ProgramIn, ProgramPatch
from app.web import no_content, ok, parse, path_id, publish

FIELDS = ("id", "name", "duration_min", "temp", "care", "sort")


def _row(r):
    return {k: r[k] for k in FIELDS}


def _get(conn, pid):
    row = conn.execute("SELECT * FROM program WHERE id=? AND archived=0", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Programmet finns inte.")
    return row


async def list_programs(request):
    with open_db(request) as conn:
        rows = conn.execute("SELECT * FROM program WHERE archived=0 ORDER BY sort, id")
        return ok([_row(r) for r in rows])


async def create_program(request):
    body = await parse(request, ProgramIn)
    with open_db(request) as conn:
        sort = conn.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM program").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO program (name, duration_min, temp, care, sort) VALUES (?, ?, ?, ?, ?)",
            (body.name.strip(), body.duration_min, body.temp, body.care, sort),
        )
        row = _get(conn, cur.lastrowid)
    publish(request, "programs")
    return ok(_row(row), 201)


async def patch_program(request):
    pid = path_id(request)
    body = await parse(request, ProgramPatch)
    with open_db(request) as conn:
        _get(conn, pid)
        for field, value in body.model_dump(exclude_none=True).items():
            conn.execute(f"UPDATE program SET {field}=? WHERE id=?", (value, pid))
        row = _get(conn, pid)
    publish(request, "programs")
    return ok(_row(row))


async def delete_program(request):
    pid = path_id(request)
    with open_db(request) as conn:
        _get(conn, pid)
        conn.execute("UPDATE program SET archived=1 WHERE id=?", (pid,))
    publish(request, "programs")
    return no_content()


routes = [
    Route("/api/programs", list_programs, methods=["GET"]),
    Route("/api/programs", create_program, methods=["POST"]),
    Route("/api/programs/{id:int}", patch_program, methods=["PATCH"]),
    Route("/api/programs/{id:int}", delete_program, methods=["DELETE"]),
]
