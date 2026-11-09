"""
gnani.prisma
~~~~~~~~~~~~
Client wrapper for Gnani AI Prisma v2.5 (Speech-to-Text).

Verified Official API Details:
- Endpoint: POST https://api.vachana.ai/stt/v3
- Authentication: X-API-Key-ID: <api_key>
- Content-Type: multipart/form-data
- Required form fields: audio_file (binary), language_code (e.g., 'hi-IN')
- Optional form fields: format='transcribe', itn_native_numerals='true'
- Response: JSON with 'success', 'request_id', 'timestamp', 'transcript'
- Limits: Audio clips <= 60 seconds
"""

from __future__ import annotations

import io
from pathlib import Path
import threading
from typing import BinaryIO, Dict, Optional, Tuple, Union

import requests

from .config import GnaniConfig, mask_secret


class PrismaAPIError(Exception):
    """Raised when the Prisma STT API returns an error or fails."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PrismaRateLimitError(PrismaAPIError):
    """Raised when Prisma STT API returns HTTP 429 Rate Limited or when a concurrent request is blocked."""
    def __init__(self, message: str, status_code: int = 429, response_body: Optional[str] = None):
        super().__init__(message, status_code=status_code, response_body=response_body)


class PrismaClient:
    """Client for interacting with Gnani Prisma v2.5 Speech-to-Text API."""

    # Thread lock guaranteeing strictly one active STT request at a time
    _request_lock = threading.Lock()

    @classmethod
    def is_transcribing(cls) -> bool:
        """Returns True if an STT transcription request is currently active."""
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
        """Instance property indicating whether transcription is currently active."""
        return self._request_lock.locked()

    def __init__(
        self,
        config: GnaniConfig,
        timeout: Optional[Union[float, Tuple[float, float]]] = None,
        mock_mode: bool = False,
    ):
        self.config = config
        self.timeout = timeout if timeout is not None else getattr(config, "prisma_timeout", (10.0, 60.0))
        self.mock_mode = mock_mode

    @property
    def endpoint_url(self) -> str:
        """Constructs the official verified STT v3 endpoint URL."""
        base = self.config.base_url.rstrip("/")
        return f"{base}/stt/v3"

    def transcribe(
        self,
        audio_source: Union[str, Path, bytes, BinaryIO],
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
        preferred_language: Optional[str] = None,
        itn_native_numerals: bool = True,
    ) -> Dict[str, Union[str, bool]]:
        """
        Transcribes an audio file or bytes using Gnani Prisma v2.5.

        Args:
            audio_source: File path (str/Path), raw audio bytes, or binary stream.
            filename: Name of the audio file (default: audio.wav).
            language_code: Language code (default: config.prisma_language or 'hi-IN').
            preferred_language: Optional preferred language code.
            itn_native_numerals: Apply Inverse Text Normalization to spoken numbers.

        Returns:
            Dict containing 'transcript', 'request_id', 'success', and 'timestamp'.
        """
        lang = language_code or self.config.prisma_language or "hi-IN"

        # Ensure strictly one active STT request at a time across the entire application
        acquired = self._request_lock.acquire(blocking=False)
        if not acquired:
            raise PrismaRateLimitError(
                "Speech transcription is already in progress. The Prisma STT service allows only one active transcription request at a time. Please wait for the current request to complete and try again.",
                status_code=429,
            )

        try:
            # Mock mode for offline unit testing without network/API calls
            if self.mock_mode:
                return {
                    "success": True,
                    "request_id": "mock_req_stt_123",
                    "timestamp": "mock_timestamp",
                    "transcript": "Anna, two kilos of rice, one litre of oil, aur ek kilo sugar.",
                }

            # Resolve audio content
            file_bytes: bytes
            if isinstance(audio_source, (str, Path)):
                p = Path(audio_source)
                if not p.is_file():
                    raise FileNotFoundError(f"Audio file not found: {audio_source}")
                file_bytes = p.read_bytes()
                filename = p.name
            elif isinstance(audio_source, bytes):
                file_bytes = audio_source
            elif hasattr(audio_source, "read"):
                file_bytes = audio_source.read()
            else:
                raise ValueError(f"Unsupported audio source type: {type(audio_source)}")

            if not file_bytes:
                raise ValueError("Audio payload is empty (0 bytes).")

            headers = self.config.get_headers()

            mime_type = "audio/wav" if filename.lower().endswith(".wav") else "application/octet-stream"
            files = {
                "audio_file": (filename, io.BytesIO(file_bytes), mime_type)
            }

            data = {
                "language_code": lang, 
                "format": "transcribe",
                "itn_native_numerals": "true" if itn_native_numerals else "false",
            }

            if preferred_language:
                data["preferred_language"] = preferred_language

            try:
                response = requests.post(
                    self.endpoint_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as e:
                # Mask headers from error representations
                raise PrismaAPIError(
                    f"Failed to connect to Prisma STT endpoint at {self.endpoint_url}: {str(e)}"
                ) from None

            if response.status_code != 200:
                error_text = response.text[:500] if response.text else "<empty response>"
                if response.status_code == 429:
                    msg = (
                        f"Prisma STT rate limited (HTTP 429): Only one active STT request is permitted at a time. "
                        f"Server response: {error_text}"
                    )
                    raise PrismaRateLimitError(
                        msg,
                        status_code=429,
                        response_body=response.text,
                    )
                raise PrismaAPIError(
                    f"Prisma STT request failed with status {response.status_code}: {error_text}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            try:
                payload = response.json()
            except Exception as e:
                raise PrismaAPIError(
                    f"Prisma STT returned non-JSON response: {response.text[:200]}"
                ) from e

            if not isinstance(payload, dict):
                raise PrismaAPIError(f"Unexpected response structure: {payload}")

            return {
                "success": payload.get("success", True),
                "request_id": payload.get("request_id", ""),
                "timestamp": payload.get("timestamp", ""),
                "transcript": payload.get("transcript", "").strip(),
            }
        finally:
            self._request_lock.release()

    def __repr__(self) -> str:
        return (
            f"PrismaClient(endpoint='{self.endpoint_url}', "
            f"key='{mask_secret(self.config.api_key)}', "
            f"mock_mode={self.mock_mode})"
        )
