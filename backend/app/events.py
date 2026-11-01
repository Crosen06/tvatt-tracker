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

    def open(self) -> asyncio.Queue:
        """Register a listener queue; always pair with close()."""
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def close(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    async def subscribe(self) -> AsyncIterator[str]:
        q = self.open()
        try:
            while True:
                yield await q.get()
        finally:
            self.close(q)
