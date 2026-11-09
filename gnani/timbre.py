"""
gnani.timbre
~~~~~~~~~~~~
Client wrapper for Gnani AI Timbre v2.5 (Text-to-Speech).

Verified Official API Details:
- Endpoint: POST https://api.vachana.ai/api/v1/tts/inference
- Authentication: X-API-Key-ID: <api_key>
- Content-Type: application/json
- Required JSON fields: text, voice, model ('timbre-v2.5'), language
- Optional JSON fields: speed, audio_config
- Response: Raw binary audio (audio/wav) in the HTTP body
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple, Union

import requests

from .config import GnaniConfig, mask_secret


class TimbreAPIError(Exception):
    """Raised when the Timbre TTS API returns an error or fails."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TimbreRateLimitError(TimbreAPIError):
    """Raised when Timbre TTS API returns HTTP 429 Rate Limited or when a concurrent request is blocked."""
    def __init__(self, message: str, status_code: int = 429, response_body: Optional[str] = None):
        super().__init__(message, status_code=status_code, response_body=response_body)


# Minimal 44-byte valid RIFF WAV header for mock testing
_MOCK_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class TimbreClient:
    """Client for interacting with Gnani Timbre v2.5 Text-to-Speech API."""

    # Thread lock guaranteeing strictly one active TTS request at a time
    _request_lock = threading.Lock()

    @classmethod
    def is_synthesizing(cls) -> bool:
        """Returns True if a TTS synthesis request is currently active."""
        return cls._request_lock.locked()

    @classmethod
    def reset_lock(cls) -> None:
        """Safely releases the request lock if held by an interrupted or orphaned thread."""
        if cls._request_lock.locked():
            try:
                cls._request_lock.release()
            except RuntimeError:
                pass

    @property
    def is_busy(self) -> bool:
        """Instance property indicating whether synthesis is currently active."""
        return self._request_lock.locked()

    def __init__(
        self,
        config: GnaniConfig,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        mock_mode: bool = False,
    ):
        self.config = config
        self.timeout = timeout if timeout is not None else getattr(config, "timbre_timeout", (10.0, 60.0))
        self.mock_mode = mock_mode

    @property
    def endpoint_url(self) -> str:
        """Constructs the official verified TTS inference endpoint URL."""
        base = self.config.base_url.rstrip("/")
        return f"{base}/api/v1/tts/inference"

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        audio_config: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Synthesizes text into spoken audio using Gnani Timbre v2.5.

        Args:
            text: Text to speak (plain text, no XML/inline tags for v2.5).
            voice: Voice name (default: config.timbre_voice or 'Nalini').
            language: Language code (default: config.timbre_language or 'hi-IN').
            speed: Speech speed multiplier (default: config.timbre_speed or 1.0).
            audio_config: Optional audio container and sample settings.

        Returns:
            Raw audio binary bytes (WAV format).
        """
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise ValueError("Text to synthesize cannot be empty.")

        # Ensure strictly one active TTS request at a time across the entire application
        acquired = self._request_lock.acquire(blocking=False)
        if not acquired:
            raise TimbreRateLimitError(
                "Audio generation is already in progress. The Timbre TTS service allows only one active voice synthesis request at a time. Please wait for the current request to complete and try again.",
                status_code=429,
            )

        try:
            # Mock mode for offline unit testing without network/API calls
            if self.mock_mode:
                return _MOCK_WAV_BYTES

            chosen_voice = voice or self.config.timbre_voice or "Nalini"
            chosen_language = language or self.config.timbre_language or "hi-IN"
            chosen_speed = speed if speed is not None else self.config.timbre_speed

            sample_rate = getattr(self.config, "timbre_sample_rate", 16000) or 16000
            cfg = audio_config or {
                "encoding": "linear_pcm",
                "container": "wav",
                "num_channels": 1,
                "sample_rate": sample_rate,
                "sample_width": 2,
            }

            payload: Dict[str, Any] = {
                "text": cleaned_text,
                "voice": chosen_voice,
                "model": self.config.timbre_model or "timbre-v2.5",
                "language": chosen_language,
                "speed": chosen_speed,
                "audio_config": cfg,
            }

            headers = self.config.get_headers()
            headers["Content-Type"] = "application/json"

            try:
                response = requests.post(
                    self.endpoint_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as e:
                raise TimbreAPIError(
                    f"Failed to connect to Timbre TTS endpoint at {self.endpoint_url}: {str(e)}"
                ) from None

            # 1. Check HTTP response status code before processing body
            if response.status_code != 200:
                error_text = response.text[:500] if response.text else "<empty response>"
                if response.status_code == 429:
                    msg = (
                        f"Timbre TTS rate limited (HTTP 429): Only one active TTS request is permitted at a time. "
                        f"Server response: {error_text}"
                    )
                    raise TimbreRateLimitError(
                        msg,
                        status_code=429,
                        response_body=response.text,
                    )
                elif response.status_code == 504:
                    msg = f"Timbre TTS gateway timeout (HTTP 504): {error_text}"
                elif response.status_code == 502:
                    msg = f"Timbre TTS bad gateway (HTTP 502): {error_text}"
                elif response.status_code == 503:
                    msg = f"Timbre TTS service unavailable (HTTP 503): {error_text}"
                else:
                    msg = f"Timbre TTS request failed with status {response.status_code}: {error_text}"
                raise TimbreAPIError(
                    msg,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            # 2. Verify response is audio data, not HTML or JSON
            content_type = ""
            if hasattr(response, "headers") and hasattr(response.headers, "get"):
                ct_val = response.headers.get("Content-Type", "")
                if isinstance(ct_val, str):
                    content_type = ct_val.lower()

            if "text/html" in content_type or content_type.startswith("text/"):
                snippet = response.text[:300] if hasattr(response, "text") and isinstance(response.text, str) else ""
                raise TimbreAPIError(
                    f"Timbre TTS returned HTML/text instead of audio (Content-Type: '{content_type}'): {snippet}",
                    status_code=response.status_code,
                    response_body=response.text if hasattr(response, "text") and isinstance(response.text, str) else None,
                )
            if "application/json" in content_type:
                snippet = response.text[:300] if hasattr(response, "text") and isinstance(response.text, str) else ""
                raise TimbreAPIError(
                    f"Timbre TTS returned JSON instead of audio: {snippet}",
                    status_code=response.status_code,
                    response_body=response.text if hasattr(response, "text") and isinstance(response.text, str) else None,
                )

            # 3. Retrieve raw binary audio bytes
            audio_bytes = response.content
            if not audio_bytes:
                raise TimbreAPIError("Timbre TTS returned an empty audio response (0 bytes).")

            # 4. Validate WAV header (must start with RIFF and contain WAVE format tag)
            if len(audio_bytes) < 12 or not (audio_bytes.startswith(b"RIFF") and audio_bytes[8:12] == b"WAVE"):
                preview = audio_bytes[:100].decode("utf-8", errors="replace")
                raise TimbreAPIError(
                    f"Timbre TTS returned invalid WAV audio (missing RIFF/WAVE header, length {len(audio_bytes)}B): {preview}",
                    status_code=response.status_code,
                    response_body=response.text if hasattr(response, "text") else None,
                )

            return audio_bytes
        finally:
            self._request_lock.release()

    def __repr__(self) -> str:
        return (
            f"TimbreClient(endpoint='{self.endpoint_url}', "
            f"key='{mask_secret(self.config.api_key)}', "
            f"model='{self.config.timbre_model}', "
            f"mock_mode={self.mock_mode})"
        )
