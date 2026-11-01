from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.db import open_db
from app.models import PersonIn, PersonPatch
from app.web import ok, parse, path_id, publish


def _row(r):
    return {"id": r["id"], "name": r["name"], "color": r["color"], "sort": r["sort"]}


async def list_people(request):
    with open_db(request) as conn:
        return ok([_row(r) for r in conn.execute("SELECT * FROM person ORDER BY sort, id")])


async def create_person(request):
    body = await parse(request, PersonIn)
    with open_db(request) as conn:
        sort = conn.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM person").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO person (name, color, sort) VALUES (?, ?, ?)", (body.name.strip(), body.color, sort)
        )
        row = conn.execute("SELECT * FROM person WHERE id=?", (cur.lastrowid,)).fetchone()
    publish(request, "people")
    return ok(_row(row), 201)


async def patch_person(request):
    pid = path_id(request)
    body = await parse(request, PersonPatch)
    with open_db(request) as conn:
        if not conn.execute("SELECT 1 FROM person WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, "Personen finns inte.")
        for field, value in body.model_dump(exclude_none=True).items():
            conn.execute(f"UPDATE person SET {field}=? WHERE id=?", (value.strip() if field == "name" else value, pid))
        row = conn.execute("SELECT * FROM person WHERE id=?", (pid,)).fetchone()
    publish(request, "people")
    return ok(_row(row))


routes = [
    Route("/api/people", list_people, methods=["GET"]),
    Route("/api/people", create_person, methods=["POST"]),
    Route("/api/people/{id:int}", patch_person, methods=["PATCH"]),
]
