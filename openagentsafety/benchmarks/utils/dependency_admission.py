"""Wait for local dependency availability before occupying a worker."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class DependencyAdmission:
    """Atomically reserve dependency sets; OS locks remain the safety boundary."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active: set[str] = set()

    @asynccontextmanager
    async def reserve(self, keys: tuple[str, ...]) -> AsyncIterator[None]:
        wanted = set(keys)
        async with self._condition:
            await self._condition.wait_for(lambda: not self._active & wanted)
            self._active.update(wanted)
        try:
            yield
        finally:
            async with self._condition:
                self._active.difference_update(wanted)
                self._condition.notify_all()
