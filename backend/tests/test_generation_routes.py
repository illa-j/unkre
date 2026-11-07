import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid7

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.api.dependencies.generation import get_runpod_client
from adapters.api.dependencies.images import get_image_store
from adapters.api.dependencies.settings import get_app_settings
from adapters.api.guard import configure_guard
from adapters.api.main import app as main_app
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.generation import router
from adapters.api.routes.workflow import router as workflow_router
from adapters.database import db_session
from adapters.database.models import (
    Base,
    GenerationModel,
    LoraModel,
    UserModel,
    WalletModel,
    WorkflowModel,
    workflow_loras,
)
from adapters.runpod import RunPodClient
from adapters.runpod import workflow as workflow_module
from adapters.security.tokens import JwtProvider
from adapters.settings import RunPodSettings, Settings
from domain.enums import GenerationStatus


@pytest.fixture
async def api(tmp_path, monkeypatch):
    settings = Settings(
        RUNPOD_SETTINGS=RunPodSettings(
            RUNPOD_API_KEY="test-key", RUNPOD_ENDPOINT_ID="endpoint-original"
        )
    )
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'generations-api.db'}",
        connect_args={"autocommit": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "_async_session", factory)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db_session.session_scope() as session:
        lora = LoraModel(name="style.safetensors")
        workflow = WorkflowModel(name="portrait", loras=[lora])
        users = [
            UserModel(first_name="First"),
            UserModel(first_name="Second"),
            UserModel(first_name="Blocked", is_blocked=True),
        ]
        session.add_all(
            [workflow, *[WalletModel(user=user, credits=20) for user in users]]
        )
        await session.flush()
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
    state = SimpleNamespace(
        settings=settings,
        workflow=workflow,
        lora=lora,
        users=users,
        requests=[],
        provider_status=200,
        run_payload=None,
        cancel_status="CANCELLED",
        status_payload={"status": "COMPLETED", "output": {"images": []}},
        tokens=JwtProvider(settings.JWT_TOKEN_SETTINGS),
    )

    def runpod(request):
        state.requests.append(request)
        payload = (
            {"status": state.cancel_status}
            if "/cancel/" in request.url.path
            else state.status_payload
            if "/status/" in request.url.path
            else state.run_payload
            if state.run_payload is not None
            else {"id": "job-" + str(uuid7()), "status": "IN_QUEUE"}
        )
        return httpx.Response(state.provider_status, json=payload)

    app = FastAPI()
    state.app = app
    app.middleware("http")(authentication_middleware)
    app.include_router(router)
    app.include_router(workflow_router)
    app.dependency_overrides[get_app_settings] = lambda: settings
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(runpod)) as http:
            runpod_client = RunPodClient(settings.RUNPOD_SETTINGS, http)
            app.dependency_overrides[get_runpod_client] = lambda: runpod_client
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="https://api.example",
            ) as client:
                state.client = client
                login(state)
                yield state
    finally:
        await engine.dispose()


def login(api, user=0, *, scope="user"):
    api.client.cookies.clear()
    api.client.cookies.set(
        api.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE,
        api.tokens.create_access_token(
            {"sub": str(api.users[user].id), "scope": scope}
        ),
    )


async def create(api, **overrides):
    data = {"workflow_id": str(api.workflow.id), "prompt": "Portrait"}
    data.update(overrides)
    return await api.client.post("/generations", json=data)


async def persist(api, *, user=0, **overrides):
    async with db_session.session_scope() as session:
        generation = GenerationModel(
            user_id=api.users[user].id,
            workflow_id=api.workflow.id,
            prompt="Saved portrait",
            **overrides,
        )
        session.add(generation)
        await session.flush()
        return generation.id


async def count_generations():
    async with db_session.session_scope() as session:
        return await session.scalar(select(func.count()).select_from(GenerationModel))


def test_main_registers_user_generation_routes():
    paths = main_app.openapi()["paths"]
    assert {"get", "post"} <= paths["/generations"].keys()
    assert {"get", "delete"} <= paths["/generations/{generation_id}"].keys()
    assert "patch" not in paths["/generations/{generation_id}"]


async def test_create_immediately_submits_workflow_and_returns_saved_generation(
    api, tmp_path
):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, api.workflow.id)
        workflow.name = "Qwen Image 2.1"
    (tmp_path / "Qwen Image 2.1.json").write_text(
        (tmp_path / "portrait.json").read_text()
    )
    image = base64.b64encode(b"reference-image").decode()
    response = await create(
        api,
        prompt="  Portrait  ",
        negative_prompt="  blur  ",
        images=[image],
        loras_strength={str(api.lora.id): 0.25},
        seed=42,
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["prompt"] == "Portrait"
    assert result["negative_prompt"] == "blur"
    assert result["seed"] == 42 and result["uploaded_images"] == 1
    assert result["loras_strength"] == {str(api.lora.id): 0.25}
    assert result["status"] == "queued" and result["created_at"] is not None
    assert not {"user_id", "runpod_job_id", "runpod_endpoint_id"} & result.keys()
    assert response.headers["Cache-Control"] == "no-store"
    assert len(api.requests) == 1
    submitted = api.requests[0]
    assert str(submitted.url) == "https://api.runpod.ai/v2/endpoint-original/run"
    graph = json.loads(submitted.content)["input"]["workflow"]
    assert graph["1"]["inputs"] == {"seed": 42, "text": "Portrait"}
    assert graph["2"]["inputs"]["lora_name"] == "style.safetensors"
    assert graph["2"]["inputs"]["strength_model"] == 0.25
    async with db_session.session_scope() as session:
        row = await session.get(GenerationModel, UUID(result["id"]))
        assert row.user_id == api.users[0].id
        assert row.negative_prompt == "blur"
        assert row.runpod_job_id is not None
        assert row.runpod_endpoint_id == "endpoint-original"
    fetched = await api.client.get(f"/generations/{result['id']}")
    assert fetched.status_code == 200 and fetched.json() == result


async def test_reference_images_for_other_models_return_422_without_submission(api):
    response = await create(api, images=[base64.b64encode(b"reference").decode()])
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Reference images are only supported by Qwen Image 2.1."
    )
    assert await count_generations() == 0
    assert not api.requests


async def test_list_is_owned_paginated_and_ordered_newest_first(api):
    own = [await persist(api) for _ in range(3)]
    await persist(api, user=1)
    first = await api.client.get("/generations?limit=2")
    second = await api.client.get("/generations?limit=2&offset=2")
    assert first.status_code == second.status_code == 200
    assert [item["id"] for item in first.json() + second.json()] == [
        str(ident) for ident in reversed(own)
    ]
    assert first.headers["Cache-Control"] == "no-store"
    assert not api.requests


@pytest.mark.parametrize("method", ["get", "delete"])
async def test_other_users_generation_is_indistinguishable_from_missing(api, method):
    other = await persist(api, user=1)
    request = getattr(api.client, method)
    response = await request(f"/generations/{other}")
    missing = await request(f"/generations/{uuid7()}")
    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json() == {"detail": "Generation not found"}
    assert await count_generations() == 1
    assert not api.requests


async def test_delete_cancels_active_job_on_original_endpoint(api):
    response = await create(api)
    assert response.status_code == 201
    ident = response.json()["id"]
    api.settings.RUNPOD_SETTINGS.RUNPOD_ENDPOINT_ID = "changed-endpoint"
    deleted = await api.client.delete(f"/generations/{ident}")
    assert deleted.status_code == 204 and deleted.content == b""
    assert "/endpoint-original/cancel/" in api.requests[-1].url.path
    assert await count_generations() == 0


@pytest.mark.parametrize("cancel_status", ["IN_QUEUE", "IN_PROGRESS"])
async def test_delete_keeps_row_if_runpod_job_is_still_active(api, cancel_status):
    response = await create(api)
    api.cancel_status = cancel_status
    deleted = await api.client.delete(f"/generations/{response.json()['id']}")
    assert deleted.status_code == 409
    assert await count_generations() == 1


async def test_delete_provider_failure_keeps_row(api):
    response = await create(api)
    api.provider_status = 503
    deleted = await api.client.delete(f"/generations/{response.json()['id']}")
    assert deleted.status_code == 503
    assert deleted.json() == {"detail": "Generation provider is unavailable"}
    assert await count_generations() == 1


async def test_read_and_terminal_delete_do_not_require_runpod_configuration(api):
    ident = await persist(
        api, status=GenerationStatus.COMPLETED, runpod_job_id="old-job"
    )
    api.app.dependency_overrides.pop(get_runpod_client)
    api.settings.RUNPOD_SETTINGS.RUNPOD_API_KEY = ""
    api.settings.RUNPOD_SETTINGS.RUNPOD_ENDPOINT_ID = ""
    assert (await api.client.get("/generations")).status_code == 200
    assert (await api.client.get(f"/generations/{ident}")).status_code == 200
    assert (await api.client.delete(f"/generations/{ident}")).status_code == 204
    assert not api.requests


async def test_missing_runpod_config_returns_503_without_creating_generation(api):
    api.settings.RUNPOD_SETTINGS.RUNPOD_API_KEY = ""
    api.settings.RUNPOD_SETTINGS.RUNPOD_ENDPOINT_ID = ""
    response = await create(api)
    assert response.status_code == 503
    assert await count_generations() == 0
    assert not api.requests


@pytest.mark.parametrize("failure", ["http", "invalid-response"])
async def test_failed_submission_rolls_back_without_automatic_retry(api, failure):
    if failure == "http":
        api.provider_status = 500
    else:
        api.run_payload = {"status": "IN_QUEUE"}
    response = await create(api)
    assert response.status_code == 503
    assert response.json() == {"detail": "Generation provider is unavailable"}
    assert await count_generations() == 0
    assert len(api.requests) == 1


async def test_lora_strength_allows_values_up_to_two(api):
    for strength in (1.5, 2):
        response = await create(api, loras_strength={str(api.lora.id): strength})
        assert response.status_code == 201, response.text
        assert response.json()["loras_strength"] == {str(api.lora.id): strength}
        graph = json.loads(api.requests[-1].content)["input"]["workflow"]
        assert graph["2"]["inputs"]["strength_model"] == strength

    for strength in (2.5, 3):
        rejected = await create(api, loras_strength={str(api.lora.id): strength})
        assert rejected.status_code == 422


async def test_missing_workflow_is_404_and_unavailable_lora_is_422(api):
    missing = await create(api, workflow_id=str(uuid7()))
    assert missing.status_code == 404
    invalid_lora = await create(api, loras_strength={str(uuid7()): 1})
    assert invalid_lora.status_code == 422
    assert await count_generations() == 0
    assert not api.requests


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt": "   "},
        {"prompt": 123},
        {"prompt": "x" * 8193},
        {"workflow_id": "not-a-uuid"},
        {"seed": -1},
        {"seed": 2**63},
        {"seed": True},
        {"seed": "42"},
        {"images": "base64"},
        {"images": [""]},
        {"images": ["not-base64!"]},
        {"loras_strength": {"not-a-uuid": 1}},
        {"loras_strength": {"01900000-0000-7000-8000-000000000000": True}},
        {"loras_strength": {"01900000-0000-7000-8000-000000000000": "0.5"}},
        {"user_id": "01900000-0000-7000-8000-000000000000"},
        {"status": "completed"},
        {"credits_spent": 0},
        {"runpod_job_id": "injected"},
        {"runpod_endpoint_id": "injected"},
        {"uploaded_images": 1},
    ],
)
async def test_invalid_or_server_managed_fields_are_rejected_before_submission(
    api, changes
):
    response = await create(api, **changes)
    assert response.status_code == 422, response.text
    assert await count_generations() == 0
    assert not api.requests


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=abc"])
async def test_invalid_pagination_is_422(api, query):
    response = await api.client.get(f"/generations?{query}")
    assert response.status_code == 422


@pytest.mark.parametrize("path", ["not-a-uuid", "1"])
async def test_invalid_generation_id_is_422(api, path):
    response = await api.client.get(f"/generations/{path}")
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["get", "post", "delete"])
async def test_routes_require_client_cookie_even_with_bearer_or_admin_cookie(
    api, method
):
    token = api.client.cookies[api.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE]
    api.client.cookies.clear()
    api.client.cookies.set(api.settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE, token)
    path = "/generations" if method != "delete" else f"/generations/{uuid7()}"
    response = await api.client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
        json={"workflow_id": str(api.workflow.id), "prompt": "Portrait"}
        if method == "post"
        else None,
    )
    assert response.status_code == 401
    assert not api.requests


async def test_blocked_user_is_forbidden(api):
    login(api, user=2)
    assert (await create(api)).status_code == 403
    assert (await api.client.get("/generations")).status_code == 403
    assert not api.requests


async def test_guard_requires_csrf_for_create_and_delete(api):
    api.settings.API_SETTINGS.SECURITY_REDIS_ENABLED = False
    configure_guard(api.app, api.settings)
    assert (await create(api)).status_code == 403
    bootstrap = await api.client.get("/generations")
    assert bootstrap.status_code == 200
    response = await api.client.post(
        "/generations",
        json={"workflow_id": str(api.workflow.id), "prompt": "Portrait"},
        headers={"X-CSRF-Token": bootstrap.headers["X-CSRF-Token"]},
    )
    assert response.status_code == 201, response.text
    path = f"/generations/{response.json()['id']}"
    assert (await api.client.delete(path)).status_code == 403
    deleted = await api.client.delete(
        path, headers={"X-CSRF-Token": bootstrap.headers["X-CSRF-Token"]}
    )
    assert deleted.status_code == 204


async def test_inactive_workflows_are_hidden_from_the_catalog(api):
    async with db_session.session_scope() as session:
        workflow = await session.get(WorkflowModel, api.workflow.id)
        workflow.is_active = False

    response = await api.client.get("/workflows")

    assert response.status_code == 200
    assert response.json() == []


async def test_runpod_dependency_closes_owned_http_client():
    dependency = get_runpod_client(Settings())
    client = await anext(dependency)
    assert not client._client.is_closed
    await dependency.aclose()
    assert client._client.is_closed


async def test_workflow_catalog_returns_database_loras_and_requires_user(api):
    async with db_session.session_scope() as session:
        await session.execute(
            update(workflow_loras)
            .where(workflow_loras.c.workflow_id == api.workflow.id)
            .values(recommended_strength=0.85)
        )
    response = await api.client.get("/workflows")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(api.workflow.id),
            "name": "portrait",
            "description": None,
            "generation_credits": 1,
            "loras": [
                {
                    "id": str(api.lora.id),
                    "name": "style.safetensors",
                    "description": None,
                    "preview_urls": [],
                    "is_nsfw": False,
                }
            ],
            "is_active": True,
            "recommended_strengths": {str(api.lora.id): 0.85},
        }
    ]
    assert response.headers["Cache-Control"] == "no-store"
    api.client.cookies.clear()
    assert (await api.client.get("/workflows")).status_code == 401
    assert not api.requests


async def test_owned_completed_image_uses_original_endpoint(api):
    content = b"\x89PNG\r\n\x1a\n" + b"test-image"
    api.status_payload["output"]["images"] = [
        {"type": "base64", "data": base64.b64encode(content).decode()}
    ]
    ident = await persist(
        api,
        status=GenerationStatus.COMPLETED,
        runpod_job_id="job-completed",
        runpod_endpoint_id="saved-endpoint",
    )
    response = await api.client.get(f"/generations/{ident}/image")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert response.headers["Cache-Control"] == "no-store"
    assert api.requests[-1].url.path == "/v2/saved-endpoint/status/job-completed"


async def test_foreign_missing_and_pending_images_do_not_contact_runpod(api):
    foreign = await persist(
        api, user=1, status=GenerationStatus.COMPLETED, runpod_job_id="private-job"
    )
    pending = await persist(api)
    for ident in (foreign, pending, uuid7()):
        assert (await api.client.get(f"/generations/{ident}/image")).status_code == 404
    assert not api.requests


async def test_missing_output_returns_404_and_active_content_is_not_served(api):
    ident = await persist(
        api, status=GenerationStatus.COMPLETED, runpod_job_id="job-completed"
    )
    assert (await api.client.get(f"/generations/{ident}/image")).status_code == 404
    api.status_payload["output"]["images"] = [
        {
            "type": "base64",
            "data": base64.b64encode(b"<svg onload='alert(1)'/>").decode(),
        }
    ]
    response = await api.client.get(f"/generations/{ident}/image")
    assert response.status_code == 502
    assert b"<svg" not in response.content


def cache_store(*, cached: bytes | None = None):
    store = SimpleNamespace(
        get=AsyncMock(return_value=(cached, "image/png") if cached else None),
        put=AsyncMock(),
        delete=AsyncMock(return_value=True),
        close=AsyncMock(),
    )
    return store


async def test_cached_image_skips_the_provider(api):
    content = b"\x89PNG\r\n\x1a\n" + b"cached-image"
    ident = await persist(
        api,
        status=GenerationStatus.COMPLETED,
        runpod_job_id="job-completed",
        runpod_endpoint_id="saved-endpoint",
    )
    store = cache_store(cached=content)
    api.app.dependency_overrides[get_image_store] = lambda: store

    response = await api.client.get(f"/generations/{ident}/image")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert not api.requests
    store.get.assert_awaited_once_with(ident)


async def test_first_read_fills_the_temporary_cache(api):
    content = b"\x89PNG\r\n\x1a\n" + b"fresh-image"
    api.status_payload["output"]["images"] = [
        {"type": "base64", "data": base64.b64encode(content).decode()}
    ]
    ident = await persist(
        api, status=GenerationStatus.COMPLETED, runpod_job_id="job-completed"
    )
    store = cache_store()
    api.app.dependency_overrides[get_image_store] = lambda: store

    response = await api.client.get(f"/generations/{ident}/image")

    assert response.status_code == 200
    assert response.content == content
    store.put.assert_awaited_once_with(ident, content)


async def test_deleting_a_generation_clears_the_cached_image(api):
    ident = await persist(
        api, status=GenerationStatus.COMPLETED, runpod_job_id="job-completed"
    )
    store = cache_store()
    api.app.dependency_overrides[get_image_store] = lambda: store

    response = await api.client.delete(f"/generations/{ident}")

    assert response.status_code == 204
    store.delete.assert_awaited_once_with(ident)


@pytest.mark.parametrize(
    "provider_status,expected", [(404, 404), (500, 503), (401, 503)]
)
async def test_missing_provider_image_is_distinct_from_temporary_failure(
    api, provider_status, expected
):
    ident = await persist(
        api,
        status=GenerationStatus.COMPLETED,
        runpod_job_id="expired-job",
        runpod_endpoint_id="original-endpoint",
    )
    api.provider_status = provider_status
    response = await api.client.get(f"/generations/{ident}/image")
    assert response.status_code == expected
    if expected == 404:
        assert response.json() == {"detail": "Generation image is unavailable"}


@pytest.mark.parametrize("cancel_fails", [False, True])
async def test_failed_final_commit_cancels_the_accepted_job(
    api, monkeypatch, cancel_fails
):
    from sqlalchemy.ext.asyncio import AsyncSession

    original_commit = AsyncSession.commit

    async def failed_commit(session):
        if cancel_fails:
            api.provider_status = 500
        raise RuntimeError("database commit failed")

    monkeypatch.setattr(AsyncSession, "commit", failed_commit)
    response = await create(api)
    assert response.status_code == 500
    assert len(api.requests) == 2
    assert api.requests[0].url.path.endswith("/run")
    assert "/endpoint-original/cancel/" in api.requests[1].url.path
    monkeypatch.setattr(AsyncSession, "commit", original_commit)
    assert await count_generations() == 0
    async with db_session.session_scope() as session:
        wallet = await session.scalar(
            select(WalletModel).where(WalletModel.user_id == api.users[0].id)
        )
        assert wallet.credits == 20


async def test_failed_image_deletion_keeps_generation_for_retry(api):
    ident = await persist(
        api, status=GenerationStatus.COMPLETED, runpod_job_id="completed"
    )
    store = cache_store()
    store.delete.return_value = False
    api.app.dependency_overrides[get_image_store] = lambda: store
    response = await api.client.delete(f"/generations/{ident}")
    assert response.status_code == 503
    assert await count_generations() == 1
    store.delete.return_value = True
    response = await api.client.delete(f"/generations/{ident}")
    assert response.status_code == 204
    assert await count_generations() == 0
