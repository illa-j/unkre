from datetime import UTC, datetime, timedelta
from uuid import uuid4

from minio.error import S3Error

from adapters.settings import StorageSettings
from adapters.storage import MinioImageStore, generation_image_key, image_media_type

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"
JPEG = b"\xff\xd8\xff" + b"pixels"
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"pixels"


class FakeResponse:
    def __init__(self, data: bytes, content_type: str) -> None:
        self._data = data
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        pass


class FakeMinio:
    def __init__(self, last_modified: datetime | None = None) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.lifecycle = None
        self.bucket = ""
        self.last_modified = last_modified or datetime.now(UTC)
        self.removed: list[str] = []
        self.exists = False

    def bucket_exists(self, bucket: str) -> bool:
        self.bucket = bucket
        return self.exists

    def make_bucket(self, bucket: str) -> None:
        self.exists = True

    def set_bucket_lifecycle(self, bucket: str, config) -> None:
        self.lifecycle = config

    def get_bucket_lifecycle(self, bucket: str):
        return self.lifecycle

    def list_objects(self, bucket, *, prefix, recursive, start_after=None):
        from types import SimpleNamespace

        for key in sorted(self.objects):
            if key.startswith(prefix) and (start_after is None or key > start_after):
                yield SimpleNamespace(object_name=key, last_modified=self.last_modified)

    def put_object(self, bucket, key, data, length=None, content_type=None) -> None:
        self.objects[key] = (data.read(), content_type or "")

    def stat_object(self, bucket, key):
        if key not in self.objects:
            raise S3Error(None, "NoSuchKey", "missing", key, "", "", bucket)
        return type("Stat", (), {"last_modified": self.last_modified, "size": 1})()

    def get_object(self, bucket, key):
        data, content_type = self.objects[key]
        return FakeResponse(data, content_type)

    def remove_object(self, bucket, key) -> None:
        self.removed.append(key)
        self.objects.pop(key, None)


def settings(**overrides) -> StorageSettings:
    values = {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_ACCESS_KEY": "key",
        "MINIO_SECRET_KEY": "secret",
        "MINIO_BUCKET": "unkre-images",
        "MINIO_RETENTION_HOURS": 24,
    }
    values.update(overrides)
    return StorageSettings(**values)


def store(client: FakeMinio, **overrides) -> MinioImageStore:
    return MinioImageStore(settings(**overrides), client=client)


def test_image_signatures_cover_supported_formats() -> None:
    assert image_media_type(PNG) == ("image/png", "png")
    assert image_media_type(JPEG) == ("image/jpeg", "jpg")
    assert image_media_type(WEBP) == ("image/webp", "webp")
    assert image_media_type(b"not an image") is None
    assert image_media_type(b"RIFF0000NOPE") is None


def test_image_key_is_scoped_to_the_generation() -> None:
    ident = uuid4()
    assert generation_image_key(ident) == f"generations/{ident}"


async def test_put_creates_bucket_lifecycle_and_content_type() -> None:
    client = FakeMinio()
    ident = uuid4()

    await store(client).put(ident, PNG)

    key = generation_image_key(ident)
    assert client.objects[key] == (PNG, "image/png")
    assert client.exists is True
    rule = client.lifecycle.rules[0]
    assert rule.rule_id == "expire-generation-images"
    assert rule.expiration.days == 1


async def test_put_skips_unsupported_payloads() -> None:
    client = FakeMinio()
    await store(client).put(uuid4(), b"definitely not an image")
    assert client.objects == {}


async def test_get_returns_cached_image_and_type() -> None:
    client = FakeMinio()
    ident = uuid4()
    cached = store(client)
    await cached.put(ident, JPEG)

    assert await cached.get(ident) == (JPEG, "image/jpeg")


async def test_get_misses_missing_objects() -> None:
    assert await store(FakeMinio()).get(uuid4()) is None


async def test_get_drops_objects_past_retention() -> None:
    client = FakeMinio(last_modified=datetime.now(UTC) - timedelta(hours=25))
    ident = uuid4()
    cached = store(client)
    await cached.put(ident, PNG)
    client.last_modified = datetime.now(UTC) - timedelta(hours=25)

    assert await cached.get(ident) is None
    assert generation_image_key(ident) in client.removed
    assert client.objects == {}


async def test_get_keeps_objects_inside_retention() -> None:
    client = FakeMinio()
    ident = uuid4()
    cached = store(client)
    await cached.put(ident, PNG)
    client.last_modified = datetime.now(UTC) - timedelta(hours=23)

    assert await cached.get(ident) == (PNG, "image/png")
    assert client.removed == []


async def test_delete_removes_the_object() -> None:
    client = FakeMinio()
    ident = uuid4()
    cached = store(client)
    await cached.put(ident, PNG)

    await cached.delete(ident)

    assert client.objects == {}


def test_disabled_settings_need_endpoint_and_credentials() -> None:
    assert settings().enabled is True
    assert settings(MINIO_ENDPOINT="").enabled is False
    assert settings(MINIO_ACCESS_KEY="").enabled is False
    assert settings(MINIO_SECRET_KEY="").enabled is False


def test_endpoint_scheme_is_stripped() -> None:
    assert (
        settings(MINIO_ENDPOINT="https://minio.example.com/").MINIO_ENDPOINT
        == "minio.example.com"
    )


async def test_image_cache_reports_upload_success_and_failure(monkeypatch):
    client = FakeMinio()
    cached = store(client)
    assert await cached.put(uuid4(), PNG) is True
    assert await cached.put(uuid4(), b"invalid image") is False

    def unavailable(*args, **kwargs):
        raise OSError("storage offline")

    monkeypatch.setattr(client, "put_object", unavailable)
    assert await cached.put(uuid4(), PNG) is False


async def test_lifecycle_preserves_unrelated_rules_and_replaces_only_owned_rule():
    from minio.commonconfig import ENABLED, Filter
    from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

    client = FakeMinio()
    external = Rule(
        ENABLED,
        rule_filter=Filter(prefix="other/"),
        rule_id="external",
        expiration=Expiration(days=90),
    )
    previous = Rule(
        ENABLED,
        rule_filter=Filter(prefix="generations/"),
        rule_id="expire-generation-images",
        expiration=Expiration(days=10),
    )
    client.lifecycle = LifecycleConfig([external, previous])
    await store(client).put(uuid4(), PNG)
    rules = client.lifecycle.rules
    assert len(rules) == 2 and rules[0] is external
    assert (
        rules[1].rule_id == "expire-generation-images" and rules[1].expiration.days == 1
    )


async def test_failed_lifecycle_setup_is_retried_without_overwriting_rules(monkeypatch):
    client = FakeMinio()
    original = client.get_bucket_lifecycle

    def denied(bucket):
        raise S3Error(None, "AccessDenied", "denied", bucket, "", "", bucket)

    monkeypatch.setattr(client, "get_bucket_lifecycle", denied)
    cached = store(client)
    assert await cached.put(uuid4(), PNG)
    assert client.lifecycle is None and cached._ready is False
    monkeypatch.setattr(client, "get_bucket_lifecycle", original)
    assert await cached.put(uuid4(), PNG)
    assert cached._ready is True and client.lifecycle is not None


async def test_generation_delete_reports_failure_and_missing_file_is_success(
    monkeypatch,
):
    client = FakeMinio()
    cached = store(client)
    assert await cached.delete(uuid4()) is True

    def fail(*args):
        raise OSError("offline")

    monkeypatch.setattr(client, "remove_object", fail)
    assert await cached.delete(uuid4()) is False

    def missing(*args):
        raise S3Error(None, "NoSuchKey", "missing", "key", "", "", "bucket")

    monkeypatch.setattr(client, "remove_object", missing)
    assert await cached.delete(uuid4()) is True


async def test_image_listing_is_bounded_and_does_not_include_previews():
    client = FakeMinio()
    keys = sorted(generation_image_key(uuid4()) for _ in range(3))
    for key in [*keys, "preset-previews/keep", "lora-previews/keep"]:
        client.objects[key] = (PNG, "image/png")
    cached = store(client)
    page = await cached.list_generation_images(limit=2)
    assert [item.key for item in page] == keys[:2]
    last = await cached.list_generation_images(after=page[-1].key, limit=2)
    assert [item.key for item in last] == keys[2:]
    assert all(item.last_modified == client.last_modified for item in page + last)
