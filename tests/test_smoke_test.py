"""
tests.test_smoke_test
~~~~~~~~~~~~~~~~~~~~~
Offline unit tests for scripts/smoke_test.py WAV header validation and
safe live smoke test execution (zero live network traffic or credit consumption).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gnani.config import GnaniConfig
from gnani.timbre import TimbreAPIError
from scripts.smoke_test import run_live_smoke_test, validate_wav_bytes


class TestValidateWavBytes(unittest.TestCase):
    """Unit tests for validate_wav_bytes helper in scripts/smoke_test.py."""

    def setUp(self):
        # Standard valid 44-byte RIFF/WAVE header
        self.valid_44_byte_wav = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        self.minimal_12_byte_wav = b"RIFF\x04\x00\x00\x00WAVE"

    def test_valid_standard_44_byte_wav(self):
        """Standard 44-byte WAV header passes validation."""
        valid, msg = validate_wav_bytes(self.valid_44_byte_wav)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_valid_minimal_12_byte_wav(self):
        """Minimal 12-byte RIFF/WAVE header passes validation."""
        valid, msg = validate_wav_bytes(self.minimal_12_byte_wav)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

    def test_empty_bytes(self):
        """Empty byte string fails validation."""
        valid, msg = validate_wav_bytes(b"")
        self.assertFalse(valid)
        self.assertIn("empty", msg.lower())

    def test_none_value(self):
        """None value fails validation safely."""
        valid, msg = validate_wav_bytes(None)
        self.assertFalse(valid)
        self.assertIn("empty", msg.lower())

    def test_too_short_bytes(self):
        """Byte string shorter than 12 bytes fails validation."""
        valid, msg = validate_wav_bytes(b"RIFF\x04")
        self.assertFalse(valid)
        self.assertIn("too short", msg.lower())

    def test_invalid_riff_magic(self):
        """Non-RIFF magic bytes (e.g. OggS, HTML, MP3) fail validation."""
        invalid_bytes = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00"
        valid, msg = validate_wav_bytes(invalid_bytes)
        self.assertFalse(valid)
        self.assertIn("expected 'RIFF'", msg)

    def test_invalid_wave_format_at_offset_8_11(self):
        """RIFF container with non-WAVE format tag (e.g. AVI, WEBP) fails validation."""
        invalid_bytes = b"RIFF\x24\x00\x00\x00AVI fmt "
        valid, msg = validate_wav_bytes(invalid_bytes)
        self.assertFalse(valid)
        self.assertIn("expected 'WAVE'", msg)


class TestRunLiveSmokeTest(unittest.TestCase):
    """Offline unit tests verifying run_live_smoke_test flow and failure isolation."""

    def setUp(self):
        self.config = GnaniConfig(
            api_key="gnani-sahaayak-test-key",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
            prisma_language="hi-IN",
            timbre_model="timbre-v2.5",
            timbre_voice="Nalini",
            timbre_language="hi-IN",
        )
        self.valid_wav = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )

    @patch("gnani.prisma.PrismaClient.transcribe")
    @patch("gnani.timbre.TimbreClient.synthesize")
    def test_run_live_smoke_test_success_flow(self, mock_synthesize, mock_transcribe):
        """When Timbre returns valid WAV bytes, Prisma is called and test succeeds."""
        mock_synthesize.return_value = self.valid_wav
        mock_transcribe.return_value = {
            "success": True,
            "request_id": "test_req_stt_001",
            "transcript": "Namaste, Gnani Sahaayak.",
        }

        result = run_live_smoke_test(self.config)
        self.assertTrue(result)
        mock_synthesize.assert_called_once()
        mock_transcribe.assert_called_once()
        # Verify Prisma was passed the exact audio bytes from Timbre
        _, call_kwargs = mock_transcribe.call_args
        self.assertEqual(call_kwargs["audio_source"], self.valid_wav)

    @patch("gnani.prisma.PrismaClient.transcribe")
    @patch("gnani.timbre.TimbreClient.synthesize")
    def test_run_live_smoke_test_fails_on_empty_audio_without_calling_prisma(
        self, mock_synthesize, mock_transcribe
    ):
        """When Timbre returns empty bytes, validation fails and Prisma is never called."""
        mock_synthesize.return_value = b""

        result = run_live_smoke_test(self.config)
        self.assertFalse(result)
        mock_synthesize.assert_called_once()
        mock_transcribe.assert_not_called()

    @patch("gnani.prisma.PrismaClient.transcribe")
    @patch("gnani.timbre.TimbreClient.synthesize")
    def test_run_live_smoke_test_fails_on_invalid_riff_without_calling_prisma(
        self, mock_synthesize, mock_transcribe
    ):
        """When Timbre returns invalid bytes (not starting with RIFF), Prisma is not called."""
        mock_synthesize.return_value = b"<html>502 Bad Gateway</html>"

        result = run_live_smoke_test(self.config)
        self.assertFalse(result)
        mock_synthesize.assert_called_once()
        mock_transcribe.assert_not_called()

    @patch("gnani.prisma.PrismaClient.transcribe")
    @patch("gnani.timbre.TimbreClient.synthesize")
    def test_run_live_smoke_test_fails_on_invalid_wave_without_calling_prisma(
        self, mock_synthesize, mock_transcribe
    ):
        """When Timbre returns RIFF but not WAVE format, Prisma is not called."""
        mock_synthesize.return_value = b"RIFF\x24\x00\x00\x00AVI fmt \x10\x00"

        result = run_live_smoke_test(self.config)
        self.assertFalse(result)
        mock_synthesize.assert_called_once()
        mock_transcribe.assert_not_called()

    @patch("gnani.prisma.PrismaClient.transcribe")
    @patch("gnani.timbre.TimbreClient.synthesize")
    def test_run_live_smoke_test_timbre_api_error_stops_safely(
        self, mock_synthesize, mock_transcribe
    ):
        """When Timbre raises TimbreAPIError, Prisma is not called and test returns False."""
        mock_synthesize.side_effect = TimbreAPIError("Timeout connecting to Timbre TTS")

        result = run_live_smoke_test(self.config)
        self.assertFalse(result)
        mock_synthesize.assert_called_once()
        mock_transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()

