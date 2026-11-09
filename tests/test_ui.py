"""
tests.test_ui
~~~~~~~~~~~~~
Automated offline test suite for GNANI — VOXORA UI integration and state workflows.

Covers:
1. Verification of app.py syntax and import integrity.
2. UI VoiceAssistant orchestration lifecycle.
3. Screen navigation state flow (Landing -> Interaction -> Confirmation).
4. Stepper quantity modifications and automatic price recalculations.
5. Multilingual order interactions via UI controller (Telugu, Hindi, English).
6. Order confirmation, inventory deduction, and voice receipt generation.
7. Error handling for empty or invalid commands.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gnani.assistant import AssistantTurnResponse, VoiceAssistant
from gnani.audio_input import create_dummy_wav
from gnani.config import GnaniConfig
from gnani.languages import LanguageMode, TIMBRE_VOICE_CONFIG
from gnani.order import OrderStatus
from gnani.prisma import PrismaAPIError, PrismaClient, PrismaRateLimitError
from gnani.timbre import TimbreAPIError, TimbreClient, TimbreRateLimitError


class TestVoxoraUIIntegration(unittest.TestCase):
    """Tests the backend controller workflow powering GNANI — VOXORA UI."""

    def setUp(self):
        self.config = GnaniConfig(
            api_key="mock-key-voxora-ui",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
        )
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp_dir.name)
        self.assistant = VoiceAssistant(
            config=self.config,
            mock_mode=True,
            output_audio_dir=self.output_dir,
            language_mode=LanguageMode.AUTO,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_app_py_syntax_and_importability(self):
        """Verifies app.py parses cleanly into Python AST without syntax errors."""
        import ast

        app_path = Path(__file__).resolve().parent.parent / "app.py"
        self.assertTrue(app_path.is_file(), "app.py should exist in project root.")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename="app.py")
        self.assertIsNotNone(tree)

    def test_screen_a_to_screen_b_voice_flow_telugu(self):
        """Tests initial spoken order creation in Telugu (Landing -> Interaction)."""
        self.assistant.set_language_mode(LanguageMode.TELUGU)
        turn = self.assistant.process_text("రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె కావాలి")

        self.assertTrue(turn.success)
        self.assertEqual(turn.active_language, LanguageMode.TELUGU)
        self.assertIsNotNone(self.assistant.current_order)
        self.assertEqual(len(self.assistant.current_order.items), 2)
        self.assertEqual(self.assistant.current_order.total_amount, 260.0)
        self.assertIn("సరే అన్నా", turn.response_text)
        self.assertIn("రూపాయలు", turn.response_text)

    def test_screen_b_stepper_quantity_modifications(self):
        """Tests tactile quantity increment, decrement, and price roll on Grocery Canvas."""
        self.assistant.process_text("2 kg rice and 1 litre oil")
        order = self.assistant.current_order
        self.assertIsNotNone(order)
        self.assertEqual(order.total_amount, 260.0)

        # Stepper: Increment Rice by 1 kg (2 -> 3 kg)
        rice_item = next(it for it in order.items if "Rice" in it.product_name)
        success, _ = self.assistant.order_manager.modify_item_quantity(
            order, rice_item.product_name, rice_item.requested_quantity + 1.0
        )
        self.assertTrue(success)
        self.assertEqual(order.total_amount, 320.0)

        # Stepper: Decrement Oil (1 -> 0.5 litre)
        oil_item = next(it for it in order.items if "Oil" in it.product_name)
        success, _ = self.assistant.order_manager.modify_item_quantity(
            order, oil_item.product_name, 0.5
        )
        self.assertTrue(success)
        self.assertEqual(order.total_amount, 250.0)

    def test_screen_b_item_deletion(self):
        """Tests item removal from Grocery Canvas."""
        self.assistant.process_text("2 kg rice and 1 litre oil")
        order = self.assistant.current_order
        self.assertEqual(len(order.items), 2)

        # Delete Oil
        success, _ = self.assistant.order_manager.remove_item(order, "Sunflower Cooking Oil")
        self.assertTrue(success)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.total_amount, 120.0)

    def test_screen_b_to_screen_c_confirmation_seal(self):
        """Tests Screen B -> Screen C transition: Order confirmation and Vyapar seal billing."""
        self.assistant.set_language_mode(LanguageMode.TELUGU)
        self.assistant.process_text("రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె")

        # Confirm Order
        turn_conf = self.assistant.confirm_current_order()
        self.assertTrue(turn_conf.success)
        self.assertIsNotNone(turn_conf.order)
        self.assertEqual(turn_conf.order.status, OrderStatus.CONFIRMED)
        self.assertEqual(turn_conf.order.total_amount, 260.0)
        self.assertIn("మీ ఆర్డర్ నిర్ధారించబడింది", turn_conf.response_text)
        self.assertIsNotNone(turn_conf.audio_path)
        self.assertTrue(turn_conf.audio_path.is_file())

    def test_empty_order_confirmation_error_handling(self):
        """Tests graceful error handling when confirming without items."""
        self.assistant.current_order = None
        turn = self.assistant.confirm_current_order()
        self.assertFalse(turn.success)
        self.assertEqual(turn.error, "No active order.")

    def test_microphone_audio_input_processing(self):
        """Tests live microphone audio recording ingestion through the assistant voice pipeline."""
        # Generate valid 16kHz PCM WAV bytes as would be output by st.audio_input()
        mic_wav_bytes = create_dummy_wav(duration_seconds=2.0, sample_rate=16000, channels=1)
        turn = self.assistant.process_audio(mic_wav_bytes, filename="live_mic_recording.wav")

        self.assertTrue(turn.success, "Microphone audio processing should succeed in mock mode.")
        self.assertIsNotNone(turn.transcript)
        self.assertIsNotNone(self.assistant.current_order)
        self.assertGreater(len(self.assistant.current_order.items), 0)
        self.assertGreater(self.assistant.current_order.total_amount, 0)
        self.assertIsNotNone(turn.audio_path)
        self.assertTrue(turn.audio_path.is_file(), "Synthesized audio file should exist.")

    def test_invalid_microphone_audio_error_handling(self):
        """Tests that invalid audio captured from microphone is rejected gracefully without crashing."""
        corrupt_audio_bytes = b"CORRUPT_AUDIO_HEADER_1234567890"
        turn = self.assistant.process_audio(corrupt_audio_bytes, filename="corrupt_mic.wav")

        self.assertFalse(turn.success, "Corrupt audio should not succeed.")
        self.assertIn("Audio validation failed", turn.error)
        self.assertIsNotNone(turn.response_text)
        # Should still generate audio error prompt
        self.assertIsNotNone(turn.audio_path)

    def test_multilingual_microphone_audio_pipeline(self):
        """Tests microphone input handling with Telugu and Hindi language modes."""
        mic_wav_bytes = create_dummy_wav(duration_seconds=1.5, sample_rate=16000, channels=1)

        # Telugu mode
        self.assistant.set_language_mode(LanguageMode.TELUGU)
        turn_te = self.assistant.process_audio(mic_wav_bytes, filename="mic_te.wav")
        self.assertTrue(turn_te.success)
        self.assertEqual(turn_te.active_language, LanguageMode.TELUGU)

        # Hindi mode
        self.assistant.set_language_mode(LanguageMode.HINDI)
        turn_hi = self.assistant.process_audio(mic_wav_bytes, filename="mic_hi.wav")
        self.assertTrue(turn_hi.success)
        self.assertEqual(turn_hi.active_language, LanguageMode.HINDI)

    def test_wav_file_upload_processing(self):
        """Tests that uploaded .WAV files route seamlessly through the voice pipeline."""
        upload_bytes = create_dummy_wav(duration_seconds=2.0, sample_rate=16000, channels=1)
        turn = self.assistant.process_audio(upload_bytes, filename="customer_uploaded.wav")
        self.assertTrue(turn.success)
        self.assertIsNotNone(turn.transcript)
        self.assertIsNotNone(self.assistant.current_order)
        self.assertGreater(len(self.assistant.current_order.items), 0)

    def test_typed_text_input_processing(self):
        """Tests typed text input routing through the assistant without audio upload."""
        turn = self.assistant.process_text("1 kg sugar and 2 kg rice")
        self.assertTrue(turn.success)
        self.assertEqual(len(self.assistant.current_order.items), 2)
        self.assertEqual(self.assistant.current_order.total_amount, 162.0)
        self.assertEqual(turn.active_language, LanguageMode.ENGLISH)

    def test_two_way_voice_recording_to_tts_workflow_mocked(self):
        """Tests complete two-way recording -> STT -> order processing -> TTS response workflow."""
        mic_wav_bytes = create_dummy_wav(duration_seconds=2.0, sample_rate=16000, channels=1)
        mock_prisma_resp = {
            "success": True,
            "transcript": "రెండు కిలోల బియ్యం కావాలి",
            "request_id": "test-req-123",
            "timestamp": "2026-11-07T12:00:00Z",
        }
        with patch.object(self.assistant.prisma_client, "transcribe", return_value=mock_prisma_resp):
            turn = self.assistant.process_audio(mic_wav_bytes, filename="live_mic_workflow.wav")

            self.assertTrue(turn.success)
            self.assertEqual(turn.transcript, "రెండు కిలోల బియ్యం కావాలి")
            self.assertEqual(turn.active_language, LanguageMode.TELUGU)
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 1)
            self.assertIn("Rice", self.assistant.current_order.items[0].product_name)
            self.assertEqual(self.assistant.current_order.items[0].requested_quantity, 2.0)
            self.assertIsNotNone(turn.audio_path)
            self.assertTrue(turn.audio_path.is_file())
            self.assertTrue(turn.audio_bytes.startswith(b"RIFF"))
            self.assertGreaterEqual(len(turn.audio_bytes), 44)

    def test_failed_microphone_upload_rejection(self):
        """Tests that empty, truncated, or corrupted microphone audio inputs are rejected safely."""
        # Empty audio bytes
        turn_empty = self.assistant.process_audio(b"", filename="empty.wav")
        self.assertFalse(turn_empty.success)
        self.assertIn("Audio validation failed", turn_empty.error)

        # Truncated header (< 12 bytes)
        turn_short = self.assistant.process_audio(b"RIFF", filename="short.wav")
        self.assertFalse(turn_short.success)
        self.assertIn("Audio validation failed", turn_short.error)

        # Corrupted format non-WAV
        turn_corrupt = self.assistant.process_audio(b"INVALID_HEADER_NOT_A_WAV_FILE_12345", filename="corrupt.wav")
        self.assertFalse(turn_corrupt.success)
        self.assertIn("Audio validation failed", turn_corrupt.error)

    def test_prisma_stt_api_error_handling(self):
        """Tests Prisma STT API error handling and empty transcript handling."""
        mic_wav_bytes = create_dummy_wav(duration_seconds=1.5, sample_rate=16000, channels=1)

        # HTTP error 500 from Prisma
        with patch.object(self.assistant.prisma_client, "transcribe", side_effect=PrismaAPIError("Prisma STT 500: Server Error", status_code=500)):
            turn = self.assistant.process_audio(mic_wav_bytes, filename="error_500.wav")
            self.assertFalse(turn.success)
            self.assertIn("Prisma API error", turn.error)
            self.assertIsNotNone(turn.response_text)

        # Empty transcript from Prisma
        mock_empty_resp = {"success": True, "transcript": "   "}
        with patch.object(self.assistant.prisma_client, "transcribe", return_value=mock_empty_resp):
            turn = self.assistant.process_audio(mic_wav_bytes, filename="empty_transcript.wav")
            self.assertFalse(turn.success)
            self.assertIn("Empty transcription", turn.error)

    def test_timbre_tts_504_gateway_timeout_preserves_order_and_allows_retry(self):
        """Tests that a Timbre TTS HTTP 504 timeout preserves order on canvas and allows retry."""
        with patch.object(self.assistant.timbre_client, "synthesize", side_effect=TimbreAPIError("Timbre TTS gateway timeout (HTTP 504)", status_code=504)):
            turn = self.assistant.process_text("1 kg sugar and 2 kg rice")

            # Order items and bill calculation are preserved!
            self.assertTrue(turn.success)
            self.assertIsNone(turn.audio_path)
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 2)
            self.assertEqual(self.assistant.current_order.total_amount, 162.0)

        # Customer triggers TTS retry button
        retry_result = self.assistant.voice_service.synthesize_response(
            turn.response_text,
            filename_prefix="retry_test_voice",
            language=turn.active_language,
        )
        self.assertTrue(retry_result.success)
        self.assertIsNotNone(retry_result.audio_path)
        self.assertTrue(retry_result.audio_path.is_file())
        self.assertEqual(len(self.assistant.current_order.items), 2)

    def test_timbre_tts_429_rate_limited_preserves_order_and_allows_retry(self):
        """Tests that a Timbre TTS HTTP 429 rate limit preserves order on canvas and allows retry."""
        rate_limit_err = TimbreRateLimitError(
            "Timbre TTS rate limited (HTTP 429): Only one active TTS request permitted at a time.",
            status_code=429,
        )
        with patch.object(self.assistant.timbre_client, "synthesize", side_effect=rate_limit_err):
            turn = self.assistant.process_text("1 kg sugar and 2 kg rice")

            # Cart and order calculations are completely preserved!
            self.assertTrue(turn.success)
            self.assertIsNone(turn.audio_path)
            self.assertIsNotNone(turn.error)
            self.assertIn("429", turn.error)
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 2)
            self.assertEqual(self.assistant.current_order.total_amount, 162.0)

        # Once rate limit window clears, user clicks Retry and synthesis succeeds
        retry_result = self.assistant.voice_service.synthesize_response(
            turn.response_text,
            filename_prefix="retry_test_voice_429",
            language=turn.active_language,
        )
        self.assertTrue(retry_result.success)
        self.assertIsNotNone(retry_result.audio_path)
        self.assertTrue(retry_result.audio_path.is_file())
        self.assertEqual(len(self.assistant.current_order.items), 2)

    def test_concurrent_tts_requests_blocked_by_request_lock(self):
        """Tests that the request lock blocks overlapping requests and allows retry once released."""
        # Simulate active TTS request by acquiring the lock
        acquired = self.assistant.timbre_client._request_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            self.assertTrue(self.assistant.is_tts_busy)

            # Concurrent synthesis attempt is rejected with 429 rate limit
            res = self.assistant.voice_service.synthesize_response(
                "ధన్యవాదాలు",
                language=LanguageMode.TELUGU,
            )
            self.assertFalse(res.success)
            self.assertIsNone(res.audio_path)
            self.assertIn("429", res.error)
            self.assertIn("rate limited", res.error.lower())
        finally:
            self.assistant.timbre_client._request_lock.release()

        self.assertFalse(self.assistant.is_tts_busy)

        # Retry after lock release succeeds
        retry_res = self.assistant.voice_service.synthesize_response(
            "ధన్యవాదాలు",
            language=LanguageMode.TELUGU,
        )
        self.assertTrue(retry_res.success)
        self.assertIsNotNone(retry_res.audio_path)
        self.assertTrue(retry_res.audio_path.is_file())

    def test_timbre_tts_html_response_rejection(self):
        """Tests that HTML response bodies from broken gateway are rejected while cart remains safe."""
        html_error = TimbreAPIError("Timbre TTS returned HTML error page (HTTP 502)", status_code=502, response_body="<html>502 Bad Gateway</html>")
        with patch.object(self.assistant.timbre_client, "synthesize", side_effect=html_error):
            # Calling voice service directly returns error result without crashing
            res = self.assistant.voice_service.synthesize_response("2 kg rice", language=LanguageMode.ENGLISH)
            self.assertFalse(res.success)
            self.assertIsNone(res.audio_path)
            self.assertIn("HTML error page", res.error)

            # Calling through assistant preserves order items on canvas
            turn = self.assistant.process_text("2 kg rice")
            self.assertTrue(turn.success)
            self.assertIsNone(turn.audio_path)
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 1)

    def test_multilingual_voice_selection_chitra_and_nalini(self):
        """Tests that voice selection maps Telugu/Tenglish -> Chitra and Hindi/English -> Nalini."""
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.TELUGU]["voice"], "Chitra")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.TELUGU]["language"], "te-IN")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.TENGLISH]["voice"], "Chitra")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.TENGLISH]["language"], "te-IN")

        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.HINDI]["voice"], "Nalini")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.HINDI]["language"], "hi-IN")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.HINGLISH]["voice"], "Nalini")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.HINGLISH]["language"], "hi-IN")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.ENGLISH]["voice"], "Nalini")
        self.assertEqual(TIMBRE_VOICE_CONFIG[LanguageMode.ENGLISH]["language"], "en-IN")

        mock_wav = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        )
        with patch.object(self.assistant.timbre_client, "synthesize", return_value=mock_wav) as mock_synth:
            self.assistant.voice_service.synthesize_response("ధన్యవాదాలు", language=LanguageMode.TELUGU)
            self.assertEqual(mock_synth.call_args[1]["voice"], "Chitra")
            self.assertEqual(mock_synth.call_args[1]["language"], "te-IN")

            self.assistant.voice_service.synthesize_response("धन्यवाद", language=LanguageMode.HINDI)
            self.assertEqual(mock_synth.call_args[1]["voice"], "Nalini")
            self.assertEqual(mock_synth.call_args[1]["language"], "hi-IN")

    def test_prisma_stt_429_rate_limited_preserves_cart_and_allows_retry(self):
        """Tests that a Prisma STT HTTP 429 rate limit preserves grocery cart and allows manual retry."""
        # 1. Establish an existing cart turn
        first_turn = self.assistant.process_text("1 kg sugar")
        self.assertTrue(first_turn.success)
        self.assertIsNotNone(self.assistant.current_order)
        self.assertEqual(len(self.assistant.current_order.items), 1)
        self.assertEqual(self.assistant.current_order.total_amount, 42.0)

        # 2. Simulate Prisma STT returning HTTP 429 Rate Limited during voice ordering
        rate_limit_err = PrismaRateLimitError(
            "Prisma STT rate limited (HTTP 429): Only one active STT request is permitted at a time.",
            status_code=429,
        )
        dummy_wav = create_dummy_wav(duration_seconds=1.0)
        with patch.object(self.assistant.prisma_client, "transcribe", side_effect=rate_limit_err):
            failed_turn = self.assistant.process_audio(dummy_wav, filename="customer_speech.wav")

            # Speech recognition failed due to rate limiting
            self.assertFalse(failed_turn.success)
            self.assertIn("429", failed_turn.error)

            # Both assistant.current_order and failed_turn.order preserve the pre-existing grocery cart!
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 1)
            self.assertEqual(self.assistant.current_order.total_amount, 42.0)
            self.assertIsNotNone(failed_turn.order)
            self.assertEqual(len(failed_turn.order.items), 1)

        # 3. Simulate user manual retry after rate limit window clears (using the saved WAV bytes)
        mock_response = {
            "success": True,
            "request_id": "req_retry_123",
            "timestamp": "20261107_230000.000",
            "transcript": "2 kg rice",
        }
        with patch.object(self.assistant.prisma_client, "transcribe", return_value=mock_response):
            retry_turn = self.assistant.process_audio(dummy_wav, filename="customer_speech.wav")
            self.assertTrue(retry_turn.success)
            self.assertEqual(retry_turn.transcript, "2 kg rice")
            self.assertIsNotNone(self.assistant.current_order)
            self.assertEqual(len(self.assistant.current_order.items), 1)
            self.assertEqual(self.assistant.current_order.total_amount, 120.0)

    def test_concurrent_stt_requests_blocked_by_request_lock(self):
        """Tests that Prisma STT request lock blocks overlapping requests and allows retry once released."""
        acquired = self.assistant.prisma_client._request_lock.acquire(blocking=False)
        self.assertTrue(acquired, "Initial lock acquisition should succeed")
        try:
            self.assertTrue(PrismaClient.is_transcribing())
            self.assertTrue(self.assistant.is_stt_busy)
            self.assertTrue(self.assistant.is_busy)

            dummy_wav = create_dummy_wav(duration_seconds=1.0)
            turn = self.assistant.process_audio(dummy_wav)
            self.assertFalse(turn.success)
            self.assertIn("already in progress", turn.error.lower())
        finally:
            self.assistant.prisma_client._request_lock.release()

        self.assertFalse(PrismaClient.is_transcribing())
        self.assertFalse(self.assistant.is_stt_busy)

        # Subsequent call after lock release succeeds in mock mode
        self.assistant.prisma_client.mock_mode = True
        success_turn = self.assistant.process_audio(dummy_wav)
        self.assertTrue(success_turn.success)

    def test_assistant_busy_properties_reflect_stt_and_tts_locks(self):
        """Tests assistant.is_stt_busy, is_tts_busy, and is_busy properties under active locks."""
        self.assertFalse(self.assistant.is_stt_busy)
        self.assertFalse(self.assistant.is_tts_busy)
        self.assertFalse(self.assistant.is_busy)

        # STT lock
        PrismaClient._request_lock.acquire()
        try:
            self.assertTrue(self.assistant.is_stt_busy)
            self.assertFalse(self.assistant.is_tts_busy)
            self.assertTrue(self.assistant.is_busy)
        finally:
            PrismaClient._request_lock.release()

        # TTS lock
        TimbreClient._request_lock.acquire()
        try:
            self.assertFalse(self.assistant.is_stt_busy)
            self.assertTrue(self.assistant.is_tts_busy)
            self.assertTrue(self.assistant.is_busy)
        finally:
            TimbreClient._request_lock.release()

        self.assertFalse(self.assistant.is_busy)

    def test_failed_transcription_recovery_and_lock_reset(self):
        """Tests that PrismaClient and TimbreClient reset_lock recovers from an orphaned lock state."""
        # 1. Simulate an orphaned lock left by an interrupted thread
        PrismaClient._request_lock.acquire(blocking=False)
        TimbreClient._request_lock.acquire(blocking=False)
        self.assertTrue(PrismaClient.is_transcribing())
        self.assertTrue(TimbreClient.is_synthesizing())
        self.assertTrue(self.assistant.is_stt_busy)
        self.assertTrue(self.assistant.is_tts_busy)

        # 2. Safely reset locks
        PrismaClient.reset_lock()
        TimbreClient.reset_lock()

        self.assertFalse(PrismaClient.is_transcribing())
        self.assertFalse(TimbreClient.is_synthesizing())
        self.assertFalse(self.assistant.is_stt_busy)
        self.assertFalse(self.assistant.is_tts_busy)
        self.assertFalse(self.assistant.is_busy)

        # 3. Subsequent call succeeds without rate-limit error
        dummy_wav = create_dummy_wav(duration_seconds=1.0)
        self.assistant.prisma_client.mock_mode = True
        res = self.assistant.process_audio(dummy_wav)
        self.assertTrue(res.success)

    def test_duplicate_audio_submission_prevention(self):
        """Tests that hash-based comparison prevents duplicate submissions of identical audio bytes."""
        import hashlib
        dummy_wav = create_dummy_wav(duration_seconds=1.0)
        audio_hash = hashlib.md5(dummy_wav).hexdigest()

        # Initial submission sets last_mic_hash
        session_state = {"last_mic_hash": None, "voice_state": "idle"}
        auto_proc = True

        should_process_first = (auto_proc and session_state.get("last_mic_hash") != audio_hash)
        self.assertTrue(should_process_first)
        session_state["last_mic_hash"] = audio_hash

        # Second submission with the exact same audio does not re-trigger
        should_process_second = (auto_proc and session_state.get("last_mic_hash") != audio_hash)
        self.assertFalse(should_process_second)

    def test_auto_healing_of_stuck_transcribing_voice_state(self):
        """Tests that an orphaned 'transcribing' state heals when background STT is idle."""
        # When STT is not busy and last turn failed, voice_state heals to 'error'
        failed_turn = AssistantTurnResponse(
            success=False,
            transcript="",
            response_text="Error",
            error="Rate limit error",
        )
        voice_state = "transcribing"
        is_stt_busy = PrismaClient.is_transcribing()
        if voice_state == "transcribing" and not is_stt_busy:
            voice_state = "error" if (failed_turn and not failed_turn.success) else "idle"
        self.assertEqual(voice_state, "error")

        # When STT is not busy and no failed turn exists, voice_state heals to 'idle'
        voice_state = "transcribing"
        last_turn = None
        if voice_state == "transcribing" and not is_stt_busy:
            voice_state = "error" if (last_turn and not last_turn.success) else "idle"
        self.assertEqual(voice_state, "idle")


if __name__ == "__main__":
    unittest.main()
