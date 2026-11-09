"""
gnani.speech
~~~~~~~~~~~~
Speech Recognition Service module wrapping Gnani Prisma v2.5 STT.

Handles:
- Audio format and size validation.
- Sending audio to Prisma STT endpoint.
- Handling empty audio, API errors, timeouts, and blank transcripts gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Union

import requests

from .audio_input import AudioInputHandler, AudioMetadata, AudioValidationError
from .config import GnaniConfig
from .prisma import PrismaAPIError, PrismaClient, PrismaRateLimitError


class SpeechRecognitionError(Exception):
    """Raised when speech recognition fails."""
    pass


@dataclass
class SpeechResult:
    """Result of speech recognition process."""
    success: bool
    transcript: str
    request_id: str = ""
    timestamp: str = ""
    error: Optional[str] = None
    metadata: Optional[AudioMetadata] = None

    @property
    def is_empty(self) -> bool:
        """Returns True if the transcription contains no speech."""
        return not bool(self.transcript and self.transcript.strip())


class SpeechRecognizer:
    """Service orchestrating speech-to-text recognition with validation and error handling."""

    def __init__(
        self,
        config: GnaniConfig,
        client: Optional[PrismaClient] = None,
        audio_handler: Optional[AudioInputHandler] = None,
        mock_mode: bool = False,
    ):
        self.config = config
        self.client = client or PrismaClient(config=config, mock_mode=mock_mode)
        self.audio_handler = audio_handler or AudioInputHandler()
        self.mock_mode = mock_mode

    @property
    def is_busy(self) -> bool:
        """Indicates whether speech recognition transcription is currently active."""
        return getattr(self.client, "is_busy", False)

    def transcribe(
        self,
        audio_source: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> SpeechResult:
        """
        Validates audio and transcribes it using Prisma STT.

        Args:
            audio_source: File path, bytes, or file-like stream.
            filename: Optional filename hint.
            language_code: STT language (defaults to config.prisma_language).

        Returns:
            SpeechResult dataclass instance.
        """
        # 1. Validate audio input format and duration
        try:
            audio_bytes, metadata = self.audio_handler.validate_and_read(audio_source, filename)
        except (AudioValidationError, FileNotFoundError, ValueError) as e:
            return SpeechResult(
                success=False,
                transcript="",
                error=f"Audio validation failed: {str(e)}",
            )

        # 2. Transcribe via Prisma client
        try:
            response = self.client.transcribe(
                audio_source=audio_bytes,
                filename=metadata.filename,
                language_code=language_code or self.config.prisma_language,
            )
        except requests.exceptions.Timeout:
            return SpeechResult(
                success=False,
                transcript="",
                error="Speech recognition timed out. Please try again.",
                metadata=metadata,
            )
        except PrismaRateLimitError as e:
            return SpeechResult(
                success=False,
                transcript="",
                error=f"Prisma STT Rate Limited (HTTP 429): {str(e)}",
                metadata=metadata,
            )
        except PrismaAPIError as e:
            return SpeechResult(
                success=False,
                transcript="",
                error=f"Prisma API error: {str(e)}",
                metadata=metadata,
            )
        except Exception as e:
            return SpeechResult(
                success=False,
                transcript="",
                error=f"Unexpected transcription failure: {str(e)}",
                metadata=metadata,
            )

        transcript = str(response.get("transcript", "")).strip()
        request_id = str(response.get("request_id", ""))
        timestamp = str(response.get("timestamp", ""))

        return SpeechResult(
            success=True,
            transcript=transcript,
            request_id=request_id,
            timestamp=timestamp,
            metadata=metadata,
        )

