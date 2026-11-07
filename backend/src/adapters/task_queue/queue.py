from asyncio import Lock
from datetime import timedelta
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job

from adapters.settings import TaskQueueSettings
from domain.validators import NumberValidator

_pool: ArqRedis | None = None
_pool_lock = Lock()


def make_redis_settings(settings: TaskQueueSettings | None = None) -> RedisSettings:
    settings = settings or TaskQueueSettings()
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def create_queue() -> ArqTaskQueue:
    global _pool
    async with _pool_lock:
        if _pool is None:
            settings = TaskQueueSettings()
            _pool = await create_pool(
                make_redis_settings(settings),
                default_queue_name=settings.TASK_QUEUE_NAME,
            )
        return ArqTaskQueue(_pool)


async def close_queue() -> None:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.aclose(close_connection_pool=True)
            _pool = None


class ArqTaskQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue(
        self,
        name: str,
        *args: Any,
        defer: int | float | timedelta = 0,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> Job | None:
        seconds = defer.total_seconds() if isinstance(defer, timedelta) else defer
        NumberValidator.validate(seconds, min_value=0)
        return await self._pool.enqueue_job(
            name, *args, _defer_by=defer or None, _job_id=job_id, **kwargs
        )
