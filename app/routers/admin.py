from fastapi import APIRouter, Depends

from app.core.auth import Role, require_role
from app.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
async def ping(user: User = Depends(require_role(Role.ADMIN))) -> dict[str, str]:
    """Admin-only route proving require_role actually gates access — see epic1.task3."""
    return {"status": "ok", "admin": user.email}
