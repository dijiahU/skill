"""Dependency waiters must not consume execution capacity."""

import asyncio

from benchmarks.utils.dependency_admission import DependencyAdmission


def test_waiter_does_not_block_independent_work() -> None:
    async def scenario() -> None:
        admission = DependencyAdmission()
        workers = asyncio.Semaphore(2)
        release = asyncio.Event()
        started = asyncio.Event()
        independent = asyncio.Event()

        async def first() -> None:
            async with admission.reserve(("plane",)), workers:
                started.set()
                await release.wait()

        async def blocked() -> None:
            async with admission.reserve(("plane",)), workers:
                assert release.is_set()

        async def free() -> None:
            async with admission.reserve(()), workers:
                independent.set()

        first_task = asyncio.create_task(first())
        await started.wait()
        blocked_task = asyncio.create_task(blocked())
        free_task = asyncio.create_task(free())
        await asyncio.wait_for(independent.wait(), 1)
        release.set()
        await asyncio.gather(first_task, blocked_task, free_task)

    asyncio.run(scenario())


def test_multi_service_atomic_and_cancellation_safe() -> None:
    async def scenario() -> None:
        admission = DependencyAdmission()
        async with admission.reserve(("gitlab",)):

            async def blocked() -> None:
                async with admission.reserve(("plane", "gitlab")):
                    raise AssertionError("Must remain blocked")

            task = asyncio.create_task(blocked())
            await asyncio.sleep(0)
            async with admission.reserve(("plane",)):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        async with admission.reserve(("gitlab", "plane")):
            pass

    asyncio.run(scenario())
