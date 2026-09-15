"""Central configuration loaded exclusively from environment variables.

Rules (sysrules.md):
- Never hardcode credentials; everything flows through env vars / .env.
- Values are parsed once into an immutable, typed settings object.
"""

from functools import lru_cache
from pathlib import Path

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
    openai_base_url: str | None = None

    # Optional distribution channels
    slack_webhook_url: str | None = None
    slack_bot_token: str | None = None
    slack_channel_id: str | None = None
    sendgrid_api_key: str | None = None
    sender_email: str | None = None
    recipient_emails: list[str] | str = Field(default_factory=list)

    # Behavior
    targets_path: Path = DEFAULT_TARGETS_PATH
    model_name: str = Field(default="gpt-4o", alias="competepulse_model")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    similarity_threshold: float = 0.85
    distribution_dry_run: bool = False
    reports_dir: Path = PROJECT_ROOT / "reports"

    @field_validator("recipient_emails", mode="before")
    @classmethod
    def _split_recipients(cls, value: object) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return []
            if val_str.startswith("[") and val_str.endswith("]"):
                try:
                    import json
                    parsed = json.loads(val_str)
                    if isinstance(parsed, list):
                        return [str(e).strip() for e in parsed if str(e).strip()]
                except Exception:
                    pass
            return [email.strip() for email in val_str.split(",") if email.strip()]
        if isinstance(value, (list, tuple)):
            return [str(e).strip() for e in value if str(e).strip()]
        return []

    def has_vector_store(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    def has_llm(self) -> bool:
        return bool(self.openai_api_key or self.nvidia_api_key)

    @property
    def effective_llm_api_key(self) -> str | None:
        return self.nvidia_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str | None:
        if self.openai_base_url:
            return self.openai_base_url
        if self.nvidia_api_key:
            return "https://integrate.api.nvidia.com/v1"
        return None

    def has_scraper(self) -> bool:
        return bool(self.firecrawl_api_key)


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings()
