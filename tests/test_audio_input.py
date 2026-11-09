"""
tests.test_audio_input
~~~~~~~~~~~~~~~~~~~~~~
Unit tests for AudioInputHandler, format validation, size and duration limits.
"""

import io
import unittest

from gnani.audio_input import (
    AudioInputHandler,
    AudioValidationError,
    create_dummy_wav,
)


class TestAudioInputHandler(unittest.TestCase):

    def setUp(self):
        self.handler = AudioInputHandler(max_duration_seconds=60.0, max_file_size_bytes=10 * 1024 * 1024)

    def test_valid_dummy_wav_passes(self):
        """Valid synthetic WAV audio passes inspection and returns correct metadata."""
        wav_bytes = create_dummy_wav(duration_seconds=2.5, sample_rate=16000, channels=1)
        data, meta = self.handler.validate_and_read(wav_bytes, filename="order.wav")

        self.assertEqual(data, wav_bytes)
        self.assertEqual(meta.format, "WAV")
        self.assertEqual(meta.channels, 1)
        self.assertEqual(meta.sample_rate, 16000)
        self.assertAlmostEqual(meta.duration_seconds, 2.5, places=2)
        self.assertGreater(meta.size_bytes, 44)

    def test_empty_audio_raises_error(self):
        """Empty audio bytes raise AudioValidationError."""
        with self.assertRaises(AudioValidationError) as ctx:
            self.handler.validate_and_read(b"")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_too_small_payload_raises_error(self):
        """Audio payload smaller than 44 bytes raises AudioValidationError."""
        with self.assertRaises(AudioValidationError) as ctx:
            self.handler.validate_and_read(b"RIFF123")
        self.assertIn("too small", str(ctx.exception).lower())

    def test_non_wav_format_raises_error(self):
        """Non-WAV files (e.g. MP3 header or arbitrary bytes) raise AudioValidationError."""
        fake_mp3 = b"ID3" + b"\x00" * 100
        with self.assertRaises(AudioValidationError) as ctx:
            self.handler.validate_and_read(fake_mp3)
        self.assertIn("standard riff/wave", str(ctx.exception).lower())

    def test_exceeding_max_duration_raises_error(self):
        """Audio exceeding max allowed duration (e.g. 60s) raises AudioValidationError."""
        strict_handler = AudioInputHandler(max_duration_seconds=3.0)
        long_wav = create_dummy_wav(duration_seconds=5.0, sample_rate=8000)
        with self.assertRaises(AudioValidationError) as ctx:
            strict_handler.validate_and_read(long_wav)
        self.assertIn("exceeds maximum allowed length", str(ctx.exception).lower())

    def test_file_not_found(self):
        """Non-existent file path raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.handler.validate_and_read("non_existent_audio_path_xyz123.wav")

    def test_file_stream_input(self):
        """Passing an io.BytesIO stream is correctly supported."""
        wav_bytes = create_dummy_wav(duration_seconds=1.0, sample_rate=16000)
        stream = io.BytesIO(wav_bytes)
        data, meta = self.handler.validate_and_read(stream, filename="stream_audio.wav")
        self.assertEqual(len(data), len(wav_bytes))
        self.assertEqual(meta.filename, "stream_audio.wav")

    def test_streaming_placeholder_wav_calculates_correct_duration(self):
        """
        Regression test: Timbre v2.5 streaming TTS writes 0xFFFFFFFF in RIFF size
        and data chunk size. Handler must calculate true duration from available PCM bytes
        and sanitize headers rather than reporting ~44,739 seconds.
        """
        # Create 3.0s audio at 48kHz (Timbre default format)
        clean_wav = create_dummy_wav(duration_seconds=3.0, sample_rate=48000, channels=1)
        streaming_bytes = bytearray(clean_wav)
        
        # Inject 0xFFFFFFFF streaming placeholders
        streaming_bytes[4:8] = b"\xff\xff\xff\xff"
        data_idx = streaming_bytes.find(b"data")
        self.assertNotEqual(data_idx, -1)
        streaming_bytes[data_idx + 4 : data_idx + 8] = b"\xff\xff\xff\xff"

        sanitized_data, meta = self.handler.validate_and_read(
            bytes(streaming_bytes), filename="timbre_live.wav"
        )

        # Duration must be 3.0 seconds, NOT 44,739s
        self.assertAlmostEqual(meta.duration_seconds, 3.0, places=2)
        self.assertEqual(meta.sample_rate, 48000)
        self.assertEqual(meta.channels, 1)
        self.assertEqual(meta.format, "WAV")

        # Returned audio bytes should have sanitized valid chunk sizes
        self.assertNotEqual(sanitized_data[4:8], b"\xff\xff\xff\xff")
        sanitized_data_idx = sanitized_data.find(b"data")
        self.assertNotEqual(
            sanitized_data[sanitized_data_idx + 4 : sanitized_data_idx + 8],
            b"\xff\xff\xff\xff",
        )

    def test_streaming_placeholder_wav_exceeding_max_duration_still_raises(self):
        """
        Confirms that the 60-second limit is NOT bypassed for streaming WAVs:
        a streaming-header WAV whose actual PCM data exceeds 60s must still be rejected.
        """
        # Create 65.0s audio with strict 60s handler
        long_wav = create_dummy_wav(duration_seconds=65.0, sample_rate=8000, channels=1)
        streaming_bytes = bytearray(long_wav)
        streaming_bytes[4:8] = b"\xff\xff\xff\xff"
        data_idx = streaming_bytes.find(b"data")
        streaming_bytes[data_idx + 4 : data_idx + 8] = b"\xff\xff\xff\xff"

        with self.assertRaises(AudioValidationError) as ctx:
            self.handler.validate_and_read(bytes(streaming_bytes))
        self.assertIn("exceeds maximum allowed length", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()

