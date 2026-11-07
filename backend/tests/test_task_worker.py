import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from arq import Retry
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.database import DatabaseManager, db_session
from adapters.database.models import (
    Base,
    GenerationModel,
    PaymentModel,
    TransactionModel,
    UserModel,
    WalletModel,
    WorkflowModel,
)
from adapters.database.repositiries import GenerationRepository
from adapters.settings import RunPodSettings, StorageSettings, TaskQueueSettings
from adapters.task_queue import worker
from domain.enums import GenerationStatus, PaymentProvider, PaymentStatus
from domain.exceptions.runpod import RunPodRequestError


@pytest.fixture
async def database(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def ctx():
    return {
        "settings": TaskQueueSettings(GENERATION_POLL_INTERVAL_SECONDS=3),
        "runpod": SimpleNamespace(
            status=AsyncMock(return_value=GenerationStatus.PROCESSING),
            error=AsyncMock(return_value="Provider error"),
            close=AsyncMock(),
        ),
        "queue": SimpleNamespace(enqueue=AsyncMock()),
        "job_try": 2,
    }


async def add_generation(**overrides):
    values = dict(
        user=UserModel(first_name="Test"),
        workflow=WorkflowModel(name="portrait"),
        prompt="Portrait",
        runpod_job_id=str(uuid7()),
        runpod_endpoint_id="original-endpoint",
        status=GenerationStatus.QUEUED,
    )
    values.update(overrides)
    async with db_session.session_scope() as session:
        generation = GenerationModel(**values)
        session.add(generation)
        await session.flush()
    return generation


async def read_generation(ident):
    async with db_session.session_scope() as session:
        return await session.get(GenerationModel, ident)


async def test_active_poll_commits_before_scheduling(database, ctx):
    generation = await add_generation()

    async def check_committed(*args, **kwargs):
        saved = await read_generation(generation.id)
        assert saved.status == GenerationStatus.PROCESSING
        assert saved.completed_at is None
        assert kwargs["revision"] == worker._revision(saved.updated_at)
        assert kwargs["defer"] == 3

    ctx["queue"].enqueue.side_effect = check_committed
    await worker.poll_generation(ctx, str(generation.id))
    ctx["runpod"].status.assert_awaited_once_with(
        generation.runpod_job_id, endpoint_id="original-endpoint"
    )
    ctx["queue"].enqueue.assert_awaited_once()


@pytest.mark.parametrize(
    "status",
    [
        GenerationStatus.COMPLETED,
        GenerationStatus.FAILED,
        GenerationStatus.CANCELLED,
        GenerationStatus.TIMED_OUT,
    ],
)
async def test_terminal_poll_is_idempotent_and_saves_error(database, ctx, status):
    generation = await add_generation()
    ctx["runpod"].status.return_value = status
    ctx["runpod"].error.return_value = "x" * 5000
    await worker.poll_generation(ctx, str(generation.id))
    await worker.poll_generation(ctx, str(generation.id))
    saved = await read_generation(generation.id)
    assert saved.status == status and saved.completed_at is not None
    assert saved.error == ("x" * 4096 if status == GenerationStatus.FAILED else None)
    ctx["runpod"].status.assert_awaited_once()
    ctx["queue"].enqueue.assert_not_awaited()


@pytest.mark.parametrize("kind", ["missing", "unsubmitted", "terminal"])
async def test_irrelevant_generations_do_not_call_runpod(database, ctx, kind):
    if kind == "missing":
        ident = uuid7()
    else:
        overrides = (
            {"runpod_job_id": None}
            if kind == "unsubmitted"
            else {"status": GenerationStatus.COMPLETED}
        )
        ident = (await add_generation(**overrides)).id
    await worker.poll_generation(ctx, str(ident))
    ctx["runpod"].status.assert_not_awaited()
    ctx["queue"].enqueue.assert_not_awaited()


async def test_provider_failure_retries_without_failing_generation(database, ctx):
    generation = await add_generation()
    ctx["runpod"].status.side_effect = RunPodRequestError("offline")
    with pytest.raises(Retry) as error:
        await worker.poll_generation(ctx, str(generation.id))
    assert error.value.defer_score == 6000
    saved = await read_generation(generation.id)
    assert saved.status == GenerationStatus.QUEUED and saved.completed_at is None
    ctx["queue"].enqueue.assert_not_awaited()


async def test_cancel_during_poll_is_not_overwritten(database, ctx):
    generation = await add_generation()

    async def cancel_during_request(*args, **kwargs):
        async with db_session.session_scope() as session:
            await session.execute(
                update(GenerationModel)
                .where(GenerationModel.id == generation.id)
                .values(status=GenerationStatus.CANCELLED)
            )
        return GenerationStatus.COMPLETED

    ctx["runpod"].status.side_effect = cancel_during_request
    await worker.poll_generation(ctx, str(generation.id))
    assert (await read_generation(generation.id)).status == GenerationStatus.CANCELLED
    ctx["queue"].enqueue.assert_not_awaited()


async def test_parallel_polls_have_only_one_successor(database, ctx):
    generation = await add_generation()
    both_read = asyncio.Event()
    requests = 0

    async def status(*args, **kwargs):
        nonlocal requests
        requests += 1
        if requests == 2:
            both_read.set()
        await both_read.wait()
        return GenerationStatus.PROCESSING

    ctx["runpod"].status.side_effect = status
    await asyncio.wait_for(
        asyncio.gather(
            worker.poll_generation(ctx, str(generation.id)),
            worker.poll_generation(ctx, str(generation.id)),
        ),
        timeout=5,
    )
    ctx["queue"].enqueue.assert_awaited_once()


async def test_recovery_restores_publish_gap_and_skips_old_revision(database, ctx):
    generation = await add_generation()
    ctx["queue"].enqueue.side_effect = RedisConnectionError("offline")
    with pytest.raises(Retry):
        await worker.poll_generation(ctx, str(generation.id))
    saved = await read_generation(generation.id)
    assert saved.status == GenerationStatus.PROCESSING

    ctx["queue"].enqueue.reset_mock(side_effect=True)
    await worker.recover_generations(ctx)
    args, kwargs = ctx["queue"].enqueue.call_args
    assert args == ("poll_generation", str(generation.id))
    assert kwargs["job_id"].endswith(worker._revision(saved.updated_at))
    ctx["runpod"].status.reset_mock()
    await worker.poll_generation(
        ctx, str(generation.id), revision=worker._revision(generation.updated_at)
    )
    ctx["runpod"].status.assert_not_awaited()


async def test_recovery_paginates_and_uses_stable_job_ids(database, ctx, monkeypatch):
    monkeypatch.setattr(worker, "BATCH_SIZE", 2)
    active = [await add_generation() for _ in range(3)]
    await add_generation(runpod_job_id=None)
    await add_generation(status=GenerationStatus.COMPLETED)
    await worker.recover_generations(ctx)
    calls = ctx["queue"].enqueue.call_args_list.copy()
    assert {call.args[1] for call in calls} == {str(item.id) for item in active}
    ctx["queue"].enqueue.reset_mock()
    await worker.recover_generations(ctx)
    assert ctx["queue"].enqueue.call_args_list == calls


async def test_repository_rejects_stale_active_snapshot(database):
    generation = await add_generation()
    async with db_session.session_scope() as session:
        repo = GenerationRepository(DatabaseManager(session))
        first = await repo.apply_runpod_status(
            generation,
            GenerationStatus.PROCESSING,
            error=None,
            now=datetime.now(UTC),
        )
    assert first is not None
    async with db_session.session_scope() as session:
        stale = await GenerationRepository(
            DatabaseManager(session)
        ).apply_runpod_status(
            generation,
            GenerationStatus.COMPLETED,
            error=None,
            now=datetime.now(UTC),
        )
    assert stale is None
    assert (await read_generation(generation.id)).status == GenerationStatus.PROCESSING


async def test_payment_expiration_uses_deadlines_and_preserves_history(
    database, monkeypatch
):
    monkeypatch.setattr(worker, "BATCH_SIZE", 2)
    now = datetime.now(UTC)
    async with db_session.session_scope() as session:
        wallet = WalletModel(user=UserModel(first_name="Test"), credits=10)
        payments = []
        for status, deadline in [
            (PaymentStatus.PENDING, now - timedelta(minutes=1)),
            (PaymentStatus.PENDING, now - timedelta(minutes=2)),
            (PaymentStatus.PENDING, now - timedelta(minutes=3)),
            (PaymentStatus.PENDING, now + timedelta(minutes=10)),
            (PaymentStatus.PENDING, None),
            (PaymentStatus.PROCESSING, now - timedelta(hours=2)),
            (PaymentStatus.SUCCEEDED, now - timedelta(hours=2)),
        ]:
            values = dict(
                wallet=wallet,
                provider=PaymentProvider.TELEGRAM_STARS,
                credits=20,
                amount=Decimal(100),
                currency="XTR",
                telegram_user_id=123,
                idempotency_key=str(uuid7()),
                expires_at=deadline,
                status=status,
            )
            if status == PaymentStatus.SUCCEEDED:
                values.update(
                    paid_at=now, paid_amount=Decimal(100), provider_transaction_id="tx"
                )
            payments.append(PaymentModel(**values))
        session.add_all(payments)
        await session.flush()
        ids = [item.id for item in payments]

    await worker.cleanup_pending_payments({})
    await worker.cleanup_pending_payments({})
    async with db_session.session_scope() as session:
        statuses = [
            await session.scalar(
                select(PaymentModel.status).where(PaymentModel.id == id)
            )
            for id in ids
        ]
        assert statuses == [PaymentStatus.EXPIRED] * 3 + [
            PaymentStatus.PENDING,
            PaymentStatus.PENDING,
            PaymentStatus.EXPIRED,
            PaymentStatus.SUCCEEDED,
        ]
        assert await session.scalar(select(WalletModel.credits)) == 10
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 0
        )


async def test_worker_can_run_payment_tasks_without_runpod(monkeypatch):
    config = SimpleNamespace(
        TASK_QUEUE_SETTINGS=TaskQueueSettings(),
        RUNPOD_SETTINGS=RunPodSettings(RUNPOD_API_KEY=""),
        STORAGE_SETTINGS=StorageSettings(),
    )
    client_factory = Mock()
    monkeypatch.setattr(worker, "get_settings", lambda: config)
    monkeypatch.setattr(worker, "RunPodClient", client_factory)
    ctx = {"redis": object()}
    await worker.startup(ctx)
    assert ctx["runpod"] is None
    assert ctx["images"] is None
    await worker.recover_generations(ctx)
    await worker.shutdown(ctx)
    client_factory.assert_not_called()


async def test_worker_closes_owned_runpod_but_not_arq_pool(ctx):
    ctx["redis"] = SimpleNamespace(aclose=AsyncMock())
    await worker.shutdown(ctx)
    ctx["runpod"].close.assert_awaited_once()
    ctx["redis"].aclose.assert_not_awaited()


async def test_stale_expired_and_cancelled_payments_are_deleted_after_retention(
    database,
):
    now = datetime.now(UTC)
    async with db_session.session_scope() as session:
        wallet = WalletModel(user=UserModel(first_name="Cleanup"), credits=0)
        payments = []
        for status, updated_at in [
            (PaymentStatus.EXPIRED, now - timedelta(days=31)),
            (PaymentStatus.CANCELLED, now - timedelta(days=31)),
            (PaymentStatus.EXPIRED, now - timedelta(days=29)),
            (PaymentStatus.SUCCEEDED, now - timedelta(days=1)),
        ]:
            values = dict(
                wallet=wallet,
                provider=PaymentProvider.TELEGRAM_STARS,
                credits=20,
                amount=Decimal(100),
                currency="XTR",
                telegram_user_id=123,
                idempotency_key=str(uuid7()),
                status=status,
                updated_at=updated_at,
            )
            if status == PaymentStatus.SUCCEEDED:
                values.update(
                    paid_at=now, paid_amount=Decimal(100), provider_transaction_id="tx"
                )
            payments.append(PaymentModel(**values))
        session.add_all(payments)
        await session.flush()
        ids = [item.id for item in payments]

    await worker.cleanup_pending_payments({})

    async with db_session.session_scope() as session:
        remaining = {
            row.id for row in (await session.scalars(select(PaymentModel))).all()
        }
        assert remaining == {ids[2], ids[3]}


@pytest.mark.parametrize("failure", ["download", "invalid", "missing", "storage"])
async def test_completed_job_retries_image_before_becoming_terminal(
    database, ctx, failure
):
    from domain.exceptions.runpod import InvalidRunPodResponseError

    generation = await add_generation()
    content = b"\x89PNG\r\n\x1a\nresult"
    ctx["runpod"].status.return_value = GenerationStatus.COMPLETED
    ctx["runpod"].decode_result = AsyncMock(return_value=content)
    ctx["images"] = SimpleNamespace(put=AsyncMock(return_value=True))
    if failure == "download":
        ctx["runpod"].decode_result.side_effect = RunPodRequestError("temporary outage")
    elif failure == "invalid":
        ctx["runpod"].decode_result.side_effect = InvalidRunPodResponseError(
            "bad result"
        )
    elif failure == "missing":
        ctx["runpod"].decode_result.return_value = None
    else:
        ctx["images"].put.return_value = False
    with pytest.raises(Retry):
        await worker.poll_generation(ctx, str(generation.id))
    saved = await read_generation(generation.id)
    assert saved.status == GenerationStatus.QUEUED
    assert saved.completed_at is None

    ctx["runpod"].decode_result.side_effect = None
    ctx["runpod"].decode_result.return_value = content
    ctx["images"].put.return_value = True
    await worker.poll_generation(ctx, str(generation.id))
    saved = await read_generation(generation.id)
    assert saved.status == GenerationStatus.COMPLETED
    assert saved.completed_at is not None
    ctx["images"].put.assert_awaited_with(generation.id, content)
    assert (
        ctx["runpod"].decode_result.call_args.kwargs["endpoint_id"]
        == "original-endpoint"
    )


async def test_cleanup_generations_removes_only_old_terminal_rows_and_keeps_ledger(
    database, ctx
):
    from domain.enums import TransactionType

    now = datetime.now(UTC)
    old = now - timedelta(days=8)
    expired = [
        await add_generation(status=state, completed_at=old)
        for state in (
            GenerationStatus.COMPLETED,
            GenerationStatus.FAILED,
            GenerationStatus.CANCELLED,
            GenerationStatus.TIMED_OUT,
        )
    ]
    expired.append(await add_generation(status=GenerationStatus.FAILED, updated_at=old))
    retained = [
        await add_generation(
            status=GenerationStatus.COMPLETED,
            completed_at=now - timedelta(days=6),
            created_at=old,
        ),
        await add_generation(status=GenerationStatus.PROCESSING, updated_at=old),
        await add_generation(status=GenerationStatus.QUEUED, updated_at=old),
        await add_generation(
            status=GenerationStatus.PENDING, runpod_job_id=None, updated_at=old
        ),
    ]
    async with db_session.session_scope() as session:
        wallet = WalletModel(user_id=expired[0].user_id, credits=9)
        session.add(
            TransactionModel(
                wallet=wallet,
                generation_id=expired[0].id,
                type=TransactionType.SPEND,
                amount=-1,
                balance_before=10,
                balance_after=9,
                idempotency_key="preserved-spend",
            )
        )
    ctx["images"] = SimpleNamespace(delete=AsyncMock(return_value=True))
    await worker.cleanup_generations(ctx)
    await worker.cleanup_generations(ctx)
    async with db_session.session_scope() as session:
        assert set(await session.scalars(select(GenerationModel.id))) == {
            row.id for row in retained
        }
        ledger = (await session.scalars(select(TransactionModel))).one()
        assert ledger.amount == -1 and ledger.generation_id is None
        assert await session.scalar(select(WalletModel.credits)) == 9
    assert {call.args[0] for call in ctx["images"].delete.call_args_list} == {
        row.id for row in expired
    }
    assert ctx["images"].delete.await_count == len(expired)


async def test_cleanup_generations_retries_failed_image_deletion(database, ctx):
    row = await add_generation(
        status=GenerationStatus.COMPLETED,
        completed_at=datetime.now(UTC) - timedelta(days=8),
    )
    ctx["images"] = SimpleNamespace(delete=AsyncMock(return_value=False))
    await worker.cleanup_generations(ctx)
    assert await read_generation(row.id) is not None
    ctx["images"].delete.return_value = True
    await worker.cleanup_generations(ctx)
    assert await read_generation(row.id) is None


async def test_generation_cleanup_is_bounded_and_uses_configured_retention(
    database, ctx
):
    ctx["settings"] = TaskQueueSettings(
        GENERATION_RETENTION_DAYS=10, GENERATION_CLEANUP_BATCH_SIZE=1
    )
    recent = await add_generation(
        status=GenerationStatus.COMPLETED,
        completed_at=datetime.now(UTC) - timedelta(days=8),
    )
    old = [
        await add_generation(
            status=GenerationStatus.COMPLETED,
            completed_at=datetime.now(UTC) - timedelta(days=11),
        )
        for _ in range(2)
    ]
    await worker.cleanup_generations(ctx)
    assert await read_generation(recent.id) is not None
    assert sum([await read_generation(row.id) is not None for row in old]) == 1
    await worker.cleanup_generations(ctx)
    assert all([await read_generation(row.id) is None for row in old])


async def test_payment_cleanup_preserves_any_evidence_of_funds(database):
    now = datetime.now(UTC)
    evidence = [
        {"paid_at": now},
        {"paid_amount": Decimal(100)},
        {"provider_transaction_id": "known-transaction"},
        {
            "asset_amount": Decimal("1.5"),
            "asset_code": "USDT",
            "blockchain_code": "ETH",
        },
        {"blockchain_hash": "0xabc"},
        {"sender_address": "0xdef"},
    ]
    async with db_session.session_scope() as session:
        wallet = WalletModel(user=UserModel(first_name="Protected"), credits=0)
        rows = []
        for status in (
            PaymentStatus.EXPIRED,
            PaymentStatus.CANCELLED,
            PaymentStatus.PROCESSING,
        ):
            for index, details in enumerate(evidence):
                values = dict(details)
                if "provider_transaction_id" in values:
                    values["provider_transaction_id"] = f"transaction-{status}-{index}"
                rows.append(
                    PaymentModel(
                        wallet=wallet,
                        provider=PaymentProvider.ATLOS,
                        status=status,
                        credits=20,
                        amount=Decimal(100),
                        currency="USD",
                        idempotency_key=str(uuid7()),
                        expires_at=now - timedelta(days=40),
                        updated_at=now - timedelta(days=31),
                        **values,
                    )
                )
        session.add_all(rows)
        await session.flush()
        expected = {row.id: row.status for row in rows}
    await worker.cleanup_pending_payments({})
    async with db_session.session_scope() as session:
        assert {
            row.id: row.status for row in await session.scalars(select(PaymentModel))
        } == expected


async def test_processing_expiration_starts_new_retention_window(database):
    now = datetime.now(UTC)
    async with db_session.session_scope() as session:
        row = PaymentModel(
            wallet=WalletModel(user=UserModel(first_name="Old checkout"), credits=0),
            provider=PaymentProvider.TELEGRAM_STARS,
            status=PaymentStatus.PROCESSING,
            credits=20,
            amount=Decimal(100),
            currency="XTR",
            idempotency_key="old-processing",
            expires_at=now - timedelta(days=40),
            updated_at=now - timedelta(days=40),
        )
        session.add(row)
        await session.flush()
        ident = row.id
    await worker.cleanup_pending_payments({})
    async with db_session.session_scope() as session:
        saved = await session.get(PaymentModel, ident)
        assert saved.status == PaymentStatus.EXPIRED
        assert saved.updated_at.replace(tzinfo=UTC) >= now


def image_cleanup_context(ctx, objects):
    from adapters.storage import StoredGenerationImage

    cursor = {}

    async def get(key):
        return cursor.get(key)

    async def set_value(key, value):
        cursor[key] = value

    async def delete_key(key):
        cursor.pop(key, None)

    async def page(*, after=None, limit=100):
        return [
            StoredGenerationImage(key, modified)
            for key, modified in sorted(objects.items())
            if not after or key > after
        ][:limit]

    async def remove(ident):
        objects.pop(f"generations/{ident}", None)
        return True

    ctx["redis"] = SimpleNamespace(
        get=AsyncMock(side_effect=get),
        set=AsyncMock(side_effect=set_value),
        delete=AsyncMock(side_effect=delete_key),
    )
    ctx["storage_settings"] = StorageSettings(MINIO_RETENTION_HOURS=24)
    ctx["images"] = SimpleNamespace(
        list_generation_images=AsyncMock(side_effect=page),
        delete=AsyncMock(side_effect=remove),
    )
    return cursor


async def test_image_sweep_expires_unread_images_and_removes_only_aged_orphans(
    database, ctx
):
    now = datetime.now(UTC)
    expired = await add_generation()
    live = await add_generation()
    missing = uuid7()
    fresh = uuid7()
    objects = {
        f"generations/{expired.id}": now - timedelta(hours=25),
        f"generations/{live.id}": now - timedelta(hours=2),
        f"generations/{missing}": now - timedelta(hours=2),
        f"generations/{fresh}": now - timedelta(minutes=10),
        "generations/not-a-uuid": now - timedelta(days=10),
    }
    cursor = image_cleanup_context(ctx, objects)
    await worker.cleanup_generation_images(ctx)
    assert set(objects) == {
        f"generations/{live.id}",
        f"generations/{fresh}",
        "generations/not-a-uuid",
    }
    assert not cursor
    assert await read_generation(expired.id) is not None
    assert await read_generation(live.id) is not None


async def test_image_cleanup_cursor_continues_across_batches_and_failure(database, ctx):
    ctx["settings"] = TaskQueueSettings(IMAGE_CLEANUP_BATCH_SIZE=1)
    ids = sorted([uuid7(), uuid7()], key=str)
    objects = {
        f"generations/{ident}": datetime.now(UTC) - timedelta(hours=2) for ident in ids
    }
    cursor = image_cleanup_context(ctx, objects)
    await worker.cleanup_generation_images(ctx)
    assert list(objects) == [f"generations/{ids[1]}"]

    delete = ctx["images"].delete
    original = delete.side_effect
    delete.side_effect = None
    delete.return_value = False
    await worker.cleanup_generation_images(ctx)
    assert list(cursor.values()) == [f"generations/{ids[1]}"]
    assert len(objects) == 1

    # A failed object is skipped until the cursor reaches the end and wraps.
    delete.side_effect = original
    await worker.cleanup_generation_images(ctx)
    assert not cursor and len(objects) == 1
    await worker.cleanup_generation_images(ctx)
    assert not objects
    await worker.cleanup_generation_images(ctx)
    assert not cursor


async def test_cleanup_tasks_are_registered_without_runpod(database, ctx):
    ctx["runpod"] = None
    ctx["images"] = None
    await worker.cleanup_generations(ctx)
    await worker.cleanup_generation_images(ctx)
    for task in (worker.cleanup_generations, worker.cleanup_generation_images):
        assert task in worker.WorkerSettings.functions
        assert any(
            job.coroutine is task and job.run_at_startup
            for job in worker.WorkerSettings.cron_jobs
        )
