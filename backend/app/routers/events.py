import asyncio

from starlette.responses import StreamingResponse
from starlette.routing import Route

PING_SECONDS = 20


async def stream(request):
    bus = request.app.state.bus

    async def gen():
        yield "retry: 3000\n\n"
        sub = bus.subscribe()
        nxt = asyncio.ensure_future(sub.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait({nxt}, timeout=PING_SECONDS)
                if await request.is_disconnected():
                    break
                if done:
                    yield f"event: changed\ndata: {nxt.result()}\n\n"
                    nxt = asyncio.ensure_future(sub.__anext__())
                else:
                    yield ": ping\n\n"
        finally:
            nxt.cancel()
            await sub.aclose()

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


routes = [Route("/api/events", stream)]
