"""Items (pantry) and the shopping list."""

import sqlite3

from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.db import open_db
from app.kitchen import repo
from app.models import ItemIn, ItemPatch, ShoppingIn, UnpackIn
from app.web import no_content, ok, parse, path_id, publish

MSG_TAKEN = "Det finns redan en vara som heter så."


def _guard(fn):
    async def wrapper(request):
        try:
            return await fn(request)
        except repo.NotFound as e:
            raise HTTPException(404, str(e))
        except sqlite3.IntegrityError:
            raise HTTPException(409, MSG_TAKEN)

    return wrapper


@_guard
async def list_items(request):
    with open_db(request) as conn:
        return ok(repo.list_items(conn))


@_guard
async def create_item(request):
    body = await parse(request, ItemIn)
    with open_db(request) as conn:
        if repo.name_taken(conn, body.name):
            raise HTTPException(409, MSG_TAKEN)
        iid = repo.create_item(conn, **body.model_dump())
        item = repo.item_json(repo.fetch_item(conn, iid))
    publish(request, "items", "recipes")
    return ok(item, 201)


@_guard
async def get_item(request):
    with open_db(request) as conn:
        item = repo.item_json(repo.fetch_item(conn, path_id(request)))
        item["barcodes"] = [
            {"code": r["code"], "product_name": r["product_name"]}
            for r in conn.execute("SELECT code, product_name FROM barcode WHERE item_id=? ORDER BY created_at", (item["id"],))
        ]
    return ok(item)


@_guard
async def patch_item(request):
    iid = path_id(request)
    body = await parse(request, ItemPatch)
    changes = body.model_dump(exclude_unset=True)
    with open_db(request) as conn:
        row = repo.fetch_item(conn, iid)
        previous = {"status": row["status"], "count": row["count"]}
        if changes.get("name") and repo.name_taken(conn, changes["name"], except_id=iid):
            raise HTTPException(409, MSG_TAKEN)
        repo.update_item(conn, iid, {k: v for k, v in changes.items() if v is not None})
        entry = None
        if changes.get("status") is not None or "count" in changes:
            if "count" in changes and changes["count"] is None:
                conn.execute("UPDATE item SET count=NULL WHERE id=?", (iid,))
                entry = repo.set_status(conn, iid, changes.get("status"))
            else:
                entry = repo.set_status(conn, iid, changes.get("status"), changes.get("count"))
        item = repo.item_json(repo.fetch_item(conn, iid))
    publish(request, "items", "shopping", "recipes")
    return ok({"item": item, "list_entry_id": entry, "previous": previous})


@_guard
async def archive_item(request):
    with open_db(request) as conn:
        repo.archive_item(conn, path_id(request))
    publish(request, "items", "shopping", "recipes")
    return no_content()


@_guard
async def get_shopping(request):
    with open_db(request) as conn:
        return ok({"entries": repo.list_entries(conn), "frequent": repo.frequent(conn)})


@_guard
async def add_shopping(request):
    body = await parse(request, ShoppingIn)
    with open_db(request) as conn:
        eid = repo.add_to_list(conn, item_id=body.item_id, text=body.text, note=body.note)
        entry = next((e for e in repo.list_entries(conn) if e["id"] == eid), None)
    if entry is None:
        return ok({"entry": None, "already": True})
    publish(request, "shopping", "items")
    return ok({"entry": entry}, 201)


@_guard
async def delete_shopping(request):
    with open_db(request) as conn:
        repo.delete_entry(conn, path_id(request))
    publish(request, "shopping", "items")
    return no_content()


@_guard
async def unpack(request):
    body = await parse(request, UnpackIn)
    with open_db(request) as conn:
        repo.unpack(conn, body.entry_ids)
    publish(request, "shopping", "items", "recipes")
    return ok({"ok": True})


routes = [
    Route("/api/items", list_items, methods=["GET"]),
    Route("/api/items", create_item, methods=["POST"]),
    Route("/api/items/{id:int}", get_item, methods=["GET"]),
    Route("/api/items/{id:int}", patch_item, methods=["PATCH"]),
    Route("/api/items/{id:int}", archive_item, methods=["DELETE"]),
    Route("/api/shopping", get_shopping, methods=["GET"]),
    Route("/api/shopping", add_shopping, methods=["POST"]),
    Route("/api/shopping/{id:int}", delete_shopping, methods=["DELETE"]),
    Route("/api/shopping/unpack", unpack, methods=["POST"]),
]
