from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from adapters.api.dependencies.images import get_lora_preview_store
from adapters.api.dependencies.settings import get_app_settings
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.admin import router as admin_router
from adapters.api.routes.admin_catalog import router as catalog_router
from adapters.api.routes.lora import router as lora_router
from adapters.database import DatabaseSession, db_session
from adapters.database.models import (
    AdminModel,
    Base,
    GenerationModel,
    GenerationPresetModel,
    LoraModel,
    UserModel,
    WorkflowModel,
)
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.settings import ApiSettings, DatabaseSettings, JwtTokenSettings, Settings

PASSWORD = "catalog admin password"


class FakeLoraPreviewStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put_lora_preview(self, preview_id, data):
        self.objects[str(preview_id)] = data
        return True

    async def get_lora_preview(self, preview_id):
        data = self.objects.get(str(preview_id))
        return (data, "image/png") if data is not None else None

    async def delete_lora_preview(self, preview_id):
        self.objects.pop(str(preview_id), None)


@pytest.fixture
async def catalog(tmp_path, monkeypatch):
    settings = Settings(
        DATABASE_SETTINGS=DatabaseSettings(
            POSTGRES_HOST="localhost",
            POSTGRES_DB_PORT=5432,
            POSTGRES_USER="test",
            POSTGRES_PASSWORD="test",
            POSTGRES_DB="test",
        ),
        API_SETTINGS=ApiSettings(CSRF_ENABLED=False, SECURITY_REDIS_ENABLED=False),
        JWT_TOKEN_SETTINGS=JwtTokenSettings(
            JWT_ALGORITHM="HS256",
            ACCESS_KEY_TIMEDELTA_MINUTES=30,
            REFRESH_KEY_TIMEDELTA_MINUTES=120,
            SECRET_KEY_ACCESS="catalog-access-" + "a" * 32,
            SECRET_KEY_REFRESH="catalog-refresh-" + "b" * 32,
        ),
    )
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        admin = AdminModel(
            username="owner",
            _hashed_password=Argon2PasswordHasher().hash_password(PASSWORD),
            is_owner=True,
        )
        user = UserModel(first_name="User")
        live = WorkflowModel(name="krea2_turbo_all_api", generation_credits=2)
        spare = WorkflowModel(name="unused_model", generation_credits=1)
        lora = LoraModel(name="style.safetensors", description="Style LoRA", is_nsfw=True)
        session.add_all([admin, user, live, spare, lora])
        await session.flush()
        session.add(GenerationModel(user_id=user.id, workflow_id=live.id, prompt="x"))
        session.add(
            GenerationPresetModel(
                user_id=user.id,
                workflow_id=live.id,
                name="preset",
                prompt="x",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
        ids = {"live": live.id, "spare": spare.id, "lora": lora.id}

    monkeypatch.setattr(db_session, "_async_session", database.session_factory)
    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(admin_router)
    app.include_router(catalog_router)
    app.include_router(lora_router)
    store = FakeLoraPreviewStore()
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_lora_preview_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.example"
        ) as client:
            response = await client.post(
                "/admins/auth/login",
                json={"username": "owner", "password": PASSWORD},
            )
            assert response.status_code == 200, response.text
            token = response.cookies[settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE]
            client.cookies.set(
                settings.API_SETTINGS.ADMIN_ACCESS_TOKEN_COOKIE, token
            )
            yield {"client": client, "ids": ids, "settings": settings, "store": store}
    finally:
        await database.dispose()


async def test_workflows_can_be_created_updated_and_deactivated(catalog):
    client = catalog["client"]

    created = await client.post(
        "/admins/workflows",
        json={
            "name": "new_model_api",
            "description": "New model",
            "generation_credits": 3,
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "new_model_api"
    assert body["generation_credits"] == 3
    assert body["is_active"] is True

    patched = await client.patch(
        f"/admins/workflows/{body['id']}",
        json={"description": "Retired", "is_active": False, "generation_credits": 0},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["is_active"] is False
    assert patched.json()["description"] == "Retired"
    assert (await client.patch(f"/admins/workflows/{body['id']}", json={})).status_code == 422


async def test_workflow_names_are_unique_and_safe(catalog):
    client = catalog["client"]

    duplicate = await client.post(
        "/admins/workflows", json={"name": "krea2_turbo_all_api"}
    )
    assert duplicate.status_code == 409
    unsafe = await client.post(
        "/admins/workflows", json={"name": "../escape"}
    )
    assert unsafe.status_code == 422


async def test_workflow_loras_can_be_replaced_with_strengths(catalog):
    client = catalog["client"]
    live = catalog["ids"]["live"]
    lora = catalog["ids"]["lora"]

    response = await client.put(
        f"/admins/workflows/{live}/loras",
        json={"items": [{"lora_id": str(lora), "recommended_strength": 0.85}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body["loras"]] == [str(lora)]
    assert body["loras"][0]["is_nsfw"] is True
    assert body["recommended_strengths"][str(lora)] == 0.85

    for strength in (1.5, 2):
        stronger = await client.put(
            f"/admins/workflows/{live}/loras",
            json={
                "items": [
                    {"lora_id": str(lora), "recommended_strength": strength}
                ]
            },
        )
        assert stronger.status_code == 200, stronger.text
        assert stronger.json()["recommended_strengths"][str(lora)] == strength

    too_strong = await client.put(
        f"/admins/workflows/{live}/loras",
        json={"items": [{"lora_id": str(lora), "recommended_strength": 2.5}]},
    )
    assert too_strong.status_code == 422

    cleared = await client.put(
        f"/admins/workflows/{live}/loras", json={"items": []}
    )
    assert cleared.status_code == 200
    assert cleared.json()["loras"] == []

    missing = await client.put(
        f"/admins/workflows/{live}/loras",
        json={
            "items": [
                {
                    "lora_id": "00000000-0000-0000-0000-000000000000",
                    "recommended_strength": 0.5,
                }
            ]
        },
    )
    assert missing.status_code == 404


async def test_workflow_with_history_cannot_be_deleted(catalog):
    client = catalog["client"]

    blocked = await client.delete(f"/admins/workflows/{catalog['ids']['live']}")
    assert blocked.status_code == 409

    removed = await client.delete(f"/admins/workflows/{catalog['ids']['spare']}")
    assert removed.status_code == 204
    assert (await client.delete(f"/admins/workflows/{catalog['ids']['spare']}")).status_code == 404


async def test_loras_are_managed_from_the_admin_panel(catalog):
    client = catalog["client"]

    listed = await client.get("/admins/loras?query=style")
    assert listed.status_code == 200
    page = listed.json()
    assert page["total"] == 1
    assert page["items"][0]["name"] == "style.safetensors"
    assert page["items"][0]["is_nsfw"] is True

    created = await client.post(
        "/admins/loras",
        json={
            "name": "fresh.safetensors",
            "description": "Fresh LoRA",
            "preview_urls": ["https://cdn.example.com/preview.png"],
            "is_nsfw": True,
        },
    )
    assert created.status_code == 201, created.text
    lora_id = created.json()["id"]
    assert created.json()["workflow_count"] == 0
    assert created.json()["is_nsfw"] is True

    assert (
        await client.post("/admins/loras", json={"name": "fresh.safetensors"})
    ).status_code == 409

    patched = await client.patch(
        f"/admins/loras/{lora_id}",
        json={"description": "Renamed LoRA", "preview_urls": [], "is_nsfw": False},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Renamed LoRA"
    assert patched.json()["preview_urls"] == []
    assert patched.json()["is_nsfw"] is False

    assert (
        await client.patch(
            f"/admins/loras/{lora_id}",
            json={"preview_urls": ["javascript:alert(1)"]},
        )
    ).status_code == 422


async def test_lora_previews_can_be_uploaded_and_served(catalog):
    client = catalog["client"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    uploaded = await client.post(
        "/admins/loras/previews",
        files={"file": ("preview.png", png, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    url = uploaded.json()["url"]
    assert url.startswith("/api/loras/previews/")

    served = await client.get(url.removeprefix("/api"))
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == png

    created = await client.post(
        "/admins/loras",
        json={
            "name": "minio-preview.safetensors",
            "description": "MinIO preview",
            "preview_urls": [url],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["preview_urls"] == [url]


async def test_linked_loras_cannot_be_deleted(catalog):
    client = catalog["client"]
    live = catalog["ids"]["live"]
    lora = catalog["ids"]["lora"]

    await client.put(
        f"/admins/workflows/{live}/loras",
        json={"items": [{"lora_id": str(lora), "recommended_strength": 0.7}]},
    )
    blocked = await client.delete(f"/admins/loras/{lora}")
    assert blocked.status_code == 409

    await client.put(f"/admins/workflows/{live}/loras", json={"items": []})
    assert (await client.delete(f"/admins/loras/{lora}")).status_code == 204


async def test_catalog_admin_routes_require_an_admin_session(catalog):
    client = catalog["client"]
    client.cookies.clear()
    assert (await client.get("/admins/loras")).status_code == 401
    assert (await client.post("/admins/workflows", json={"name": "x"})).status_code == 401
