"""
gnani.audio_input
~~~~~~~~~~~~~~~~~
Audio validation and ingestion module for Gnani Sahaayak Voice Assistant.

Supports:
- WAV audio format validation (header check, sample rate, bit depth, channels).
- Size and duration constraints (Prisma STT limit <= 60 seconds, max file size 25MB).
- Audio preparation for PrismaClient ingestion.
"""

from __future__ import annotations

import io
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Tuple, Union


class AudioValidationError(Exception):
    """Raised when an audio input file fails validation checks."""
    pass


@dataclass
class AudioMetadata:
    """Metadata extracted from validated audio."""
    filename: str
    format: str
    channels: int
    sample_rate: int
    sample_width: int
    duration_seconds: float
    size_bytes: int

    def __repr__(self) -> str:
        return (
            f"AudioMetadata(format='{self.format}', "
            f"duration={self.duration_seconds:.2f}s, "
            f"sample_rate={self.sample_rate}Hz, "
            f"channels={self.channels}, "
            f"size={self.size_bytes}B)"
        )


class AudioInputHandler:
    """Validates and prepares audio input for speech recognition."""

    MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    MIN_FILE_SIZE_BYTES: int = 44                # Minimum WAV header size
    MAX_DURATION_SECONDS: float = 60.0           # Prisma v2.5 STT limit
    MIN_DURATION_SECONDS: float = 0.1            # Reject near-empty clips

    def __init__(
        self,
        max_duration_seconds: float = MAX_DURATION_SECONDS,
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    ):
        self.max_duration_seconds = max_duration_seconds
        self.max_file_size_bytes = max_file_size_bytes

    def validate_and_read(
        self,
        audio_source: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str] = None,
    ) -> Tuple[bytes, AudioMetadata]:
        """
        Validates the audio source and returns raw bytes along with metadata.

        Args:
            audio_source: File path (str/Path), raw audio bytes, or binary stream.
            filename: Optional filename hint.

        Returns:
            Tuple of (raw_audio_bytes, AudioMetadata)

        Raises:
            AudioValidationError: If format, duration, or size is invalid.
            FileNotFoundError: If a file path is specified but does not exist.
        """
        resolved_filename = "audio.wav"
        file_bytes: bytes

        if isinstance(audio_source, (str, Path)):
            p = Path(audio_source)
            if not p.is_file():
                raise FileNotFoundError(f"Audio file not found: {audio_source}")
            file_bytes = p.read_bytes()
            resolved_filename = p.name
        elif isinstance(audio_source, bytes):
            file_bytes = audio_source
            if filename:
                resolved_filename = filename
        elif hasattr(audio_source, "read"):
            file_bytes = audio_source.read()
            if filename:
                resolved_filename = filename
            elif hasattr(audio_source, "name"):
                resolved_filename = Path(getattr(audio_source, "name")).name
        else:
            raise AudioValidationError(f"Unsupported audio source type: {type(audio_source)}")

        size = len(file_bytes)
        if size == 0:
            raise AudioValidationError("Audio input is empty (0 bytes).")

        if size < self.MIN_FILE_SIZE_BYTES:
            raise AudioValidationError(
                f"Audio file is too small ({size} bytes). Minimum required is {self.MIN_FILE_SIZE_BYTES} bytes."
            )

        if size > self.max_file_size_bytes:
            raise AudioValidationError(
                f"Audio file size ({size} bytes) exceeds limit of {self.max_file_size_bytes} bytes."
            )

        # Validate RIFF/WAVE header
        if not (file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WAVE"):
            raise AudioValidationError("Invalid audio format: file must be a standard RIFF/WAVE (.wav) file.")

        # Check for streaming placeholders (0xFFFFFFFF) in RIFF size or data chunk size.
        # Streaming TTS services (e.g. Timbre v2.5) write 0xFFFFFFFF when total length is unknown in advance.
        data_idx = file_bytes.find(b"data")
        has_streaming_riff = file_bytes[4:8] == b"\xff\xff\xff\xff"
        has_streaming_data = (
            data_idx != -1
            and data_idx + 8 <= len(file_bytes)
            and file_bytes[data_idx + 4 : data_idx + 8] == b"\xff\xff\xff\xff"
        )

        if has_streaming_riff or has_streaming_data:
            sanitized = bytearray(file_bytes)
            if has_streaming_riff:
                struct.pack_into("<I", sanitized, 4, len(file_bytes) - 8)
            if has_streaming_data:
                actual_pcm_bytes = len(file_bytes) - (data_idx + 8)
                struct.pack_into("<I", sanitized, data_idx + 4, actual_pcm_bytes)
            file_bytes = bytes(sanitized)

        # Inspect WAV stream
        try:
            with wave.open(io.BytesIO(file_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                n_frames = wav_file.getnframes()
                
                if sample_rate <= 0:
                    raise AudioValidationError(f"Invalid sample rate: {sample_rate} Hz.")

                # If n_frames exceeds actual available data payload, recalculate from actual PCM bytes
                if data_idx != -1 and data_idx + 8 <= len(file_bytes):
                    actual_pcm_bytes = len(file_bytes) - (data_idx + 8)
                    frame_size = channels * sample_width
                    if frame_size > 0:
                        max_possible_frames = actual_pcm_bytes // frame_size
                        if n_frames > max_possible_frames:
                            n_frames = max_possible_frames

                duration = n_frames / float(sample_rate)
        except wave.Error as e:
            raise AudioValidationError(f"Corrupted or unsupported WAV file: {e}") from e

        if duration < self.MIN_DURATION_SECONDS:
            raise AudioValidationError(
                f"Audio duration ({duration:.2f}s) is too short. Minimum duration is {self.MIN_DURATION_SECONDS}s."
            )

        if duration > self.max_duration_seconds:
            raise AudioValidationError(
                f"Audio duration ({duration:.2f}s) exceeds maximum allowed length of {self.max_duration_seconds}s."
            )

        metadata = AudioMetadata(
            filename=resolved_filename,
            format="WAV",
            channels=channels,
            sample_rate=sample_rate,
            sample_width=sample_width,
            duration_seconds=duration,
            size_bytes=size,
        )

        return file_bytes, metadata


def create_dummy_wav(duration_seconds: float = 1.0, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """
    Utility to create a valid synthetic PCM WAV byte array for unit testing without files.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        n_frames = int(sample_rate * duration_seconds)
        # Generate silence (0x0000)
        data = b"\x00\x00" * n_frames * channels
        w.writeframes(data)
    return buf.getvalue()

