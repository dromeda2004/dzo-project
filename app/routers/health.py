from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic liveness check — confirms the app boots and responds, nothing more."""
    return {"status": "ok"}
