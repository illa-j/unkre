import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.settings import TaskQueueSettings
from adapters.task_queue import queue as queue_module
from domain.exceptions import ValidationError


async def test_enqueue_passes_job_options_and_returns_job():
    pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
    queue = queue_module.ArqTaskQueue(pool)
    result = await queue.enqueue(
        "future_task", "id", defer=timedelta(seconds=3), job_id="unique", value=2
    )
    assert result is pool.enqueue_job.return_value
    pool.enqueue_job.assert_awaited_once_with(
        "future_task",
        "id",
        _defer_by=timedelta(seconds=3),
        _job_id="unique",
        value=2,
    )
    pool.enqueue_job.return_value = None
    assert await queue.enqueue("future_task", job_id="unique") is None


@pytest.mark.parametrize("defer", [-1, timedelta(seconds=-1), True, float("nan")])
async def test_invalid_delay_is_rejected_before_redis(defer):
    pool = SimpleNamespace(enqueue_job=AsyncMock())
    with pytest.raises(ValidationError):
        await queue_module.ArqTaskQueue(pool).enqueue("task", defer=defer)
    pool.enqueue_job.assert_not_awaited()


async def test_concurrent_creation_reuses_pool_and_close_allows_reconnect(monkeypatch):
    pools = [SimpleNamespace(aclose=AsyncMock()) for _ in range(2)]

    async def connect(*args, **kwargs):
        await asyncio.sleep(0)
        return pools[connect_mock.await_count - 1]

    connect_mock = AsyncMock(side_effect=connect)
    config = TaskQueueSettings(
        REDIS_URL="redis://localhost:6380/2", TASK_QUEUE_NAME="unkre:test"
    )
    monkeypatch.setattr(queue_module, "_pool", None)
    monkeypatch.setattr(queue_module, "_pool_lock", asyncio.Lock())
    monkeypatch.setattr(queue_module, "create_pool", connect_mock)
    monkeypatch.setattr(queue_module, "TaskQueueSettings", lambda: config)
    queues = await asyncio.gather(*(queue_module.create_queue() for _ in range(10)))
    assert all(queue._pool is pools[0] for queue in queues)
    connect_mock.assert_awaited_once()
    args, kwargs = connect_mock.call_args
    assert args[0].port == 6380 and args[0].database == 2
    assert kwargs == {"default_queue_name": "unkre:test"}

    await queue_module.close_queue()
    await queue_module.close_queue()
    pools[0].aclose.assert_awaited_once_with(close_connection_pool=True)
    assert (await queue_module.create_queue())._pool is pools[1]
    await queue_module.close_queue()
    pools[1].aclose.assert_awaited_once_with(close_connection_pool=True)


async def test_failed_connection_can_be_retried(monkeypatch):
    pool = object()
    connect = AsyncMock(side_effect=[ConnectionError("offline"), pool])
    monkeypatch.setattr(queue_module, "_pool", None)
    monkeypatch.setattr(queue_module, "create_pool", connect)
    with pytest.raises(ConnectionError):
        await queue_module.create_queue()
    assert (await queue_module.create_queue())._pool is pool
