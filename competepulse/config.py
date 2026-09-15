"""Central configuration loaded exclusively from environment variables.

Rules (sysrules.md):
- Never hardcode credentials; everything flows through env vars / .env.
- Values are parsed once into an immutable, typed settings object.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGETS_PATH = PROJECT_ROOT / "targets.json"

TARGET_ENDPOINTS: dict[str, list[str]] = {
    "pricing": ["/pricing"],
    "changelog": ["/blog", "/changelog"],
    "terms": ["/terms", "/privacy"],
}

PAGE_TYPES: tuple[str, ...] = tuple(TARGET_ENDPOINTS.keys())


class Settings(BaseSettings):
    """Typed application settings (loaded from environment / .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required integrations
    firecrawl_api_key: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None
    openai_api_key: str | None = None
    nvidia_api_key: str | None = None
    deepseek_api_key: str | None = None
    openai_base_url: str | None = None

    @field_validator("supabase_url", mode="before")
    @classmethod
    def _sanitize_supabase_url(cls, value: object) -> object:
        if isinstance(value, str):
            val = value.strip()
            if "supabase.com/dashboard/project/" in val:
                import re
                match = re.search(r"supabase\.com/dashboard/project/([a-zA-Z0-9_-]+)", val)
                if match:
                    return f"https://{match.group(1)}.supabase.co"
            return val
        return value

    # Optional distribution channels
    slack_webhook_url: str | None = None
    slack_bot_token: str | None = None
    slack_channel_id: str | None = None
    sendgrid_api_key: str | None = None
    sender_email: str | None = None
    recipient_emails_raw: str | None = Field(default=None, alias="recipient_emails")

    def __init__(self, **kwargs: Any) -> None:
        if "recipient_emails" in kwargs:
            raw_val = kwargs.pop("recipient_emails")
            if isinstance(raw_val, (list, tuple)):
                kwargs["recipient_emails"] = ",".join(str(e) for e in raw_val)
            else:
                kwargs["recipient_emails"] = raw_val
        super().__init__(**kwargs)

    # Behavior
    targets_path: Path = DEFAULT_TARGETS_PATH
    model_name: str = Field(default="deepseek-ai/deepseek-r1", alias="competepulse_model")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    similarity_threshold: float = 0.85
    distribution_dry_run: bool = False
    reports_dir: Path = PROJECT_ROOT / "reports"

    @field_validator("distribution_dry_run", mode="before")
    @classmethod
    def _parse_dry_run(cls, value: object) -> bool:
        if isinstance(value, str):
            val = value.strip().lower()
            if not val or val in ("false", "0", "no", "off", "f"):
                return False
            if val in ("true", "1", "yes", "on", "t"):
                return True
        if isinstance(value, bool):
            return value
        return False

    @field_validator("similarity_threshold", mode="before")
    @classmethod
    def _parse_similarity_threshold(cls, value: object) -> float:
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return 0.85
            try:
                return float(val)
            except ValueError:
                return 0.85
        if isinstance(value, (int, float)):
            return float(value)
        return 0.85

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def _parse_embedding_dimensions(cls, value: object) -> int:
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return 1536
            try:
                return int(val)
            except ValueError:
                return 1536
        if isinstance(value, int):
            return value
        return 1536

    @property
    def recipient_emails(self) -> list[str]:
        val = self.recipient_emails_raw
        if not val or not isinstance(val, str) or not val.strip():
            return []
        val_str = val.strip()
        if val_str.startswith("[") and val_str.endswith("]"):
            try:
                import json
                parsed = json.loads(val_str)
                if isinstance(parsed, list):
                    return [str(e).strip() for e in parsed if str(e).strip()]
            except Exception:
                pass
        return [email.strip() for email in val_str.split(",") if email.strip()]

    def has_vector_store(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    def has_llm(self) -> bool:
        return bool(self.openai_api_key or self.nvidia_api_key or self.deepseek_api_key)

    @property
    def effective_llm_api_key(self) -> str | None:
        return self.deepseek_api_key or self.nvidia_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str | None:
        if self.openai_base_url:
            return self.openai_base_url
        if self.deepseek_api_key and not self.openai_api_key and not self.nvidia_api_key:
            return "https://api.deepseek.com/v1"
        if self.nvidia_api_key and not self.openai_api_key:
            return "https://integrate.api.nvidia.com/v1"
        return None

    @property
    def effective_model_name(self) -> str:
        if self.deepseek_api_key and not self.openai_api_key and not self.nvidia_api_key:
            if self.model_name in ("gpt-4o", "gpt-4o-mini", "gpt-4", "deepseek-ai/deepseek-r1"):
                return "deepseek-chat"
        if self.nvidia_api_key and not self.openai_api_key:
            if self.model_name in ("gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"):
                return "deepseek-ai/deepseek-r1"
        if self.openai_api_key and not self.nvidia_api_key:
            if "deepseek" in self.model_name:
                return "gpt-4o-mini"
        return self.model_name

    def has_scraper(self) -> bool:
        return bool(self.firecrawl_api_key)


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings()
