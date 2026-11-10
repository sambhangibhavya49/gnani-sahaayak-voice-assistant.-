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
import re
import threading
import time
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


def _clean_error_message(status_code: int, raw_text: Optional[str]) -> str:
    """Sanitizes HTTP error responses, ensuring raw HTML gateway pages are never exposed to the customer."""
    clean_text = (raw_text or "").strip()
    if "<html" in clean_text.lower() or "<body" in clean_text.lower() or "<head" in clean_text.lower():
        title_match = re.search(r"<title[^>]*>(.*?)</title>", clean_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            clean_text = title_match.group(1).strip()
        else:
            clean_text = re.sub(r"<[^>]+>", " ", clean_text)
            clean_text = " ".join(clean_text.split())

    clean_text = clean_text[:300].strip() or "<empty response>"

    if status_code == 504:
        return f"Prisma STT gateway timeout (HTTP 504): The speech recognition service timed out while processing audio. Detail: {clean_text}"
    elif status_code == 502:
        return f"Prisma STT bad gateway (HTTP 502): The speech recognition gateway received an invalid upstream response. Detail: {clean_text}"
    elif status_code == 503:
        return f"Prisma STT service temporarily unavailable (HTTP 503): The speech recognition service is busy or undergoing maintenance. Detail: {clean_text}"
    elif status_code == 429:
        return f"Prisma STT rate limited (HTTP 429): Only one active STT request is permitted at a time. Server response: {clean_text}"
    else:
        return f"Prisma STT request failed with status {status_code}: {clean_text}"


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
        max_retries: int = 1,
        retry_backoff: float = 1.2,
    ):
        self.config = config
        self.timeout = timeout if timeout is not None else getattr(config, "prisma_timeout", (10.0, 60.0))
        self.mock_mode = mock_mode
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

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
        max_retries: Optional[int] = None,
    ) -> Dict[str, Union[str, bool]]:
        """
        Transcribes an audio file or bytes using Gnani Prisma v2.5.

        Args:
            audio_source: File path (str/Path), raw audio bytes, or binary stream.
            filename: Name of the audio file (default: audio.wav).
            language_code: Language code (default: config.prisma_language or 'hi-IN').
            preferred_language: Optional preferred language code.
            itn_native_numerals: Apply Inverse Text Normalization to spoken numbers.
            max_retries: Optional override for transient gateway error retry count.

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

            data = {
                "language_code": lang,
                "format": "transcribe",
                "itn_native_numerals": "true" if itn_native_numerals else "false",
            }

            if preferred_language:
                data["preferred_language"] = preferred_language

            retries_allowed = self.max_retries if max_retries is None else max_retries
            attempts_total = 1 + max(0, retries_allowed)
            last_err: Optional[Exception] = None

            for attempt in range(attempts_total):
                is_last_attempt = (attempt == attempts_total - 1)

                # Rewind and prepare fresh stream for multipart upload
                audio_stream = io.BytesIO(file_bytes)
                files = {
                    "audio_file": (filename, audio_stream, mime_type)
                }

                try:
                    response = requests.post(
                        self.endpoint_url,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=self.timeout,
                    )
                except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as net_err:
                    last_err = PrismaAPIError(
                        f"Failed to connect to Prisma STT endpoint at {self.endpoint_url}: {str(net_err)}"
                    )
                    if not is_last_attempt:
                        time.sleep(self.retry_backoff)
                        continue
                    raise last_err from None
                except requests.exceptions.RequestException as e:
                    # Non-retriable request exception
                    raise PrismaAPIError(
                        f"Failed to connect to Prisma STT endpoint at {self.endpoint_url}: {str(e)}"
                    ) from None

                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except Exception as e:
                        raise PrismaAPIError(
                            f"Prisma STT returned non-JSON response: {_clean_error_message(200, response.text)}"
                        ) from e

                    if not isinstance(payload, dict):
                        raise PrismaAPIError(f"Unexpected response structure: {payload}")

                    return {
                        "success": payload.get("success", True),
                        "request_id": payload.get("request_id", ""),
                        "timestamp": payload.get("timestamp", ""),
                        "transcript": payload.get("transcript", "").strip(),
                    }

                # Non-200 HTTP response
                cleaned_msg = _clean_error_message(response.status_code, response.text)
                if response.status_code == 429:
                    raise PrismaRateLimitError(
                        cleaned_msg,
                        status_code=429,
                        response_body=response.text,
                    )

                # Check if transient gateway error and retries remain
                if response.status_code in {502, 503, 504} and not is_last_attempt:
                    time.sleep(self.retry_backoff)
                    continue

                # Non-retriable or retries exhausted
                raise PrismaAPIError(
                    cleaned_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            if last_err:
                raise last_err
        finally:
            self._request_lock.release()

    def __repr__(self) -> str:
        return (
            f"PrismaClient(endpoint='{self.endpoint_url}', "
            f"key='{mask_secret(self.config.api_key)}', "
            f"mock_mode={self.mock_mode})"
        )
