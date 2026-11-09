"""
tests.test_clients_mock
~~~~~~~~~~~~~~~~~~~~~~~
Offline unit tests verifying Prisma v2.5 and Timbre v2.5 client wrappers
using mocked HTTP responses (zero live network traffic or credit consumption).
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from gnani.config import GnaniConfig
from gnani.prisma import PrismaAPIError, PrismaClient, PrismaRateLimitError
from gnani.timbre import TimbreAPIError, TimbreClient, TimbreRateLimitError, _MOCK_WAV_BYTES


class TestPrismaClient(unittest.TestCase):

    def setUp(self):
        self.config = GnaniConfig(
            api_key="gnani-sahaayak-dev-test-key",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
            prisma_language="hi-IN",
        )
        self.client = PrismaClient(config=self.config)

    def test_endpoint_url(self):
        """Verified official STT v3 endpoint URL."""
        self.assertEqual(self.client.endpoint_url, "https://api.vachana.ai/stt/v3")

    def test_client_repr_masks_key(self):
        """Ensures PrismaClient repr masks secret."""
        repr_str = repr(self.client)
        self.assertNotIn("gnani-sahaayak-dev-test-key", repr_str)
        self.assertIn("gnan...-key", repr_str)

    def test_mock_mode_returns_transcript(self):
        """Offline mock mode returns expected structure without network calls."""
        mock_client = PrismaClient(config=self.config, mock_mode=True)
        res = mock_client.transcribe(audio_source=b"fake-audio-bytes")
        self.assertTrue(res["success"])
        self.assertIn("transcript", res)
        self.assertIn("rice", res["transcript"].lower())

    def test_empty_audio_raises_value_error(self):
        """Transcribing empty bytes raises ValueError immediately."""
        with self.assertRaises(ValueError):
            self.client.transcribe(audio_source=b"")

    @patch("requests.post")
    def test_transcribe_success_flow(self, mock_post):
        """Verifies correct multipart payload construction and success parsing."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "success": True,
            "request_id": "req_stt_abc123",
            "timestamp": "20261026_230000.000",
            "transcript": "Anna, two kilos of rice aur ek kilo sugar.",
        }
        mock_post.return_value = fake_response

        dummy_audio = b"RIFF....WAVEfmt....data...."
        result = self.client.transcribe(
            audio_source=dummy_audio,
            filename="customer_order.wav",
            language_code="hi-IN",
        )

        # 1. Verify requests.post was called with the verified URL
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.vachana.ai/stt/v3")

        # 2. Verify headers
        self.assertEqual(call_kwargs["headers"]["X-API-Key-ID"], "gnani-sahaayak-dev-test-key")

        # 3. Verify multipart form data
        data = call_kwargs["data"]
        self.assertEqual(data["language_code"], "hi-IN")
        self.assertEqual(data["format"], "transcribe")
        self.assertEqual(data["itn_native_numerals"], "true")

        # 4. Verify file payload
        files = call_kwargs["files"]
        self.assertIn("audio_file", files)
        file_tuple = files["audio_file"]
        self.assertEqual(file_tuple[0], "customer_order.wav")

        # 5. Verify parsed result
        self.assertTrue(result["success"])
        self.assertEqual(result["request_id"], "req_stt_abc123")
        self.assertEqual(result["transcript"], "Anna, two kilos of rice aur ek kilo sugar.")

    @patch("requests.post")
    def test_transcribe_error_status_handling(self, mock_post):
        """Verifies handling of 401 Unauthorized and 400 Bad Request."""
        fake_response = MagicMock()
        fake_response.status_code = 401
        fake_response.text = '{"error": "Unauthorized", "message": "Invalid API Key"}'
        mock_post.return_value = fake_response

        with self.assertRaises(PrismaAPIError) as ctx:
            self.client.transcribe(audio_source=b"fake-bytes")

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("401", str(ctx.exception))
        # Ensure secret is NOT in the error message
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_transcribe_default_timeout_propagation(self, mock_post):
        """Verifies that PrismaClient propagates config.prisma_timeout tuple to requests.post."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"success": True, "transcript": "ok"}
        mock_post.return_value = fake_response

        self.client.transcribe(audio_source=b"RIFFdummydata")
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["timeout"], (10.0, 60.0))

    @patch("requests.post")
    def test_transcribe_custom_timeout_propagation(self, mock_post):
        """Verifies that PrismaClient accepts a custom timeout tuple."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"success": True, "transcript": "ok"}
        mock_post.return_value = fake_response

        custom_client = PrismaClient(config=self.config, timeout=(5.0, 30.0))
        custom_client.transcribe(audio_source=b"RIFFdummydata")
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["timeout"], (5.0, 30.0))

    @patch("requests.post")
    def test_transcribe_connect_timeout_handling(self, mock_post):
        """Verifies ConnectTimeout is safely caught, wrapped in PrismaAPIError, and key is masked."""
        mock_post.side_effect = requests.exceptions.ConnectTimeout("Connection timed out after 10s")
        with self.assertRaises(PrismaAPIError) as ctx:
            self.client.transcribe(audio_source=b"RIFFdummydata")

        self.assertIn("Connection timed out after 10s", str(ctx.exception))
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_transcribe_read_timeout_handling(self, mock_post):
        """Verifies ReadTimeout is safely caught, wrapped in PrismaAPIError, and key is masked."""
        mock_post.side_effect = requests.exceptions.ReadTimeout("Read timed out after 60s")
        with self.assertRaises(PrismaAPIError) as ctx:
            self.client.transcribe(audio_source=b"RIFFdummydata")

        self.assertIn("Read timed out after 60s", str(ctx.exception))
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_transcribe_429_rate_limit(self, mock_post):
        """Verifies HTTP 429 Rate Limited raises PrismaRateLimitError with clear status and message."""
        fake_response = MagicMock()
        fake_response.status_code = 429
        fake_response.text = '{"error": "RATE_LIMITED", "message": "Only one active STT request allowed at a time."}'
        mock_post.return_value = fake_response

        with self.assertRaises(PrismaRateLimitError) as ctx:
            self.client.transcribe(audio_source=b"RIFFdummydata")

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("429", str(ctx.exception))
        self.assertIn("rate limited", str(ctx.exception).lower())
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    def test_transcribe_concurrency_lock_blocks_overlapping_request(self):
        """Verifies that the internal request lock prevents overlapping concurrent STT requests."""
        # Manually acquire the lock to simulate an active in-flight request
        acquired = PrismaClient._request_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Initial STT lock acquisition should succeed")
        try:
            self.assertTrue(PrismaClient.is_transcribing())
            self.assertTrue(self.client.is_busy)

            # Concurrent call must immediately raise PrismaRateLimitError without hitting network
            with self.assertRaises(PrismaRateLimitError) as ctx:
                self.client.transcribe(audio_source=b"RIFFdummydata")

            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("already in progress", str(ctx.exception).lower())
        finally:
            PrismaClient._request_lock.release()

        self.assertFalse(PrismaClient.is_transcribing())
        # Subsequent call after release succeeds in mock mode
        self.client.mock_mode = True
        res = self.client.transcribe(audio_source=b"RIFFdummydata")
        self.assertTrue(res["success"])


class TestTimbreClient(unittest.TestCase):

    def setUp(self):
        self.config = GnaniConfig(
            api_key="gnani-sahaayak-dev-test-key",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
            timbre_model="timbre-v2.5",
            timbre_voice="Nalini",
            timbre_language="hi-IN",
        )
        self.client = TimbreClient(config=self.config)

    def test_endpoint_url(self):
        """Verified official TTS inference endpoint URL."""
        self.assertEqual(self.client.endpoint_url, "https://api.vachana.ai/api/v1/tts/inference")

    def test_client_repr_masks_key(self):
        """Ensures TimbreClient repr masks secret."""
        repr_str = repr(self.client)
        self.assertNotIn("gnani-sahaayak-dev-test-key", repr_str)
        self.assertIn("gnan...-key", repr_str)

    def test_mock_mode_returns_wav_bytes(self):
        """Offline mock mode returns valid WAV header bytes without network calls."""
        mock_client = TimbreClient(config=self.config, mock_mode=True)
        audio_bytes = mock_client.synthesize("Aapka order confirm ho gaya hai.")
        self.assertTrue(audio_bytes.startswith(b"RIFF"))
        self.assertIn(b"WAVE", audio_bytes)

    def test_empty_text_raises_value_error(self):
        """Empty text raises ValueError immediately."""
        with self.assertRaises(ValueError):
            self.client.synthesize("")

    @patch("requests.post")
    def test_synthesize_success_flow(self, mock_post):
        """Verifies JSON request payload and binary audio retrieval."""
        fake_wav = b"RIFF1234WAVEfmt mock audio data"
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "audio/wav"}
        fake_response.content = fake_wav
        mock_post.return_value = fake_response

        text_to_speak = "Aapka order 320 rupaye ka hai."
        audio_result = self.client.synthesize(
            text=text_to_speak,
            voice="Nalini",
            language="hi-IN",
        )

        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.vachana.ai/api/v1/tts/inference")

        # Verify headers
        headers = call_kwargs["headers"]
        self.assertEqual(headers["X-API-Key-ID"], "gnani-sahaayak-dev-test-key")
        self.assertEqual(headers["Content-Type"], "application/json")

        # Verify JSON body
        payload = call_kwargs["json"]
        self.assertEqual(payload["text"], text_to_speak)
        self.assertEqual(payload["model"], "timbre-v2.5")
        self.assertEqual(payload["voice"], "Nalini")
        self.assertEqual(payload["language"], "hi-IN")
        self.assertIn("audio_config", payload)
        self.assertEqual(payload["audio_config"]["container"], "wav")

        # Verify return value is raw binary bytes
        self.assertEqual(audio_result, fake_wav)

    @patch("requests.post")
    def test_synthesize_error_status_handling(self, mock_post):
        """Verifies handling of HTTP 400 Bad Request error."""
        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.text = '{"error": "invalid_voice", "message": "Voice not found"}'
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Test text")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("400", str(ctx.exception))
        # Ensure secret is NOT in the error message
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_default_timeout_propagation(self, mock_post):
        """Verifies that TimbreClient propagates config.timbre_timeout tuple to requests.post."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "audio/wav"}
        fake_response.content = _MOCK_WAV_BYTES
        mock_post.return_value = fake_response

        self.client.synthesize("Namaste")
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["timeout"], (10.0, 60.0))

    @patch("requests.post")
    def test_synthesize_custom_timeout_propagation(self, mock_post):
        """Verifies that TimbreClient accepts a custom timeout tuple."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "audio/wav"}
        fake_response.content = _MOCK_WAV_BYTES
        mock_post.return_value = fake_response

        custom_client = TimbreClient(config=self.config, timeout=(3.0, 25.0))
        custom_client.synthesize("Namaste")
        _, call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs["timeout"], (3.0, 25.0))

    @patch("requests.post")
    def test_synthesize_connect_timeout_handling(self, mock_post):
        """Verifies ConnectTimeout is safely caught, wrapped in TimbreAPIError, and key is masked."""
        mock_post.side_effect = requests.exceptions.ConnectTimeout("Connect timed out after 10s")
        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertIn("Connect timed out after 10s", str(ctx.exception))
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_read_timeout_handling(self, mock_post):
        """Verifies ReadTimeout is safely caught, wrapped in TimbreAPIError, and key is masked."""
        mock_post.side_effect = requests.exceptions.ReadTimeout("Read timed out after 60s")
        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertIn("Read timed out after 60s", str(ctx.exception))
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_16khz_audio_config(self, mock_post):
        """Verifies that TimbreClient defaults to 16 kHz 16-bit mono PCM audio config."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "audio/wav"}
        fake_response.content = _MOCK_WAV_BYTES
        mock_post.return_value = fake_response

        self.client.synthesize("Testing sample rate")
        _, call_kwargs = mock_post.call_args
        cfg = call_kwargs["json"]["audio_config"]
        self.assertEqual(cfg["sample_rate"], 16000)
        self.assertEqual(cfg["num_channels"], 1)
        self.assertEqual(cfg["sample_width"], 2)
        self.assertEqual(cfg["encoding"], "linear_pcm")
        self.assertEqual(cfg["container"], "wav")

    @patch("requests.post")
    def test_synthesize_504_gateway_timeout(self, mock_post):
        """Verifies HTTP 504 Gateway Timeout raises TimbreAPIError with clear message and status."""
        fake_response = MagicMock()
        fake_response.status_code = 504
        fake_response.text = "<html><head><title>504 Gateway Time-out</title></head><body>504 Gateway Time-out</body></html>"
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertEqual(ctx.exception.status_code, 504)
        self.assertIn("504", str(ctx.exception))
        self.assertIn("gateway timeout", str(ctx.exception).lower())
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_html_response_handling(self, mock_post):
        """Verifies that an unexpected HTML response with HTTP 200 raises TimbreAPIError instead of audio."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        fake_response.text = "<html><body>Maintenance Page</body></html>"
        fake_response.content = b"<html><body>Maintenance Page</body></html>"
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertIn("HTML", str(ctx.exception))
        self.assertIn("Maintenance Page", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_json_response_handling(self, mock_post):
        """Verifies that a JSON error response with HTTP 200 raises TimbreAPIError."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "application/json"}
        fake_response.text = '{"error": "backend_overload", "message": "Inference queued"}'
        fake_response.content = b'{"error": "backend_overload", "message": "Inference queued"}'
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertIn("JSON", str(ctx.exception))
        self.assertIn("backend_overload", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_invalid_wav_header_raises_error(self, mock_post):
        """Verifies that non-WAV bytes without RIFF/WAVE header raise TimbreAPIError."""
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"Content-Type": "audio/wav"}
        fake_response.content = b"CORRUPTED_NON_WAV_BINARY_STREAM_DATA"
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreAPIError) as ctx:
            self.client.synthesize("Namaste")

        self.assertIn("missing RIFF/WAVE header", str(ctx.exception))

    @patch("requests.post")
    def test_synthesize_429_rate_limit(self, mock_post):
        """Verifies HTTP 429 Rate Limited raises TimbreRateLimitError with clear status and message."""
        fake_response = MagicMock()
        fake_response.status_code = 429
        fake_response.text = '{"error": "RATE_LIMITED", "message": "Only one active request allowed at a time."}'
        mock_post.return_value = fake_response

        with self.assertRaises(TimbreRateLimitError) as ctx:
            self.client.synthesize("Namaste")

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("429", str(ctx.exception))
        self.assertIn("rate limited", str(ctx.exception).lower())
        self.assertNotIn("gnani-sahaayak-dev-test-key", str(ctx.exception))

    def test_synthesize_concurrency_lock_blocks_overlapping_request(self):
        """Verifies that the internal request lock prevents overlapping concurrent requests."""
        # Manually acquire the lock to simulate an active in-flight request
        acquired = TimbreClient._request_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Initial lock acquisition should succeed")
        try:
            self.assertTrue(TimbreClient.is_synthesizing())
            self.assertTrue(self.client.is_busy)

            # Concurrent call must immediately raise TimbreRateLimitError without hitting network
            with self.assertRaises(TimbreRateLimitError) as ctx:
                self.client.synthesize("Concurrent speech")

            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("already in progress", str(ctx.exception).lower())
        finally:
            TimbreClient._request_lock.release()

        self.assertFalse(TimbreClient.is_synthesizing())
        # Subsequent call after release succeeds in mock mode
        self.client.mock_mode = True
        audio = self.client.synthesize("After release")
        self.assertEqual(audio, _MOCK_WAV_BYTES)


if __name__ == "__main__":
    unittest.main()
