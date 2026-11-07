import asyncio
import base64
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid7

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.database import DatabaseManager, db_session
from adapters.database.models import (
    Base,
    GenerationModel,
    LoraModel,
    TransactionModel,
    UserModel,
    WalletModel,
    WorkflowModel,
)
from adapters.database.repositiries import (
    GenerationRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
    WorkflowRepository,
)
from adapters.runpod import RunPodClient
from adapters.runpod import workflow as workflow_module
from adapters.settings import RunPodSettings
from domain.entities import Generation
from domain.enums import GenerationStatus, TransactionType
from domain.exceptions import ValidationError
from domain.exceptions.auth import InvalidCredentialsError, UserBlockedError
from domain.exceptions.generation import (
    GenerationNotFoundError,
    InsufficientCreditsError,
    InvalidGenerationImagesError,
    InvalidGenerationStateError,
    LoraNotInWorkflowError,
    TooManyReferenceImagesError,
    UnsupportedReferenceImagesError,
    WorkflowNotFoundError,
)
from domain.exceptions.repositories import InvalidRepositoryFieldError
from domain.exceptions.runpod import RunPodRequestError
from domain.services import GenerationService
from tests.test_package_imports import run_isolated


@pytest.fixture
async def data(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'generation-service.db'}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def setup_connection(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine.sync_engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db_session.session_scope() as session:
        lora = LoraModel(name="style.safetensors")
        workflow = WorkflowModel(name="portrait", loras=[lora], generation_credits=1)
        other = LoraModel(name="other.safetensors")
        users = [
            UserModel(first_name="First"),
            UserModel(first_name="Second"),
            UserModel(first_name="Blocked", is_blocked=True),
        ]
        session.add_all(
            [workflow, other, *[WalletModel(user=user, credits=20) for user in users]]
        )
        await session.flush()
    runner = SimpleNamespace(
        endpoint_for=Mock(return_value="endpoint-original"),
        run=AsyncMock(side_effect=lambda *args, **kwargs: "job-" + str(uuid7())),
        cancel=AsyncMock(return_value=GenerationStatus.CANCELLED),
    )

    def service(session, *, runpod=None):
        manager = DatabaseManager(session)
        return GenerationService(
            GenerationRepository(manager),
            WorkflowRepository(manager),
            UserRepository(manager),
            runpod or runner,
            wallets=WalletRepository(manager),
            transactions=TransactionRepository(manager),
        )

    try:
        yield SimpleNamespace(
            workflow=workflow,
            lora=lora,
            other=other,
            users=users,
            runner=runner,
            service=service,
        )
    finally:
        await engine.dispose()


async def pending(data, *, user=0, **overrides):
    values = dict(
        user_id=data.users[user].id, workflow_id=data.workflow.id, prompt="Portrait"
    )
    values.update(overrides)
    async with db_session.session_scope() as session:
        return await data.service(session).create(Generation(**values))


async def submit(data, *, user=0, **overrides):
    values = dict(workflow_id=data.workflow.id, prompt="Portrait")
    values.update(overrides)
    async with db_session.session_scope() as session:
        return await data.service(session).create_generation(
            data.users[user].id, **values
        )


async def count_generations():
    async with db_session.session_scope() as session:
        return await session.scalar(select(func.count()).select_from(GenerationModel))


def test_generation_service_imports_without_adapters():
    run_isolated("""
import importlib.abc
import sys

class RejectAdapters(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "adapters" or fullname.startswith("adapters."):
            raise AssertionError(f"Service imported {fullname}")

sys.meta_path.insert(0, RejectAdapters())
from domain.services import GenerationService
assert not any(name.startswith("adapters") for name in sys.modules)
""")


async def test_crud_round_trip_and_domain_lora_keys(data):
    item = await pending(
        data, prompt="  Portrait  ", loras_strength={data.lora.id: 1.5}
    )
    assert isinstance(item.id, UUID) and item.prompt == "Portrait"
    assert item.status == GenerationStatus.PENDING and item.loras_strength == {
        data.lora.id: 1.5
    }
    async with db_session.session_scope() as session:
        service = data.service(session)
        saved = await service.get(item.id)
        assert saved.loras_strength == item.loras_strength
        assert [row.id for row in await service.get_all()] == [item.id]
        updated = await service.update(
            item.id,
            {"prompt": "New prompt", "loras_strength": {data.lora.id: 0.75}, "seed": 0},
        )
        assert updated.prompt == "New prompt" and updated.seed == 0
        assert updated.loras_strength == {data.lora.id: 0.75}
        row = await session.get(GenerationModel, item.id)
        assert row.loras_strength == {str(data.lora.id): 0.75}
    async with db_session.session_scope() as session:
        assert await data.service(session).delete(item.id) is True
        assert await data.service(session).delete(item.id) is False
    data.runner.run.assert_not_awaited()


async def test_create_user_generation_submits_names_and_saves_runpod_identifiers(data):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.name = "Qwen Image 2.1"
    image = base64.b64encode(b"image-data").decode()
    item = await submit(
        data,
        prompt="  Portrait  ",
        negative_prompt="  blur  ",
        seed=42,
        images=[image],
        loras_strength={data.lora.id: 0.6},
    )
    assert item.user_id == data.users[0].id and item.status == GenerationStatus.QUEUED
    assert item.negative_prompt == "blur"
    assert item.credits_spent == 1
    assert (
        item.runpod_endpoint_id == "endpoint-original"
        and item.runpod_job_id.startswith("job-")
    )
    assert item.seed == 42 and item.uploaded_images == 1
    data.runner.run.assert_awaited_once_with(
        [image],
        42,
        "Qwen Image 2.1",
        "Portrait",
        loras_strength={"style.safetensors": 0.6},
        negative_prompt="blur",
        size=(1024, 1024),
        endpoint_id="endpoint-original",
    )
    data.runner.endpoint_for.assert_called_once_with("Qwen Image 2.1")
    async with db_session.session_scope() as session:
        row = await GenerationRepository(DatabaseManager(session)).get_for_polling(
            item.id
        )
        assert row.runpod_job_id == item.runpod_job_id
        assert row.loras_strength == {str(data.lora.id): 0.6}


async def test_insufficient_credits_blocks_generation(data):
    async with db_session.session_scope() as session:
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == data.users[0].id)
        )
        wallet.credits = 0
    with pytest.raises(InsufficientCreditsError):
        await submit(data)
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


async def test_failed_submission_rolls_back_the_charge(data):
    data.runner.run = AsyncMock(side_effect=RunPodRequestError("provider down"))
    with pytest.raises(RunPodRequestError):
        await submit(data)
    async with db_session.session_scope() as session:
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == data.users[0].id)
        )
        assert wallet.credits == 20
        assert (
            await session.scalar(select(func.count()).select_from(TransactionModel))
            == 0
        )
    assert await count_generations() == 0


async def test_generation_charge_is_a_spend_transaction(data):
    item = await submit(data)
    async with db_session.session_scope() as session:
        transaction = await session.scalar(
            select(TransactionModel).where(TransactionModel.generation_id == item.id)
        )
        assert transaction.type == TransactionType.SPEND
        assert transaction.amount == -1
        assert transaction.balance_before == 20
        assert transaction.balance_after == 19
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == data.users[0].id)
        )
        assert wallet.credits == 19


async def test_workflow_generation_credits_control_the_charge(data):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.generation_credits = 3
    item = await submit(data)
    assert item.credits_spent == 3
    async with db_session.session_scope() as session:
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == data.users[0].id)
        )
        assert wallet.credits == 17
        transaction = await session.scalar(
            select(TransactionModel).where(TransactionModel.generation_id == item.id)
        )
        assert transaction.amount == -3


async def test_multiple_reference_images_are_forwarded_to_the_provider(data):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.name = "Qwen Image 2.1"
    images = [
        base64.b64encode(b"first").decode(),
        base64.b64encode(b"second").decode(),
        base64.b64encode(b"third").decode(),
    ]
    item = await submit(data, images=images)

    assert item.uploaded_images == 3
    assert data.runner.run.await_args.args[0] == images


async def test_reference_images_follow_the_node_limit(data):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.name = "Qwen Image 2.1"
    sixteen = [
        base64.b64encode(f"reference-{index}".encode()).decode() for index in range(16)
    ]
    item = await submit(data, images=sixteen)
    assert item.uploaded_images == 16

    data.runner.run.reset_mock()
    with pytest.raises(TooManyReferenceImagesError):
        await submit(data, images=[*sixteen, base64.b64encode(b"extra").decode()])
    data.runner.run.assert_not_awaited()


@pytest.mark.parametrize("name", ["Krea 2", "Qwen Image 2", "Qwen Image 2.1 Turbo"])
async def test_reference_images_rejected_for_other_models(data, name):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.name = name
    with pytest.raises(UnsupportedReferenceImagesError):
        await submit(data, images=[base64.b64encode(b"reference").decode()])
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


async def test_default_seed_and_explicit_empty_loras(data):
    item = await submit(data, loras_strength={})
    assert 0 <= item.seed <= 2**63 - 1
    assert data.runner.run.call_args.kwargs["loras_strength"] == {}
    assert item.loras_strength == {}


async def test_workflow_name_selects_its_own_endpoint(data):
    data.runner.endpoint_for = Mock(side_effect=lambda name: f"ep-{name}")
    item = await submit(data)
    assert item.runpod_endpoint_id == "ep-portrait"
    data.runner.endpoint_for.assert_called_once_with("portrait")
    assert data.runner.run.call_args.kwargs["endpoint_id"] == "ep-portrait"


async def test_real_runpod_client_receives_comfyui_workflow_and_named_lora(
    data, tmp_path, monkeypatch
):
    monkeypatch.setattr(workflow_module, "WORKFLOWS_DIR", tmp_path)
    (tmp_path / "portrait.json").write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "Custom",
                    "inputs": {"seed": "{{seed}}", "text": "{{prompt}}"},
                },
                "2": {
                    "class_type": "LoraLoaderModelOnly",
                    "inputs": {"lora_name": "style.safetensors", "strength_model": 1},
                },
            }
        )
    )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={"id": "actual-client-job", "status": "IN_QUEUE"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        runpod = RunPodClient(
            RunPodSettings(RUNPOD_API_KEY="test", RUNPOD_ENDPOINT_ID="endpoint-real"),
            client,
        )
        async with db_session.session_scope() as session:
            item = await data.service(session, runpod=runpod).create_generation(
                data.users[0].id,
                workflow_id=data.workflow.id,
                prompt="Portrait",
                seed=7,
                loras_strength={data.lora.id: 0.25},
            )
    assert (
        item.runpod_job_id == "actual-client-job"
        and item.runpod_endpoint_id == "endpoint-real"
    )
    graph = json.loads(requests[0].content)["input"]["workflow"]
    assert graph["1"]["inputs"] == {"seed": 7, "text": "Portrait"}
    assert graph["2"]["inputs"]["lora_name"] == "style.safetensors"
    assert graph["2"]["inputs"]["strength_model"] == 0.25


@pytest.mark.parametrize(
    "values",
    [
        {"prompt": " "},
        {"seed": True},
        {"seed": -1},
        {"loras_strength": {uuid7(): float("nan")}},
    ],
)
async def test_invalid_input_does_not_submit_or_persist(data, values):
    with pytest.raises(ValidationError):
        await submit(data, **values)
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


@pytest.mark.parametrize("images", ["base64", ["not base64"], [""], [1], ["é"]])
async def test_invalid_images_rejected_before_submission(data, images):
    with pytest.raises(InvalidGenerationImagesError):
        await submit(data, images=images)
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


@pytest.mark.parametrize("strengths", [[], {"not-a-uuid": 1}, {uuid7(): True}])
async def test_invalid_lora_mapping_rejected(data, strengths):
    with pytest.raises(ValidationError):
        await submit(data, loras_strength=strengths)
    data.runner.run.assert_not_awaited()


async def test_unknown_workflow_and_unavailable_lora_are_rejected(data):
    with pytest.raises(WorkflowNotFoundError):
        await submit(data, workflow_id=uuid7())
    with pytest.raises(LoraNotInWorkflowError):
        await submit(data, loras_strength={data.other.id: 1})
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


async def test_inactive_workflow_cannot_be_used(data):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, data.workflow.id)
        workflow.is_active = False
    with pytest.raises(WorkflowNotFoundError):
        await submit(data)
    assert await count_generations() == 0
    data.runner.run.assert_not_awaited()


async def test_user_can_only_read_and_delete_owned_generations(data):
    own = await pending(data)
    other = await pending(data, user=1)
    async with db_session.session_scope() as session:
        service = data.service(session)
        assert [
            item.id for item in await service.get_user_generations(data.users[0].id)
        ] == [own.id]
        assert (
            await service.get_user_generation(data.users[0].id, own.id)
        ).id == own.id
        with pytest.raises(GenerationNotFoundError):
            await service.get_user_generation(data.users[0].id, other.id)
        with pytest.raises(GenerationNotFoundError):
            await service.delete_user_generation(data.users[0].id, other.id)
        assert await service.delete_user_generation(data.users[0].id, own.id)
    assert await count_generations() == 1
    data.runner.cancel.assert_not_awaited()


async def test_user_list_pagination(data):
    items = [await pending(data) for _ in range(3)]
    await pending(data, user=1)
    async with db_session.session_scope() as session:
        service = data.service(session)
        first = await service.get_user_generations(data.users[0].id, limit=2)
        second = await service.get_user_generations(data.users[0].id, limit=2, offset=2)
        assert len(first) == 2 and len(second) == 1
        assert {item.id for item in first + second} == {item.id for item in items}


@pytest.mark.parametrize(
    "values", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": True}]
)
async def test_invalid_pagination_rejected(data, values):
    async with db_session.session_scope() as session:
        service = data.service(session)
        with pytest.raises(ValidationError):
            await service.get_all(**values)
        with pytest.raises(ValidationError):
            await service.get_user_generations(data.users[0].id, **values)


async def test_blocked_and_missing_users_cannot_create(data):
    with pytest.raises(UserBlockedError):
        await submit(data, user=2)
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidCredentialsError):
            await data.service(session).create_generation(
                uuid7(), workflow_id=data.workflow.id, prompt="Test"
            )
    data.runner.run.assert_not_awaited()


async def test_delete_active_generation_cancels_original_endpoint(data):
    item = await submit(data)
    data.runner.endpoint_for.return_value = "changed-endpoint"
    async with db_session.session_scope() as session:
        assert await data.service(session).delete_user_generation(
            data.users[0].id, item.id
        )
    data.runner.cancel.assert_awaited_once_with(
        item.runpod_job_id, endpoint_id="endpoint-original"
    )
    assert await count_generations() == 0


@pytest.mark.parametrize(
    "failure", [RunPodRequestError("offline"), GenerationStatus.PROCESSING]
)
async def test_delete_keeps_active_row_when_cancellation_fails(data, failure):
    item = await submit(data)
    if isinstance(failure, Exception):
        data.runner.cancel.side_effect = failure
        expected = RunPodRequestError
    else:
        data.runner.cancel.return_value = failure
        expected = InvalidGenerationStateError
    with pytest.raises(expected):
        async with db_session.session_scope() as session:
            await data.service(session).delete_user_generation(
                data.users[0].id, item.id
            )
    assert await count_generations() == 1


async def test_delete_terminal_generation_preserves_credit_history(data):
    item = await pending(data, status=GenerationStatus.COMPLETED, credits_spent=2)
    async with db_session.session_scope() as session:
        assert (
            await session.scalar(select(func.count()).select_from(GenerationModel)) == 1
        )
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == data.users[0].id)
        )
        wallet.credits = 18
        session.add(
            TransactionModel(
                wallet=wallet,
                generation_id=item.id,
                type=TransactionType.SPEND,
                amount=-2,
                balance_before=20,
                balance_after=18,
                idempotency_key="generation-spend",
            )
        )
    async with db_session.session_scope() as session:
        await data.service(session).delete_user_generation(data.users[0].id, item.id)
    async with db_session.session_scope() as session:
        ledger = (await session.scalars(select(TransactionModel))).one()
        assert ledger.generation_id is None and ledger.amount == -2
        assert (
            await session.scalar(
                select(WalletModel.credits).where(
                    WalletModel.user_id == data.users[0].id
                )
            )
            == 18
        )
    data.runner.cancel.assert_not_awaited()


async def test_provider_failure_rolls_back_pending_record_without_retry(data):
    data.runner.run.side_effect = RunPodRequestError("offline")
    with pytest.raises(RunPodRequestError):
        await submit(data)
    assert await count_generations() == 0
    data.runner.run.assert_awaited_once()


@pytest.mark.parametrize("cancel_fails", [False, True])
async def test_failed_job_persistence_cancels_submission_and_preserves_error(
    data, cancel_fails
):
    if cancel_fails:
        data.runner.cancel.side_effect = RunPodRequestError("cannot cancel")
    with pytest.raises(RuntimeError, match="cannot persist"):
        async with db_session.session_scope() as session:
            service = data.service(session)
            service._generations.update_generation = AsyncMock(
                side_effect=RuntimeError("cannot persist")
            )
            await service.create_generation(
                data.users[0].id, workflow_id=data.workflow.id, prompt="Portrait"
            )
    data.runner.cancel.assert_awaited_once()
    assert data.runner.cancel.call_args.kwargs["endpoint_id"] == "endpoint-original"
    assert await count_generations() == 0


async def test_task_cancellation_after_submission_cancels_runpod(data):
    with pytest.raises(asyncio.CancelledError):
        async with db_session.session_scope() as session:
            service = data.service(session)
            service._generations.update_generation = AsyncMock(
                side_effect=asyncio.CancelledError()
            )
            await service.create_generation(
                data.users[0].id, workflow_id=data.workflow.id, prompt="Portrait"
            )
    data.runner.cancel.assert_awaited_once()
    assert await count_generations() == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", uuid7()),
        ("user_id", uuid7()),
        ("created_at", datetime.now(UTC)),
        ("unknown", 1),
    ],
)
async def test_update_rejects_read_only_and_unknown_fields(data, field, value):
    item = await pending(data)
    async with db_session.session_scope() as session:
        with pytest.raises(InvalidRepositoryFieldError):
            await data.service(session).update(item.id, {field: value})


async def test_submitted_inputs_are_immutable_but_status_can_be_updated(data):
    item = await submit(data)
    async with db_session.session_scope() as session:
        service = data.service(session)
        with pytest.raises(InvalidGenerationStateError):
            await service.update(item.id, {"prompt": "Changed"})
        saved = await service.update(
            item.id,
            {"status": GenerationStatus.COMPLETED, "completed_at": datetime.now(UTC)},
        )
        assert saved.status == GenerationStatus.COMPLETED and saved.prompt == "Portrait"


async def test_missing_generation_raises_not_found(data):
    async with db_session.session_scope() as session:
        service = data.service(session)
        with pytest.raises(GenerationNotFoundError):
            await service.get(uuid7())
        with pytest.raises(GenerationNotFoundError):
            await service.update(uuid7(), {"prompt": "new"})


@pytest.mark.parametrize("current_credits", [0, 10, 30])
async def test_generation_uses_locked_balance_after_concurrent_change(
    data, current_credits
):
    # Simulate a cached balance read before another transaction commits.
    async with db_session.session_scope() as session:
        repository = WalletRepository(DatabaseManager(session))
        stale = await repository.get_by_user(data.users[0].id)
        row = await session.get(WalletModel, stale.id)
        row.credits = current_credits
    async with db_session.session_scope() as session:
        service = data.service(session)
        service._wallets.get_by_user = AsyncMock(return_value=stale)
        if current_credits == 0:
            with pytest.raises(InsufficientCreditsError):
                await service.create_generation(
                    data.users[0].id, workflow_id=data.workflow.id, prompt="Portrait"
                )
            data.runner.run.assert_not_awaited()
        else:
            await service.create_generation(
                data.users[0].id, workflow_id=data.workflow.id, prompt="Portrait"
            )
    async with db_session.session_scope() as session:
        wallet = await session.get(WalletModel, stale.id)
        assert wallet.credits == max(0, current_credits - 1)
        ledger = (await session.scalars(select(TransactionModel))).all()
        assert len(ledger) == (1 if current_credits else 0)
        if ledger:
            assert ledger[0].balance_before == current_credits
