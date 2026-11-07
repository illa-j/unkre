import httpx

from adapters.api.main import app


async def test_health_probe_is_cheap_and_hidden_from_the_schema():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.example") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "/healthz" not in app.openapi()["paths"]
