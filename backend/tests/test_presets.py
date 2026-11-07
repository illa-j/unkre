from types import SimpleNamespace
from uuid import uuid7

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adapters.api.dependencies.images import get_preset_preview_store
from adapters.api.dependencies.user import get_current_user
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.preset import router
from adapters.database import DatabaseManager, db_session
from adapters.database.models import (
    Base,
    GenerationPresetModel,
    LoraModel,
    UserModel,
    WorkflowModel,
)
from adapters.database.repositiries import PresetRepository, WorkflowRepository
from domain.entities.user import User
from domain.exceptions.generation import (
    InvalidLoraStrengthsError,
    WorkflowNotFoundError,
)
from domain.exceptions.preset import PresetNotFoundError
from domain.services.preset import PresetService


@pytest.fixture
async def data(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'presets.db'}"
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
        workflow = WorkflowModel(name="portrait", loras=[lora])
        other = WorkflowModel(name="other")
        user = UserModel(first_name="First")
        session.add_all([workflow, other, user])
        await session.flush()

    def service(session):
        manager = DatabaseManager(session)
        return PresetService(
            PresetRepository(manager), WorkflowRepository(manager)
        )

    try:
        yield SimpleNamespace(
            engine=engine,
            workflow=workflow,
            other=other,
            lora=lora,
            user=user,
            service=service,
        )
    finally:
        await engine.dispose()


async def test_presets_are_scoped_to_the_user_and_idempotent_to_delete(data):
    async with db_session.session_scope() as session:
        preset = await data.service(session).create(
            data.user.id,
            name="  Portrait  ",
            workflow_id=data.workflow.id,
            prompt="  A portrait  ",
            description="  A focused portrait  ",
            negative_prompt="  blur  ",
            loras_strength={data.lora.id: 0.8},
            seed=42,
        )
        assert preset.name == "Portrait" and preset.prompt == "A portrait"
        assert preset.negative_prompt == "blur"
        assert preset.description == "A focused portrait"
        assert preset.loras_strength == {data.lora.id: 0.8}

    async with db_session.session_scope() as session:
        listed = await data.service(session).get_all(data.user.id)
        assert [item.id for item in listed] == [preset.id]
        assert await data.service(session).delete(data.user.id, preset.id) is True
        with pytest.raises(PresetNotFoundError):
            await data.service(session).delete(data.user.id, preset.id)

    async with db_session.session_scope() as session:
        assert await session.scalar(select(GenerationPresetModel)) is None


async def test_preset_rejects_foreign_workflow_and_lora(data):
    other_lora = LoraModel(name="other.safetensors")
    async with db_session.session_scope() as session:
        session.add(other_lora)
        await session.flush()
    async with db_session.session_scope() as session:
        with pytest.raises(WorkflowNotFoundError):
            await data.service(session).create(
                data.user.id,
                name="Missing",
                workflow_id=uuid7(),
                prompt="x",
            )
        with pytest.raises(InvalidLoraStrengthsError):
            await data.service(session).create(
                data.user.id,
                name="Wrong LoRA",
                workflow_id=data.workflow.id,
                prompt="x",
                loras_strength={other_lora.id: 0.5},
            )


async def test_preset_lora_strength_allows_values_up_to_two(data):
    async with db_session.session_scope() as session:
        for strength in (1.5, 2):
            preset = await data.service(session).create(
                data.user.id,
                name=f"Strong LoRA {strength}",
                workflow_id=data.workflow.id,
                prompt="x",
                loras_strength={data.lora.id: strength},
            )
            assert preset.loras_strength == {data.lora.id: strength}

        for strength in (2.5, 3):
            with pytest.raises(InvalidLoraStrengthsError):
                await data.service(session).create(
                    data.user.id,
                    name=f"Too strong {strength}",
                    workflow_id=data.workflow.id,
                    prompt="x",
                    loras_strength={data.lora.id: strength},
                )


async def test_preset_preview_upload_is_stored_and_served(data):
    from adapters.api.dependencies.admin import get_current_admin
    from adapters.api.routes.admin_preset import router as admin_router
    from domain.entities.admin import Admin

    class FakeStore:
        def __init__(self):
            self.objects = {}

        async def put_preset_preview(self, preview_id, data):
            self.objects[str(preview_id)] = data
            return True

        async def get_preset_preview(self, preview_id):
            value = self.objects.get(str(preview_id))
            return (value, "image/png") if value else None

        async def delete_preset_preview(self, preview_id):
            self.objects.pop(str(preview_id), None)

    store = FakeStore()
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=data.user.id, first_name="First"
    )
    app.dependency_overrides[get_current_admin] = lambda: Admin(
        username="owner", is_owner=True
    )
    app.dependency_overrides[get_preset_preview_store] = lambda: store
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        uploaded = await client.post(
            "/presets/previews",
            files={"file": ("preview.png", png, "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        body = uploaded.json()
        assert body["url"].startswith("/api/presets/previews/")
        preview_id = body["url"].rsplit("/", 1)[-1]
        assert preview_id in store.objects

        served = await client.get(body["url"].removeprefix("/api"))
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert served.content == png

        admin_upload = await client.post(
            "/admins/presets/previews",
            files={"file": ("preview.webp", b"RIFF" + b"0" * 4 + b"WEBP" + b"0" * 16, "image/webp")},
        )
        assert admin_upload.status_code == 201, admin_upload.text

        created = await client.post(
            "/presets",
            json={
                "name": "MinIO preview",
                "workflow_id": str(data.workflow.id),
                "prompt": "A",
                "preview_urls": [body["url"]],
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["preview_urls"] == [body["url"]]


async def test_preset_routes_create_list_and_delete(data):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=data.user.id, first_name="First"
    )
    payload = {
        "name": "My portrait",
        "workflow_id": str(data.workflow.id),
        "prompt": "A portrait",
        "description": "A soft portrait starter",
        "negative_prompt": "blur",
        "loras_strength": {str(data.lora.id): 0.7},
        "seed": 7,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        created = await client.post("/presets", json=payload)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["name"] == "My portrait"
        assert body["description"] == "A soft portrait starter"
        assert body["loras_strength"] == {str(data.lora.id): 0.7}
        assert body["seed"] == 7

        listed = await client.get("/presets")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [body["id"]]

        removed = await client.delete(f"/presets/{body['id']}")
        assert removed.status_code == 204
        assert (await client.get("/presets")).json() == []


async def test_preset_update_changes_only_the_given_fields(data):
    async with db_session.session_scope() as session:
        preset = await data.service(session).create(
            data.user.id,
            name="Old name",
            workflow_id=data.workflow.id,
            prompt="old prompt",
            negative_prompt="blur",
            seed=5,
            loras_strength={data.lora.id: 0.5},
        )
        updated = await data.service(session).update(
            data.user.id, preset.id, {"name": "  New name  ", "seed": None}
        )

        assert updated.name == "New name"
        assert updated.seed is None
        assert updated.prompt == "old prompt"
        assert updated.negative_prompt == "blur"
        assert updated.loras_strength == {data.lora.id: 0.5}
        assert updated.workflow_id == data.workflow.id


async def test_preset_update_can_replace_contents_and_workflow(data):
    async with db_session.session_scope() as session:
        preset = await data.service(session).create(
            data.user.id,
            name="Portrait",
            workflow_id=data.workflow.id,
            prompt="old",
            loras_strength={data.lora.id: 0.5},
        )
        updated = await data.service(session).update(
            data.user.id,
            preset.id,
            {
                "workflow_id": data.other.id,
                "prompt": "new",
                "loras_strength": None,
                "seed": 42,
            },
        )
        assert updated.workflow_id == data.other.id
        assert updated.prompt == "new"
        assert updated.loras_strength == {}
        assert updated.seed == 42

        with pytest.raises(InvalidLoraStrengthsError):
            await data.service(session).update(
                data.user.id,
                preset.id,
                {"workflow_id": data.workflow.id, "loras_strength": {uuid7(): 0.5}},
            )


async def test_preset_update_is_scoped_to_the_owner(data):
    async with db_session.session_scope() as session:
        stranger = UserModel(first_name="Stranger")
        session.add(stranger)
        await session.flush()
        preset = await data.service(session).create(
            stranger.id,
            name="Theirs",
            workflow_id=data.workflow.id,
            prompt="secret",
        )
        with pytest.raises(PresetNotFoundError):
            await data.service(session).update(data.user.id, preset.id, {"name": "Mine"})
        assert (await data.service(session).get_all(stranger.id))[0].name == "Theirs"


async def test_preset_route_updates_and_validates_payloads(data):
    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=data.user.id, first_name="First"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        created = await client.post(
            "/presets",
            json={"name": "Mine", "workflow_id": str(data.workflow.id), "prompt": "A"},
        )
        assert created.status_code == 201, created.text
        preset_id = created.json()["id"]

        patched = await client.patch(
            f"/presets/{preset_id}",
            json={"name": "Renamed", "prompt": "B", "seed": 11},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["name"] == "Renamed"
        assert patched.json()["prompt"] == "B"
        assert patched.json()["seed"] == 11

        for strength in (1.5, 2):
            stronger = await client.patch(
                f"/presets/{preset_id}",
                json={"loras_strength": {str(data.lora.id): strength}},
            )
            assert stronger.status_code == 200, stronger.text
            assert stronger.json()["loras_strength"] == {
                str(data.lora.id): strength
            }

        too_strong = await client.patch(
            f"/presets/{preset_id}",
            json={"loras_strength": {str(data.lora.id): 2.5}},
        )
        assert too_strong.status_code == 422

        assert (await client.patch(f"/presets/{preset_id}", json={})).status_code == 422
        assert (
            await client.patch(f"/presets/{uuid7()}", json={"name": "Ghost"})
        ).status_code == 404
        assert (
            await client.patch(
                f"/presets/{preset_id}", json={"loras_strength": {str(uuid7()): 0.5}}
            )
        ).status_code == 422


async def test_public_presets_are_shared_but_remain_owner_editable(data):
    async with db_session.session_scope() as session:
        stranger = UserModel(first_name="Stranger")
        session.add(stranger)
        await session.flush()
        public = await data.service(session).create(
            stranger.id,
            name="Shared look",
            workflow_id=data.workflow.id,
            prompt="shared prompt",
            is_public=True,
            preview_urls=["https://cdn.example.com/preset-1.png"],
        )
        private = await data.service(session).create(
            stranger.id,
            name="Private look",
            workflow_id=data.workflow.id,
            prompt="private prompt",
        )

    async with db_session.session_scope() as session:
        service = data.service(session)
        listed = await service.get_all(data.user.id)
        assert [item.id for item in listed] == [public.id]
        assert listed[0].preview_urls == ["https://cdn.example.com/preset-1.png"]
        assert listed[0].type == "user"
        assert await service.get_accessible(data.user.id, public.id) is not None
        with pytest.raises(PresetNotFoundError):
            await service.get_accessible(data.user.id, private.id)
        with pytest.raises(PresetNotFoundError):
            await service.update(data.user.id, public.id, {"name": "Stolen"})


async def test_admin_presets_have_no_owner_and_are_public_by_default(data):
    async with db_session.session_scope() as session:
        service = data.service(session)
        preset = await service.create_admin(
            name="Official portrait",
            workflow_id=data.workflow.id,
            prompt="editorial portrait",
            is_public=True,
            preview_urls=[
                "https://cdn.example.com/one.png",
                "https://cdn.example.com/two.png",
            ],
        )
        assert preset.type == "admin"
        assert preset.user_id is None
        assert preset.is_public is True
        assert preset.preview_urls == [
            "https://cdn.example.com/one.png",
            "https://cdn.example.com/two.png",
        ]
        assert (await service.get_all(data.user.id))[0].id == preset.id

        updated = await service.update_admin(
            preset.id,
            {"prompt": "updated", "is_public": False, "preview_urls": []},
        )
        assert updated.prompt == "updated"
        assert updated.is_public is False
        assert updated.preview_urls == []

        assert await service.delete_admin(preset.id) is True
        with pytest.raises(PresetNotFoundError):
            await service.delete_admin(preset.id)


async def test_preset_routes_expose_public_fields_and_accessible_presets(data):
    stranger = UserModel(first_name="Stranger")
    async with db_session.session_scope() as session:
        session.add(stranger)
        await session.flush()
        public = await data.service(session).create(
            stranger.id,
            name="Public",
            workflow_id=data.workflow.id,
            prompt="public",
            is_public=True,
        )

    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=data.user.id, first_name="First"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        created = await client.post(
            "/presets",
            json={
                "name": "Mine",
                "workflow_id": str(data.workflow.id),
                "prompt": "A",
                "is_public": True,
                "preview_urls": ["https://cdn.example.com/mine.png"],
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["is_public"] is True
        assert created.json()["preview_urls"] == [
            "https://cdn.example.com/mine.png"
        ]
        assert created.json()["type"] == "user"
        assert created.json()["user_id"] == str(data.user.id)

        listed = await client.get("/presets")
        ids = {item["id"] for item in listed.json()}
        assert str(public.id) in ids

        accessible = await client.get(f"/presets/{public.id}")
        assert accessible.status_code == 200
        assert accessible.json()["name"] == "Public"

        blocked = await client.patch(
            f"/presets/{public.id}", json={"name": "No"}
        )
        assert blocked.status_code == 404

        invalid = await client.post(
            "/presets",
            json={
                "name": "Bad preview",
                "workflow_id": str(data.workflow.id),
                "preview_urls": ["javascript:alert(1)"],
            },
        )
        assert invalid.status_code == 422


async def test_admin_preset_routes_create_edit_and_delete(data):
    from adapters.api.dependencies.admin import get_current_admin
    from adapters.api.routes.admin_preset import router as admin_router
    from domain.entities.admin import Admin

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_current_admin] = lambda: Admin(
        username="owner", is_owner=True
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        created = await client.post(
            "/admins/presets",
            json={
                "name": "Official",
                "workflow_id": str(data.workflow.id),
                "prompt": "official prompt",
                "description": "Official preset notes",
                "loras_strength": {str(data.lora.id): 1.5},
                "seed": 9,
                "preview_urls": ["https://cdn.example.com/official.png"],
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["type"] == "admin"
        assert body["user_id"] is None
        assert body["is_public"] is True
        assert body["description"] == "Official preset notes"
        assert body["loras_strength"] == {str(data.lora.id): 1.5}
        assert body["preview_urls"] == ["https://cdn.example.com/official.png"]

        listed = await client.get("/admins/presets?query=official")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        patched = await client.patch(
            f"/admins/presets/{body['id']}",
            json={"name": "Official v2", "is_public": False},
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Official v2"
        assert patched.json()["is_public"] is False

        at_limit = await client.patch(
            f"/admins/presets/{body['id']}",
            json={"loras_strength": {str(data.lora.id): 2}},
        )
        assert at_limit.status_code == 200, at_limit.text
        assert at_limit.json()["loras_strength"] == {str(data.lora.id): 2}

        too_strong = await client.patch(
            f"/admins/presets/{body['id']}",
            json={"loras_strength": {str(data.lora.id): 2.5}},
        )
        assert too_strong.status_code == 422

        removed = await client.delete(f"/admins/presets/{body['id']}")
        assert removed.status_code == 204
        assert (await client.get("/admins/presets")).json()["total"] == 0


async def test_public_preset_favorites_are_counted_and_scoped(data):
    stranger = UserModel(first_name="Stranger")
    async with db_session.session_scope() as session:
        session.add(stranger)
        await session.flush()
        public = await data.service(session).create(
            stranger.id,
            name="Popular",
            workflow_id=data.workflow.id,
            prompt="popular",
            is_public=True,
        )
        private = await data.service(session).create(
            stranger.id,
            name="Private",
            workflow_id=data.workflow.id,
            prompt="private",
        )

    async with db_session.session_scope() as session:
        service = data.service(session)
        assert await service.favorite(data.user.id, public.id) == (1, True)
        assert await service.favorite(data.user.id, public.id) == (1, True)
        available = await service.get_all(data.user.id)
        assert available[0].favorites_count == 1
        assert available[0].is_favorite is True
        with pytest.raises(PresetNotFoundError):
            await service.favorite(data.user.id, private.id)
        assert await service.unfavorite(data.user.id, public.id) == (0, False)
        available = await service.get_all(data.user.id)
        assert available[0].favorites_count == 0
        assert available[0].is_favorite is False


async def test_preset_likes_and_saves_are_separate(data):
    stranger = UserModel(first_name="Stranger")
    async with db_session.session_scope() as session:
        session.add(stranger)
        await session.flush()
        public = await data.service(session).create(
            stranger.id,
            name="Like and save",
            workflow_id=data.workflow.id,
            prompt="public",
            is_public=True,
        )

    async with db_session.session_scope() as session:
        service = data.service(session)
        assert await service.favorite(data.user.id, public.id) == (1, True)
        assert await service.save(data.user.id, public.id) is True
        item = next(p for p in await service.get_all(data.user.id) if p.id == public.id)
        assert item.likes_count == 1 and item.is_liked is True
        assert item.is_saved is True
        assert await service.unsave(data.user.id, public.id) is False
        item = next(p for p in await service.get_all(data.user.id) if p.id == public.id)
        assert item.is_saved is False and item.likes_count == 1
        assert await service.unfavorite(data.user.id, public.id) == (0, False)
        item = next(p for p in await service.get_all(data.user.id) if p.id == public.id)
        assert item.likes_count == 0 and item.is_liked is False


async def test_preset_favorite_routes(data):
    stranger = UserModel(first_name="Stranger")
    async with db_session.session_scope() as session:
        session.add(stranger)
        await session.flush()
        public = await data.service(session).create(
            stranger.id,
            name="Public favorite",
            workflow_id=data.workflow.id,
            prompt="public",
            is_public=True,
        )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=data.user.id, first_name="First"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        favorited = await client.put(f"/presets/{public.id}/favorite")
        assert favorited.status_code == 200, favorited.text
        assert favorited.json() == {"favorites_count": 1, "is_favorite": True}

        listed = await client.get("/presets")
        item = next(row for row in listed.json() if row["id"] == str(public.id))
        assert item["favorites_count"] == 1
        assert item["is_favorite"] is True

        liked = await client.put(f"/presets/{public.id}/like")
        assert liked.status_code == 200, liked.text
        assert liked.json() == {"likes_count": 1, "is_liked": True}
        saved = await client.put(f"/presets/{public.id}/save")
        assert saved.status_code == 200, saved.text
        assert saved.json() == {"is_saved": True}
        listed = await client.get("/presets")
        item = next(row for row in listed.json() if row["id"] == str(public.id))
        assert item["is_liked"] is True and item["is_saved"] is True
        unsaved = await client.delete(f"/presets/{public.id}/save")
        assert unsaved.json() == {"is_saved": False}
        unliked = await client.delete(f"/presets/{public.id}/like")
        assert unliked.json() == {"likes_count": 0, "is_liked": False}

        unfavorited = await client.delete(f"/presets/{public.id}/favorite")
        assert unfavorited.status_code == 200, unfavorited.text
        assert unfavorited.json() == {"favorites_count": 0, "is_favorite": False}


async def test_preset_update_persists_non_empty_lora_strengths(data):
    async with db_session.session_scope() as session:
        preset = await data.service(session).create(
            data.user.id,
            name="LoRA preset",
            workflow_id=data.workflow.id,
            prompt="x",
        )
        updated = await data.service(session).update(
            data.user.id,
            preset.id,
            {"loras_strength": {data.lora.id: 0.9}},
        )
        assert updated.loras_strength == {data.lora.id: 0.9}
        assert (await data.service(session).get_all(data.user.id))[0].loras_strength == {
            data.lora.id: 0.9
        }
