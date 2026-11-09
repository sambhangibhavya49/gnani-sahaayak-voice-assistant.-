"""
gnani.config
~~~~~~~~~~~~
Secure configuration loader and credential manager for Gnani AI services.

Ensures that the API key is loaded safely from the local environment (.env),
validated, and masked in all logs, string representations, and error traces.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


class ConfigError(Exception):
    """Raised when configuration is invalid or missing required credentials."""
    pass


def mask_secret(secret: Optional[str]) -> str:
    """
    Safely masks an API key or token for display in logs or status messages.
    Never prints or leaks the full secret.
    
    Examples:
        'gnani-sahaayak-dev-12345678' -> 'gnan...5678'
        'short'                       -> '***'
        None                          -> '<NOT SET>'
    """
    if not secret:
        return "<NOT SET>"
    s = secret.strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}...{s[-4:]}"


def _load_env_file(env_path: Path) -> None:
    """
    Internal loader for .env file.
    Uses python-dotenv if available, or falls back to a minimal pure-Python parser.
    """
    if not env_path.is_file():
        return

    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        # Fallback pure-Python parser (no third-party dependency needed)
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass


@dataclass
class GnaniConfig:
    """Holds configuration for Gnani AI APIs."""
    api_key: str
    base_url: str = "https://api.vachana.ai"
    auth_header: str = "X-API-Key-ID"
    prisma_language: str = "hi-IN"
    timbre_model: str = "timbre-v2.5"
    timbre_voice: str = "Nalini"
    timbre_language: str = "hi-IN"
    timbre_speed: float = 1.0
    timbre_sample_rate: int = 16000
    connect_timeout: float = 10.0
    prisma_read_timeout: float = 60.0
    timbre_read_timeout: float = 60.0

    @property
    def prisma_timeout(self) -> Tuple[float, float]:
        """Returns (connect_timeout, read_timeout) tuple for Prisma STT."""
        return (self.connect_timeout, self.prisma_read_timeout)

    @property
    def timbre_timeout(self) -> Tuple[float, float]:
        """Returns (connect_timeout, read_timeout) tuple for Timbre TTS."""
        return (self.connect_timeout, self.timbre_read_timeout)

    def __repr__(self) -> str:
        """Secure representation: NEVER display raw api_key."""
        return (
            f"GnaniConfig("
            f"api_key='{mask_secret(self.api_key)}', "
            f"base_url='{self.base_url}', "
            f"auth_header='{self.auth_header}', "
            f"prisma_language='{self.prisma_language}', "
            f"timbre_model='{self.timbre_model}', "
            f"timbre_voice='{self.timbre_voice}', "
            f"timbre_language='{self.timbre_language}', "
            f"timbre_speed={self.timbre_speed}, "
            f"timbre_sample_rate={self.timbre_sample_rate}, "
            f"connect_timeout={self.connect_timeout}, "
            f"prisma_read_timeout={self.prisma_read_timeout}, "
            f"timbre_read_timeout={self.timbre_read_timeout})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def get_headers(self) -> Dict[str, str]:
        """Returns the actual HTTP authentication headers."""
        return {self.auth_header: self.api_key}

    def get_sanitized_headers(self) -> Dict[str, str]:
        """Returns masked headers safe for debugging or logging."""
        return {self.auth_header: mask_secret(self.api_key)}

    def validate(self) -> None:
        """Ensures required credentials are present."""
        if not self.api_key or not self.api_key.strip():
            raise ConfigError(
                "GNANI_API_KEY is not set or empty. "
                "Please configure GNANI_API_KEY in your local .env file."
            )
        if not self.base_url or not self.base_url.startswith("http"):
            raise ConfigError(f"Invalid GNANI_API_BASE_URL: '{self.base_url}'")


def load_config(
    env_path: Optional[str | Path] = None,
    require_key: bool = True
) -> GnaniConfig:
    """
    Loads configuration from environment variables and local .env file.
    
    Args:
        env_path: Optional custom path to .env file.
        require_key: If True, raises ConfigError if GNANI_API_KEY is missing.
    
    Returns:
        GnaniConfig instance.
    """
    if env_path is not None:
        target_path = Path(env_path)
    else:
        # Search current working directory, then parent directories
        target_path = Path.cwd() / ".env"
        if not target_path.exists():
            for parent in Path.cwd().parents:
                candidate = parent / ".env"
                if candidate.exists():
                    target_path = candidate
                    break

    _load_env_file(target_path)

    api_key = os.getenv("GNANI_API_KEY", "").strip()
    base_url = os.getenv("GNANI_API_BASE_URL", "https://api.vachana.ai").strip()
    auth_header = os.getenv("GNANI_AUTH_HEADER", "X-API-Key-ID").strip()
    prisma_language = os.getenv("GNANI_PRISMA_LANGUAGE", "hi-IN").strip()
    timbre_model = os.getenv("GNANI_TIMBRE_MODEL", "timbre-v2.5").strip()
    timbre_voice = os.getenv("GNANI_TIMBRE_VOICE", "Nalini").strip()
    timbre_language = os.getenv("GNANI_TIMBRE_LANGUAGE", "hi-IN").strip()

    try:
        timbre_speed = float(os.getenv("GNANI_TIMBRE_SPEED", "1.0"))
    except ValueError:
        timbre_speed = 1.0

    try:
        timbre_sample_rate = int(os.getenv("GNANI_TIMBRE_SAMPLE_RATE", "16000"))
        if timbre_sample_rate <= 0:
            timbre_sample_rate = 16000
    except ValueError:
        timbre_sample_rate = 16000

    def _parse_timeout(var_name: str, fallback: float) -> float:
        val = os.getenv(var_name)
        if val is not None:
            try:
                parsed = float(val.strip())
                if parsed > 0:
                    return parsed
            except ValueError:
                pass
        return fallback

    connect_timeout = _parse_timeout("GNANI_CONNECT_TIMEOUT", 10.0)
    general_read_timeout = _parse_timeout("GNANI_READ_TIMEOUT", 60.0)
    general_read_timeout = _parse_timeout("GNANI_HTTP_TIMEOUT", general_read_timeout)
    prisma_read_timeout = _parse_timeout("GNANI_PRISMA_READ_TIMEOUT", general_read_timeout)
    timbre_read_timeout = _parse_timeout("GNANI_TIMBRE_READ_TIMEOUT", general_read_timeout)

    config = GnaniConfig(
        api_key=api_key,
        base_url=base_url,
        auth_header=auth_header,
        prisma_language=prisma_language,
        timbre_model=timbre_model,
        timbre_voice=timbre_voice,
        timbre_language=timbre_language,
        timbre_speed=timbre_speed,
        timbre_sample_rate=timbre_sample_rate,
        connect_timeout=connect_timeout,
        prisma_read_timeout=prisma_read_timeout,
        timbre_read_timeout=timbre_read_timeout,
    )

    if require_key:
        config.validate()

    return config
