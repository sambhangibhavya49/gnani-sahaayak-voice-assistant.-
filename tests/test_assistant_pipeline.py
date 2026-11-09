"""
tests.test_assistant_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
End-to-end integration tests for VoiceAssistant core pipeline
using offline mocked services (zero live network traffic).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gnani.audio_input import create_dummy_wav
from gnani.assistant import VoiceAssistant
from gnani.config import GnaniConfig
from gnani.order import OrderStatus
from gnani.timbre import TimbreAPIError


class TestVoiceAssistantPipeline(unittest.TestCase):

    def setUp(self):
        self.config = GnaniConfig(
            api_key="mock-api-key-12345",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
            prisma_language="hi-IN",
            timbre_model="timbre-v2.5",
            timbre_voice="Nalini",
        )
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_audio_path = Path(self.tmp_dir.name)

        # Initialize assistant in mock_mode=True
        self.assistant = VoiceAssistant(
            config=self.config,
            mock_mode=True,
            output_audio_dir=self.output_audio_path,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_complete_voice_pipeline_flow(self):
        """
        Tests the complete voice pipeline end-to-end:
        WAV Audio -> STT (mock returns 'two kilos of rice, one litre of oil')
        -> Extraction -> Inventory pricing -> Order created -> TTS synthesized & saved.
        """
        # Patch Prisma mock return to custom order transcript
        with patch.object(
            self.assistant.prisma_client,
            "transcribe",
            return_value={
                "success": True,
                "request_id": "test_req_101",
                "timestamp": "20261030_120000",
                "transcript": "Two kilos of rice and one litre of oil.",
            },
        ):
            dummy_wav = create_dummy_wav(duration_seconds=1.5, sample_rate=16000)
            res = self.assistant.process_audio(audio_source=dummy_wav, filename="order.wav")

            # 1. Pipeline success
            self.assertTrue(res.success)
            self.assertEqual(res.transcript, "Two kilos of rice and one litre of oil.")

            # 2. Order verification
            self.assertIsNotNone(res.order)
            self.assertEqual(res.order.status, OrderStatus.PENDING_CONFIRMATION)
            self.assertEqual(len(res.order.items), 2)
            # Rice: 2 * 60 = 120, Oil: 1 * 140 = 140 -> Total: 260
            self.assertEqual(res.order.total_amount, 260.0)

            # 3. Spoken summary verification
            self.assertIn("260 rupees", res.response_text)
            self.assertIn("confirm", res.response_text.lower())

            # 4. Audio output verification
            self.assertIsNotNone(res.audio_path)
            self.assertTrue(res.audio_path.exists())
            self.assertGreater(res.audio_path.stat().st_size, 0)

    def test_order_confirmation_flow(self):
        """Tests conversational order confirmation via assistant."""
        # 1. Place initial order via text
        order_res = self.assistant.process_text("2 kg rice and 1 kg sugar")
        self.assertTrue(order_res.success)
        self.assertEqual(order_res.order.total_amount, 162.0)  # 2*60 + 1*42 = 162

        # 2. Confirm order
        confirm_res = self.assistant.confirm_current_order()
        self.assertTrue(confirm_res.success)
        self.assertEqual(confirm_res.order.status, OrderStatus.CONFIRMED)
        self.assertIn("confirmed", confirm_res.response_text.lower())
        self.assertIsNotNone(confirm_res.audio_path)
        self.assertTrue(confirm_res.audio_path.exists())

    def test_order_correction_flow(self):
        """Tests conversational modification of order items and bill recalculation."""
        # Initial order: 2 kg rice (120) and 1 litre oil (140) = 260
        self.assistant.process_text("2 kg rice and 1 litre oil")
        self.assertEqual(self.assistant.current_order.total_amount, 260.0)

        # Correction: change rice to 3 kilos
        corr_res = self.assistant.correct_current_order("Change rice to 3 kilos")
        self.assertTrue(corr_res.success)
        # 3*60 + 140 = 320
        self.assertEqual(corr_res.order.total_amount, 320.0)
        self.assertIn("320 rupees", corr_res.response_text)
        self.assertIsNotNone(corr_res.audio_path)

    def test_audio_validation_failure_handling(self):
        """Corrupted/non-WAV audio returns friendly failure without crashing."""
        corrupted_bytes = b"NOT_A_WAV_HEADER"
        res = self.assistant.process_audio(audio_source=corrupted_bytes)

        self.assertFalse(res.success)
        self.assertIn("audio validation failed", res.error.lower())
        self.assertIn("sorry", res.response_text.lower())

    def test_graceful_handling_of_tts_failure(self):
        """When Timbre TTS throws TimbreAPIError, order logic and text summary remain intact."""
        with patch.object(
            self.assistant.timbre_client,
            "synthesize",
            side_effect=TimbreAPIError("TTS quota exceeded", status_code=429),
        ):
            res = self.assistant.process_text("1 kg rice")
            # Text summary is generated even if audio synthesis failed
            self.assertTrue(res.success)
            self.assertIn("60 rupees", res.response_text)
            self.assertIsNone(res.audio_path)

    def test_conversational_confirmation_via_process_text(self):
        """Tests confirming pending order by saying 'Yes' / 'Confirm'."""
        self.assistant.process_text("2 kg rice")
        self.assertEqual(self.assistant.current_order.status, OrderStatus.PENDING_CONFIRMATION)

        confirm_turn = self.assistant.process_text("Yes please confirm")
        self.assertTrue(confirm_turn.success)
        self.assertEqual(self.assistant.current_order.status, OrderStatus.CONFIRMED)
        self.assertEqual(confirm_turn.transcript, "Yes please confirm")
        self.assertIn("confirmed", confirm_turn.response_text.lower())
        self.assertIsNotNone(confirm_turn.audio_path)

    def test_conversational_rejection_via_process_text(self):
        """Tests cancelling pending order by saying 'No' / 'Cancel'."""
        self.assistant.process_text("2 kg rice")
        self.assertEqual(self.assistant.current_order.status, OrderStatus.PENDING_CONFIRMATION)

        cancel_turn = self.assistant.process_text("No cancel order")
        self.assertTrue(cancel_turn.success)
        self.assertEqual(self.assistant.current_order.status, OrderStatus.CANCELLED)
        self.assertEqual(cancel_turn.transcript, "No cancel order")
        self.assertIn("cancelled", cancel_turn.response_text.lower())
        self.assertIsNotNone(cancel_turn.audio_path)

    def test_unrecognized_input_preserves_pending_order(self):
        """Unrecognized speech during pending confirmation does not discard current order."""
        self.assistant.process_text("2 kg rice")
        self.assertEqual(self.assistant.current_order.status, OrderStatus.PENDING_CONFIRMATION)
        initial_order_id = self.assistant.current_order.order_id

        turn = self.assistant.process_text("What time do you close?")
        self.assertTrue(turn.success)
        self.assertEqual(self.assistant.current_order.status, OrderStatus.PENDING_CONFIRMATION)
        self.assertEqual(self.assistant.current_order.order_id, initial_order_id)
        self.assertIn("120 rupees", turn.response_text)

    def test_multilingual_conversational_confirmations(self):
        """Tests conversational confirmations across Hindi, Telugu, and English."""
        # Telugu confirmation
        self.assistant.set_language_mode("te")
        self.assistant.process_text("రెండు కిలోల బియ్యం")
        res_te = self.assistant.process_text("సరే అన్నా")
        self.assertTrue(res_te.success)
        self.assertEqual(self.assistant.current_order.status, OrderStatus.CONFIRMED)
        self.assertIn("నిర్ధారించబడింది", res_te.response_text)

        # Hindi rejection
        self.assistant.set_language_mode("hi")
        self.assistant.process_text("दो किलो चावल")
        res_hi = self.assistant.process_text("नहीं कैंसिल कर दो")
        self.assertTrue(res_hi.success)
        self.assertEqual(self.assistant.current_order.status, OrderStatus.CANCELLED)
        self.assertIn("रद्द", res_hi.response_text)


if __name__ == "__main__":
    unittest.main()

