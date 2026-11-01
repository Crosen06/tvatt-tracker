from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.routing import Route

from app import clock
from app.db import open_db
from app.models import BasketIn, GarmentIn, GarmentPatch
from app.photos import PhotoTooLarge, UnsupportedPhoto, delete_photo, save_photo
from app.web import no_content, ok, parse, path_id, publish, validate

MAX_UPLOAD = 20 * 1024 * 1024
MSG_FORMAT = "Bildformatet stöds inte. Ta en ny bild med kameran."
MSG_IN_WASH = "Plagget ligger i maskinen just nu."
MSG_TOO_BIG = "Bilden är för stor. Ta en ny bild med kameran."
CHUNK = 1024 * 1024

SELECT = """
SELECT g.*, EXISTS(
    SELECT 1 FROM wash_item wi JOIN wash w ON w.id = wi.wash_id
    WHERE wi.garment_id = g.id AND w.status = 'running'
) AS in_wash
FROM garment g
"""


def garment_json(r) -> dict:
    photo = r["photo"]
    return {
        "id": r["id"],
        "person_id": r["person_id"],
        "name": r["name"],
        "photo_url": f"/photos/{photo}" if photo else None,
        "thumb_url": f"/photos/thumb/{photo}" if photo else None,
        "max_temp": r["max_temp"],
        "color": r["color"],
        "max_spin": r["max_spin"],
        "care": r["care"],
        "tumble_dry": bool(r["tumble_dry"]),
        "in_basket": bool(r["in_basket"]),
        "in_wash": bool(r["in_wash"]),
        "basket_since": r["basket_since"],
    }


def fetch_garment(conn, gid: int):
    row = conn.execute(SELECT + " WHERE g.id=? AND g.archived=0", (gid,)).fetchone()
    if not row:
        raise HTTPException(404, "Plagget finns inte.")
    return row


def _check_person(conn, person_id: int) -> None:
    if not conn.execute("SELECT 1 FROM person WHERE id=?", (person_id,)).fetchone():
        raise HTTPException(422, "Personen finns inte.")


def _coerce_form(fields: dict) -> dict:
    """Multipart fields arrive as strings; numeric tags must be ints for Literal checks."""
    for key in ("person_id", "max_temp", "max_spin"):
        if isinstance(fields.get(key), str) and fields[key].strip().lstrip("-").isdigit():
            fields[key] = int(fields[key])
    return fields


def _check_length(request) -> None:
    """Refuse oversized requests before the body is read."""
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_UPLOAD + CHUNK:
        raise HTTPException(413, MSG_TOO_BIG)


async def _read_photo(form, request) -> str:
    upload = form.get("photo")
    if not isinstance(upload, UploadFile):
        raise HTTPException(422, "Foto saknas.")
    chunks, size = [], 0
    while chunk := await upload.read(CHUNK):
        size += len(chunk)
        if size > MAX_UPLOAD:
            raise HTTPException(413, MSG_TOO_BIG)
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(422, "Foto saknas.")
    try:
        return await run_in_threadpool(save_photo, data, request.app.state.data_dir / "photos")
    except UnsupportedPhoto:
        raise HTTPException(415, MSG_FORMAT)
    except PhotoTooLarge:
        raise HTTPException(413, MSG_TOO_BIG)


async def list_garments(request):
    q = request.query_params
    sql, args = SELECT + " WHERE g.archived=0", []
    if q.get("person_id"):
        sql += " AND g.person_id=?"
        args.append(int(q["person_id"]))
    if q.get("in_basket") in ("1", "true"):
        sql += " AND g.in_basket=1"
    sql += " ORDER BY g.name COLLATE NOCASE, g.id"
    with open_db(request) as conn:
        return ok([garment_json(r) for r in conn.execute(sql, args)])


async def create_garment(request):
    _check_length(request)
    async with request.form(max_part_size=MAX_UPLOAD) as form:
        fields = _coerce_form({k: v for k, v in form.items() if k != "photo"})
        body = validate(GarmentIn, fields)
        with open_db(request) as conn:
            _check_person(conn, body.person_id)
        photo = await _read_photo(form, request)
    with open_db(request) as conn:
        cur = conn.execute(
            "INSERT INTO garment (person_id, name, photo, max_temp, color, max_spin, care, tumble_dry, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.person_id, body.name.strip(), photo, body.max_temp, body.color, body.max_spin,
             body.care, int(body.tumble_dry), clock.to_iso(clock.utcnow())),
        )
        row = fetch_garment(conn, cur.lastrowid)
    publish(request, "garments")
    return ok(garment_json(row), 201)


async def patch_garment(request):
    gid = path_id(request)
    body = await parse(request, GarmentPatch)
    with open_db(request) as conn:
        fetch_garment(conn, gid)
        changes = body.model_dump(exclude_none=True)
        if "person_id" in changes:
            _check_person(conn, changes["person_id"])
        for field, value in changes.items():
            if field == "name":
                value = value.strip()
            if field == "tumble_dry":
                value = int(value)
            conn.execute(f"UPDATE garment SET {field}=? WHERE id=?", (value, gid))
        row = fetch_garment(conn, gid)
    publish(request, "garments")
    return ok(garment_json(row))


async def replace_photo(request):
    gid = path_id(request)
    _check_length(request)
    with open_db(request) as conn:
        old = fetch_garment(conn, gid)["photo"]
    async with request.form(max_part_size=MAX_UPLOAD) as form:
        photo = await _read_photo(form, request)
    with open_db(request) as conn:
        conn.execute("UPDATE garment SET photo=? WHERE id=?", (photo, gid))
        row = fetch_garment(conn, gid)
    delete_photo(old, request.app.state.data_dir / "photos")
    publish(request, "garments")
    return ok(garment_json(row))


async def archive_garment(request):
    gid = path_id(request)
    with open_db(request) as conn:
        if fetch_garment(conn, gid)["in_wash"]:
            raise HTTPException(409, MSG_IN_WASH)
        conn.execute("UPDATE garment SET archived=1, in_basket=0, basket_since=NULL WHERE id=?", (gid,))
    publish(request, "garments")
    return no_content()


async def set_basket(request):
    gid = path_id(request)
    body = await parse(request, BasketIn)
    with open_db(request) as conn:
        row = fetch_garment(conn, gid)
        if row["in_wash"]:
            raise HTTPException(409, MSG_IN_WASH)
        if body.in_basket and not row["in_basket"]:
            conn.execute(
                "UPDATE garment SET in_basket=1, basket_since=? WHERE id=?", (clock.to_iso(clock.utcnow()), gid)
            )
        elif not body.in_basket:
            conn.execute("UPDATE garment SET in_basket=0, basket_since=NULL WHERE id=?", (gid,))
        row = fetch_garment(conn, gid)
    publish(request, "garments")
    return ok(garment_json(row))


routes = [
    Route("/api/garments", list_garments, methods=["GET"]),
    Route("/api/garments", create_garment, methods=["POST"]),
    Route("/api/garments/{id:int}", patch_garment, methods=["PATCH"]),
    Route("/api/garments/{id:int}", archive_garment, methods=["DELETE"]),
    Route("/api/garments/{id:int}/photo", replace_photo, methods=["POST"]),
    Route("/api/garments/{id:int}/basket", set_basket, methods=["POST"]),
]
