from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Container health probe: no database, no schema generation, no auth."""
    return {"status": "ok"}
