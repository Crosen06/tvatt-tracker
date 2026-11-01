import asyncio

from starlette.responses import StreamingResponse
from starlette.routing import Route

PING_SECONDS = 20


async def stream(request):
    bus = request.app.state.bus

    async def gen():
        q = bus.open()
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    topic = await asyncio.wait_for(q.get(), PING_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                else:
                    yield f"event: changed\ndata: {topic}\n\n"
        finally:
            bus.close(q)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


routes = [Route("/api/events", stream)]
