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


@lru_cache
def get_settings() -> Settings:
    return Settings()
