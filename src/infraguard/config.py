from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All fields have local, no-account-required defaults."""

    model_config = SettingsConfigDict(env_prefix="INFRAGUARD_", env_file=".env", extra="ignore")

    db_path: Path = Path("./infraguard.db")
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
