from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configuración centralizada del visualizer.


class Settings(BaseSettings):
    """Runtime configuration for the Visualizer service."""

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_queue_name: str = Field(default="extracted_words", alias="REDIS_QUEUE")
    redis_block_timeout: int = Field(default=5, alias="REDIS_BLOCK_TIMEOUT")
    default_top_n: int = Field(default=15, alias="DEFAULT_TOP_N")
    websocket_max_updates_per_second: int = Field(default=5, alias="WS_MAX_UPDATES_PER_SECOND")
    dashboard_repo_limit: int = Field(default=5, alias="DASHBOARD_REPO_LIMIT")
    dashboard_activity_limit: int = Field(default=10, alias="DASHBOARD_ACTIVITY_LIMIT")
    dashboard_repo_top_words: int = Field(default=5, alias="DASHBOARD_REPO_TOP_WORDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
