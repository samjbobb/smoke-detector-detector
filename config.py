"""Configuration management using pydantic-settings."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import JsonConfigSettingsSource


class NtfyConfig(BaseModel):
    """Ntfy notification configuration."""
    enabled: bool = True
    topic: str = "smoke-alarm"
    server: str = "https://ntfy.sh"


class NotificationsConfig(BaseModel):
    """Notifications configuration."""
    ntfy: NtfyConfig = NtfyConfig()


class AudioConfig(BaseModel):
    """Audio configuration."""
    device: Optional[str] = None


class HeartbeatConfig(BaseModel):
    """Heartbeat monitoring configuration."""
    url: Optional[str] = None
    interval_minutes: int = 5


class Config(BaseSettings):
    """Application configuration."""
    model_config = SettingsConfigDict(
        json_file='config.json',
        json_file_encoding='utf-8',
        env_nested_delimiter='__',
        extra='ignore'
    )

    notifications: NotificationsConfig = NotificationsConfig()
    audio: AudioConfig = AudioConfig()
    heartbeat: HeartbeatConfig = HeartbeatConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from JSON file.

    Args:
        config_path: Path to config file. Uses 'config.json' in script directory if None.

    Returns:
        Configuration loaded from file or defaults.
    """
    if config_path is None:
        config_path = Path(__file__).parent / 'config.json'

    return Config(_settings_customise_sources=(
        lambda settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings: (
            init_settings,
            JsonConfigSettingsSource(settings_cls, json_file=config_path),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
    ))