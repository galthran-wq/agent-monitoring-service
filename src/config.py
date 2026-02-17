from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_MONITORING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "agent-monitoring-service"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    cors_origins: list[str] = ["*"]
    metrics_enabled: bool = True

    # Monitor loop
    monitor_interval: int = 3600
    lookback_period: int = 3600

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-2.0-flash"
    llm_max_input_tokens: int = 12000
    llm_max_output_tokens: int = 2000

    # Loki
    loki_url: str = "http://loki:3100"
    loki_enabled: bool = True
    loki_extra_queries: list[str] = []

    # Prometheus
    prometheus_url: str = "http://prometheus:9090"
    prometheus_enabled: bool = True
    prometheus_extra_queries: list[str] = []

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_ids: list[str] = []

    @field_validator("telegram_chat_ids", "loki_extra_queries", "prometheus_extra_queries", mode="before")
    @classmethod
    def _parse_comma_separated(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return list(v)


settings = Settings()
