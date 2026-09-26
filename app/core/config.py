from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration, loaded from environment variables / .env.
    See .env.example for the full list of expected variables.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://dzo:dzo@localhost:5432/dzo"
    alembic_database_url: str = "postgresql+psycopg2://dzo:dzo@localhost:5432/dzo"

    # MUST be overridden via .env in any shared environment — this default is
    # intentionally obvious so it's never mistaken for a real secret.
    secret_key: str = "dev-insecure-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Third-party integration credentials — provider not yet confirmed for any
    # of these (see DZO_TECH_ROADMAP.md §5). Unused stubs until roadmap Epic 5
    # (payments) / Epic 6 (DZO Ride) wire up a real integration; optional so
    # their absence never breaks local dev or tests.
    stripe_secret_key: str | None = None
    google_maps_api_key: str | None = None
    fcm_server_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
