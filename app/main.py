from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import admin, auth, health

settings = get_settings()

app = FastAPI(
    title="DZO Backend",
    description="Shared API for DZO Food, Ride, Biz, and HQ (Epic 1 core platform).",
    version="0.1.0",
    debug=settings.debug,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)

# Future domain routers get included here as they're built, e.g.:
# from app.food.router import router as food_router
# app.include_router(food_router, prefix="/food")
