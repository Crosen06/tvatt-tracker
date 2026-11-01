"""Webcam scanning and barcode ↔ item links (spec §8)."""

import asyncio

from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import StreamingResponse
from starlette.routing import Route

from app import clock
from app.db import open_db
from app.kitchen import fetch, products, repo
from app.kitchen.ingredients import normalize
from app.kitchen.products import valid_gtin
from app.kitchen.scanner import CameraUnavailable
from app.models import BarcodeIn
from app.web import no_content, ok, parse, publish

MSG_BAD_CODE = "Ogiltig streckkod."
FRAME_INTERVAL = 0.1
CANDIDATES = 5


async def scan_start(request):
    scanner = request.app.state.scanner
    try:
        await run_in_threadpool(scanner.start)
    except CameraUnavailable as e:
        raise HTTPException(503, str(e))
    await run_in_threadpool(request.app.state.vision.start_session, scanner)
    publish(request, "scan")
    return ok({"running": True})


async def scan_heartbeat(request):
    """Keeps a running camera alive. Never starts it: a dead camera must show up as an error."""
    scanner = request.app.state.scanner
    if not scanner.running:
        raise HTTPException(409, scanner.error or "Kameran är inte igång.")
    scanner.heartbeat()
    return ok({"running": True})


async def scan_stop(request):
    await run_in_threadpool(request.app.state.scanner.stop)
    return ok({"running": False})


async def scan_last(request):
    s = request.app.state.scanner
    last = s.last or {"seq": 0, "code": None, "at": None}
    return ok({**last, "error": s.error, "running": s.running})


async def scan_stream(request):
    scanner = request.app.state.scanner
    if not scanner.running:
        raise HTTPException(409, "Kameran är inte igång.")

    async def frames():
        sent = None
        while scanner.running:
            jpeg = scanner.latest_jpeg()
            if jpeg is not None and jpeg is not sent:
                sent = jpeg
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            await asyncio.sleep(FRAME_INTERVAL)

    headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers=headers)


def _code(request) -> str:
    code = request.path_params["code"]
    if not valid_gtin(code):
        raise HTTPException(422, MSG_BAD_CODE)
    return code


def _candidates(conn, product) -> list[dict]:
    """Items whose name appears in the product name, longest first."""
    if product is None:
        return []
    text = f" {normalize(product.name)} "
    hits = []
    for ref in repo.item_refs(conn):
        names = [normalize(n) for n in [ref.name, *ref.match_words] if normalize(n)]
        best = max((len(n) for n in names if f" {n} " in text or any(w.endswith(n) and len(n) >= 4 for w in text.split())), default=0)
        if best:
            hits.append((best, ref.id))
    hits.sort(reverse=True)
    return [repo.item_json(repo.fetch_item(conn, iid)) for _, iid in hits[:CANDIDATES]]


def _mapped_item(conn, code: str):
    row = conn.execute(
        "SELECT b.item_id FROM barcode b JOIN item i ON i.id = b.item_id WHERE b.code=? AND i.archived=0", (code,)
    ).fetchone()
    return repo.item_json(repo.fetch_item(conn, row["item_id"])) if row else None


async def get_barcode(request):
    code = _code(request)
    with open_db(request) as conn:
        item = _mapped_item(conn, code)
    if item:
        return ok({"code": code, "item": item, "product": None, "lookup_failed": False, "candidates": []})
    product, failed = None, False
    try:
        product = await run_in_threadpool(products.lookup, code)
    except fetch.FetchError:
        failed = True
    with open_db(request) as conn:
        candidates = _candidates(conn, product)
    return ok({
        "code": code, "item": None, "lookup_failed": failed, "candidates": candidates,
        "product": None if product is None else {
            "name": product.name, "brand": product.brand, "quantity": product.quantity,
            "category": product.category, "short_name": product.short_name,
        },
    })


async def link_barcode(request):
    body = await parse(request, BarcodeIn)
    if not valid_gtin(body.code):
        raise HTTPException(422, MSG_BAD_CODE)
    with open_db(request) as conn:
        if body.new_item is not None:
            if repo.name_taken(conn, body.new_item.name):
                raise HTTPException(409, "Det finns redan en vara som heter så.")
            iid = repo.create_item(conn, name=body.new_item.name, category=body.new_item.category)
        else:
            try:
                iid = repo.fetch_item(conn, body.item_id)["id"]
            except repo.NotFound as e:
                raise HTTPException(404, str(e))
        conn.execute(
            "INSERT INTO barcode (code, item_id, product_name, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(code) DO UPDATE SET item_id=excluded.item_id, "
            "product_name=COALESCE(excluded.product_name, barcode.product_name)",
            (body.code, iid, body.product_name, clock.to_iso(clock.utcnow())),
        )
        item = repo.item_json(repo.fetch_item(conn, iid))
    await run_in_threadpool(request.app.state.vision.on_linked, body.code, iid)
    publish(request, "items", "recipes")
    return ok(item)


async def delete_barcode(request):
    code = request.path_params["code"]
    with open_db(request) as conn:
        if conn.execute("DELETE FROM barcode WHERE code=?", (code,)).rowcount == 0:
            raise HTTPException(404, "Streckkoden finns inte.")
    publish(request, "items")
    return no_content()


routes = [
    Route("/api/scan/start", scan_start, methods=["POST"]),
    Route("/api/scan/heartbeat", scan_heartbeat, methods=["POST"]),
    Route("/api/scan/stop", scan_stop, methods=["POST"]),
    Route("/api/scan/last", scan_last, methods=["GET"]),
    Route("/api/scan/stream", scan_stream, methods=["GET"]),
    Route("/api/barcodes", link_barcode, methods=["POST"]),
    Route("/api/barcodes/{code}", get_barcode, methods=["GET"]),
    Route("/api/barcodes/{code}", delete_barcode, methods=["DELETE"]),
]
