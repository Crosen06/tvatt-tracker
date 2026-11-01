"""Item recognition: identify, learn and manage learned pictures (spec: bildigenkanning §7)."""

from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.kitchen import repo
from app.kitchen.vision_service import VisionUnavailable
from app.models import MAX_ID, VisionCaptureIn, VisionConfirmIn
from app.web import no_content, ok, parse

NOT_RUNNING = "Kameran är inte igång."


def path_id(request) -> int:
    value = int(request.path_params["id"])
    if not 0 < value <= MAX_ID:
        raise HTTPException(404, "Finns inte.")
    return value


def _vision(request):
    return request.app.state.vision


def _frame(request):
    scanner = request.app.state.scanner
    frame = scanner.latest_frame() if scanner.running else None
    if frame is None:
        raise HTTPException(409, NOT_RUNNING)
    return frame


async def _call(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except VisionUnavailable as e:
        raise HTTPException(503, str(e))
    except repo.NotFound as e:
        raise HTTPException(404, str(e))


async def vision_status(request):
    return ok(await run_in_threadpool(_vision(request).status))


async def vision_last(request):
    return ok(_vision(request).last)


async def vision_identify(request):
    vision = _vision(request)
    if not await run_in_threadpool(lambda: vision.available):
        raise HTTPException(503, vision.message)
    return ok(await _call(vision.identify, _frame(request)))


async def vision_capture(request):
    body = await parse(request, VisionCaptureIn)
    vision = _vision(request)
    if not await run_in_threadpool(lambda: vision.available):
        raise HTTPException(503, vision.message)
    return ok(await _call(vision.capture, body.item_id, _frame(request)))


async def vision_confirm(request):
    body = await parse(request, VisionConfirmIn)
    return ok({"saved": await _call(_vision(request).confirm, body.token, body.item_id)})


async def vision_items(request):
    return ok(await run_in_threadpool(_vision(request).items))


async def item_images(request):
    return ok(await _call(_vision(request).item_images, path_id(request)))


async def delete_image(request):
    if not await run_in_threadpool(_vision(request).delete_image, path_id(request)):
        raise HTTPException(404, "Bilden finns inte.")
    return no_content()


async def delete_item_images(request):
    await _call(_vision(request).delete_item_images, path_id(request))
    return no_content()


routes = [
    Route("/api/vision/status", vision_status, methods=["GET"]),
    Route("/api/vision/last", vision_last, methods=["GET"]),
    Route("/api/vision/identify", vision_identify, methods=["POST"]),
    Route("/api/vision/capture", vision_capture, methods=["POST"]),
    Route("/api/vision/confirm", vision_confirm, methods=["POST"]),
    Route("/api/vision/items", vision_items, methods=["GET"]),
    Route("/api/vision/images/{id:int}", delete_image, methods=["DELETE"]),
    Route("/api/items/{id:int}/images", item_images, methods=["GET"]),
    Route("/api/items/{id:int}/images", delete_item_images, methods=["DELETE"]),
]
