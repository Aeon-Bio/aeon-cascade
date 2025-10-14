"""Application settings and configuration."""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS Bedrock Credentials
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"

    # Optional API Keys
    iqair_api_key: Optional[str] = None

    # Application Settings
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # INDRA Settings
    # Network Search API for entity grounding and resolution
    indra_base_url: str = "https://network.indra.bio"
    indra_timeout: int = 30
    indra_cache_ttl: int = 3600  # 1 hour

    # Agent Settings (AWS Bedrock Model ID)
    agent_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    agent_temperature: float = 0.0

    @property
    def is_iqair_configured(self) -> bool:
        """Check if IQAir API key is configured."""
        return self.iqair_api_key is not None and len(self.iqair_api_key) > 0


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance.

    Returns:
        Settings: Application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment.

    Returns:
        Settings: Fresh settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
