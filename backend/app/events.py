"""In-process pub/sub used to push "something changed" to SSE clients."""

import asyncio
from collections.abc import AsyncIterator


class EventBus:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def publish(self, topic: str) -> None:
        for q in list(self._queues):
            if self._loop is not None and self._loop.is_running():
                try:
                    running = asyncio.get_running_loop()
                except RuntimeError:
                    running = None
                if running is self._loop:
                    q.put_nowait(topic)
                else:
                    self._loop.call_soon_threadsafe(q.put_nowait, topic)

    async def subscribe(self) -> AsyncIterator[str]:
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._queues.discard(q)
