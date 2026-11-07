from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any
from uuid import UUID

import httpx
from aiogram import Bot
from arq import Retry
from arq.cron import cron
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from adapters.database import DatabaseManager, session_scope
from adapters.database.models import GenerationModel
from adapters.database.repositiries import (
    GenerationRepository,
    PaymentRepository,
    ReferralRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
)
from adapters.database.repositiries.generation import ACTIVE_GENERATION_STATUSES
from adapters.runpod import RunPodClient
from adapters.settings import TaskQueueSettings, get_settings
from adapters.storage import ImageStore, MinioImageStore, generation_image_key
from adapters.system_settings import build_system_settings
from adapters.task_queue.queue import ArqTaskQueue, make_redis_settings
from domain.enums import GenerationStatus
from domain.exceptions.runpod import (
    InvalidRunPodResponseError,
    RunPodNotConfiguredError,
    RunPodRequestError,
)
from domain.services.crypto_payment import CryptoPaymentService
from domain.services.referral import ReferralService
from domain.services.telegram_stars_payment import TelegramStarsPaymentService

logger = getLogger(__name__)
BATCH_SIZE = 500
PAYMENT_CLEANUP_MAX_BATCHES = 5
# Keep expired/cancelled payment rows long enough for late provider postbacks,
# reconciliation and support. Financial history must not disappear after two hours.
PAYMENT_RETENTION = timedelta(days=30)


def _revision(updated_at: datetime) -> str:
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return updated_at.astimezone(UTC).isoformat()


async def _schedule_poll(
    ctx: dict[str, Any],
    generation_id: UUID,
    updated_at: datetime,
    *,
    defer: int = 0,
) -> None:
    revision = _revision(updated_at)
    await ctx["queue"].enqueue(
        "poll_generation",
        str(generation_id),
        job_id=f"poll_generation:{generation_id}:{revision}",
        defer=defer,
        revision=revision,
    )


async def poll_generation(
    ctx: dict[str, Any], generation_id: str, *, revision: str | None = None
) -> None:
    ident = UUID(generation_id)
    config: TaskQueueSettings = ctx["settings"]
    try:
        async with session_scope() as session:
            generation = await GenerationRepository(
                DatabaseManager(session)
            ).get_for_polling(ident)
        if generation is None or (
            revision is not None and revision != _revision(generation.updated_at)
        ):
            return
        client: RunPodClient | None = ctx["runpod"]
        if client is None:
            raise RunPodNotConfiguredError("RUNPOD_API_KEY is not configured")

        status = await client.status(
            generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
        )
        error = None
        if status == GenerationStatus.FAILED:
            error = await client.error(
                generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
            )

        if status == GenerationStatus.COMPLETED and ctx.get("images") is not None:
            await _cache_image(ctx["images"], client, generation)
        async with session_scope() as session:
            updated_at = await GenerationRepository(
                DatabaseManager(session)
            ).apply_runpod_status(
                generation, status, error=error, now=datetime.now(UTC)
            )
        # Publish only after session_scope commits; recovery fills any publish gap.
        if updated_at is not None and status in ACTIVE_GENERATION_STATUSES:
            await _schedule_poll(
                ctx, ident, updated_at, defer=config.GENERATION_POLL_INTERVAL_SECONDS
            )
    except (
        RunPodRequestError,
        InvalidRunPodResponseError,
        SQLAlchemyError,
        RedisError,
    ) as exc:
        logger.warning("Generation %s polling failed (%s)", ident, type(exc).__name__)
        raise Retry(
            defer=config.GENERATION_POLL_INTERVAL_SECONDS * ctx.get("job_try", 1)
        ) from exc


async def _cache_image(
    store: ImageStore, client: RunPodClient, generation: GenerationModel
) -> None:
    """Park the finished image in MinIO so every browser can fetch it for a day."""
    content = await client.decode_result(
        generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
    )
    if content is None:
        raise InvalidRunPodResponseError("Completed generation has no inline image")
    if not await store.put(generation.id, content):
        # Keep the row active so ARQ/recovery retries before RunPod expires output.
        raise RunPodRequestError("Generation image could not be cached")


async def recover_generations(ctx: dict[str, Any]) -> None:
    if ctx["runpod"] is None:
        return
    after = None
    while True:
        async with session_scope() as session:
            generations = await GenerationRepository(
                DatabaseManager(session)
            ).get_active_batch(after=after, limit=BATCH_SIZE)
        for generation in generations:
            await _schedule_poll(ctx, generation.id, generation.updated_at)
        if len(generations) < BATCH_SIZE:
            return
        after = generations[-1].id


async def _referral_service(session, settings) -> ReferralService:
    manager = DatabaseManager(session)
    system_settings = build_system_settings(manager, settings)
    return ReferralService(
        ReferralRepository(manager),
        WalletRepository(manager),
        TransactionRepository(manager),
        inviter_credits=await system_settings.get_int("referral.inviter_credits"),
        invitee_credits=await system_settings.get_int("referral.invitee_credits"),
    )


async def reconcile_payments(ctx: dict[str, Any]) -> None:
    """Recover provider confirmations when a webhook or bot update was missed."""
    settings = get_settings()
    payment = settings.PAYMENT_SETTINGS
    since = datetime.now(UTC) - timedelta(days=7)
    credited = 0

    if payment.ATLOS_MERCHANT_ID and payment.ATLOS_API_SECRET:
        try:
            async with httpx.AsyncClient() as client:
                async with session_scope() as session:
                    referrals = await _referral_service(session, settings)
                    manager = DatabaseManager(session)
                    service = CryptoPaymentService(
                        PaymentRepository(manager),
                        WalletRepository(manager),
                        TransactionRepository(manager),
                        UserRepository(manager),
                        client,
                        merchant_id=payment.ATLOS_MERCHANT_ID,
                        api_secret=payment.ATLOS_API_SECRET,
                        timeout=payment.PAYMENT_PROVIDER_TIMEOUT_SECONDS,
                        referrals=referrals,
                    )
                    count = await service.reconcile(since=since)
                credited += count
        except Exception:
            logger.exception("ATLOS reconciliation failed")

    if payment.TELEGRAM_BOT_TOKEN:
        bot = Bot(payment.TELEGRAM_BOT_TOKEN)
        try:
            async with session_scope() as session:
                referrals = await _referral_service(session, settings)
                manager = DatabaseManager(session)
                service = TelegramStarsPaymentService(
                    PaymentRepository(manager),
                    WalletRepository(manager),
                    TransactionRepository(manager),
                    UserRepository(manager),
                    bot,
                    referrals=referrals,
                )
                count = await service.reconcile(since=since)
            credited += count
        except Exception:
            logger.exception("Telegram Stars reconciliation failed")
        finally:
            await bot.session.close()

    if credited:
        logger.info("Reconciled %d provider payments", credited)


async def cleanup_pending_payments(ctx: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    expired = 0
    for _ in range(PAYMENT_CLEANUP_MAX_BATCHES):
        async with session_scope() as session:
            count = await PaymentRepository(DatabaseManager(session)).expire_pending(
                now, limit=BATCH_SIZE
            )
        expired += count
        if count < BATCH_SIZE:
            break
    if expired:
        logger.info("Marked %d overdue unpaid payments as expired", expired)

    deleted = 0
    cutoff = now - PAYMENT_RETENTION
    for _ in range(PAYMENT_CLEANUP_MAX_BATCHES):
        async with session_scope() as session:
            count = await PaymentRepository(DatabaseManager(session)).delete_stale(
                cutoff, limit=BATCH_SIZE
            )
        deleted += count
        if count < BATCH_SIZE:
            break
    if deleted:
        logger.info(
            "Deleted %d expired or cancelled payments older than %s",
            deleted,
            PAYMENT_RETENTION,
        )


async def cleanup_generations(ctx: dict[str, Any]) -> None:
    """Remove terminal generations after retention, preserving the credit ledger."""
    config: TaskQueueSettings = ctx["settings"]
    cutoff = datetime.now(UTC) - timedelta(days=config.GENERATION_RETENTION_DAYS)
    store: ImageStore | None = ctx.get("images")
    deleted = 0
    for _ in range(config.GENERATION_CLEANUP_BATCH_SIZE):
        async with session_scope() as session:
            repository = GenerationRepository(DatabaseManager(session))
            generation = await repository.get_expired_for_update(cutoff)
            if generation is None:
                break
            if store is not None and not await store.delete(generation.id):
                logger.warning(
                    "Generation %s cleanup deferred: image deletion failed",
                    generation.id,
                )
                break
            removed = await repository.delete_expired(generation.id, cutoff)
        deleted += int(removed)
    if deleted:
        logger.info("Deleted %d terminal generations older than %s", deleted, cutoff)


async def cleanup_generation_images(ctx: dict[str, Any]) -> None:
    """Sweep expired/orphan files independently of S3 lifecycle and row deletion."""
    store: ImageStore | None = ctx.get("images")
    if store is None:
        return
    config: TaskQueueSettings = ctx["settings"]
    storage = ctx["storage_settings"]
    cursor_key = f"{config.TASK_QUEUE_NAME}:image-cleanup:{storage.MINIO_BUCKET}:cursor"
    after = await ctx["redis"].get(cursor_key)
    if isinstance(after, bytes):
        after = after.decode()
    page = await store.list_generation_images(
        after=after or None, limit=config.IMAGE_CLEANUP_BATCH_SIZE
    )
    identifiers = {}
    for item in page:
        try:
            ident = UUID(item.key.removeprefix("generations/"))
        except ValueError:
            continue
        if generation_image_key(ident) == item.key:
            identifiers[item.key] = ident
    async with session_scope() as session:
        existing = await GenerationRepository(DatabaseManager(session)).existing_ids(
            list(identifiers.values())
        )
    now = datetime.now(UTC)
    expiry = now - timedelta(hours=storage.MINIO_RETENTION_HOURS)
    orphan_cutoff = now - timedelta(hours=config.IMAGE_ORPHAN_GRACE_HOURS)
    deleted = 0
    for item in page:
        ident = identifiers.get(item.key)
        modified = item.last_modified
        if modified is not None and modified.tzinfo is None:
            modified = modified.replace(tzinfo=UTC)
        if (
            ident is not None
            and modified is not None
            and (
                modified <= expiry
                or (ident not in existing and modified <= orphan_cutoff)
            )
        ):
            if not await store.delete(ident):
                logger.warning(
                    "Image cleanup failed for %s; it will be retried on a later pass",
                    item.key,
                )
            else:
                deleted += 1
        # Persist progress per object: timeouts/restarts must not starve later keys.
        await ctx["redis"].set(cursor_key, item.key)
    if len(page) < config.IMAGE_CLEANUP_BATCH_SIZE:
        await ctx["redis"].delete(cursor_key)
    if deleted:
        logger.info("Deleted %d expired or orphan generation images", deleted)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["settings"] = settings.TASK_QUEUE_SETTINGS
    ctx["storage_settings"] = settings.STORAGE_SETTINGS
    ctx["queue"] = ArqTaskQueue(ctx["redis"])
    ctx["runpod"] = (
        RunPodClient(settings.RUNPOD_SETTINGS)
        if settings.RUNPOD_SETTINGS.RUNPOD_API_KEY.strip()
        else None
    )
    ctx["images"] = (
        MinioImageStore(settings.STORAGE_SETTINGS)
        if settings.STORAGE_SETTINGS.enabled
        else None
    )
    if ctx["runpod"] is None:
        logger.info("RunPod polling is disabled: RUNPOD_API_KEY is not configured")
    if ctx["images"] is None:
        logger.info("MinIO image cache is disabled: MINIO_* is not configured")


async def shutdown(ctx: dict[str, Any]) -> None:
    if ctx.get("runpod") is not None:
        await ctx["runpod"].close()
    if ctx.get("images") is not None:
        await ctx["images"].close()


class WorkerSettings:
    settings = TaskQueueSettings()
    functions = [
        poll_generation,
        recover_generations,
        cleanup_pending_payments,
        reconcile_payments,
        cleanup_generations,
        cleanup_generation_images,
    ]
    cron_jobs = [
        cron(recover_generations, second=0, run_at_startup=True),
        cron(cleanup_pending_payments, second=30, run_at_startup=True),
        cron(
            cleanup_generations,
            minute={0, 10, 20, 30, 40, 50},
            second=10,
            run_at_startup=True,
        ),
        cron(
            cleanup_generation_images,
            minute={0, 10, 20, 30, 40, 50},
            second=45,
            run_at_startup=True,
        ),
        cron(
            reconcile_payments,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=True,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = make_redis_settings(settings)
    queue_name = settings.TASK_QUEUE_NAME
    max_jobs = settings.TASK_QUEUE_MAX_JOBS
    max_tries = settings.TASK_QUEUE_MAX_TRIES
    job_timeout = settings.TASK_QUEUE_JOB_TIMEOUT_SECONDS
    keep_result = 0
    timezone = UTC
