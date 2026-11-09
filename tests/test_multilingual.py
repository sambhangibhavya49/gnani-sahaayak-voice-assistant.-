"""
tests.test_multilingual
~~~~~~~~~~~~~~~~~~~~~~~
Automated offline test suite for multilingual and code-mixed conversation support
in Gnani Sahaayak Voice Assistant.

Covers:
1. Telugu-only input (script)
2. Hindi-only input (script)
3. English-only input
4. Hinglish input (Hindi + English)
5. Tenglish input (Telugu + English)
6. Romanized Telugu
7. Romanized Hindi
8. Mixed three-language input (Telugu + Hindi + English)
9. Multilingual grocery product extraction & inventory mapping
10. Multilingual quantity normalization (అర కిలో, పావు కిలో, కిలోన్నర, aadha kilo, dedh kilo, etc.)
11. Language preference persistence across conversation turns
12. Multilingual order summaries & confirmations (Telugu, Hindi, English, Hinglish, Tenglish)
"""

import tempfile
import unittest
from pathlib import Path

from gnani.assistant import VoiceAssistant
from gnani.config import GnaniConfig
from gnani.extractor import DeterministicProductExtractor
from gnani.inventory import InventoryManager
from gnani.languages import LanguageMode
from gnani.order import OrderManager, OrderStatus


class TestMultilingualExtractionAndNormalization(unittest.TestCase):
    """Tests product extraction, quantity normalization, and code-mixed understanding."""

    def setUp(self):
        self.extractor = DeterministicProductExtractor()
        self.inventory = InventoryManager.default_inventory()

    def test_telugu_only_script_input(self):
        """1. Telugu-only input in Telugu script: రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె."""
        transcript = "రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె"
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)

        # Item 1: Rice
        self.assertEqual(res.items[0].quantity, 2.0)
        self.assertEqual(res.items[0].unit, "kg")
        inv_item1 = self.inventory.find_item(res.items[0].raw_product)
        self.assertIsNotNone(inv_item1)
        self.assertEqual(inv_item1.id, "PROD-001")  # Basmati Rice

        # Item 2: Oil
        self.assertEqual(res.items[1].quantity, 1.0)
        self.assertEqual(res.items[1].unit, "litre")
        inv_item2 = self.inventory.find_item(res.items[1].raw_product)
        self.assertIsNotNone(inv_item2)
        self.assertEqual(inv_item2.id, "PROD-002")  # Cooking Oil

    def test_hindi_only_script_input(self):
        """2. Hindi-only input in Devanagari script: दो किलो चावल और एक लीटर तेल देना."""
        transcript = "दो किलो चावल और एक लीटर तेल देना"
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)

        # Item 1: Rice
        self.assertEqual(res.items[0].quantity, 2.0)
        self.assertEqual(res.items[0].unit, "kg")
        inv1 = self.inventory.find_item(res.items[0].raw_product)
        self.assertIsNotNone(inv1)
        self.assertEqual(inv1.id, "PROD-001")

        # Item 2: Oil
        self.assertEqual(res.items[1].quantity, 1.0)
        self.assertEqual(res.items[1].unit, "litre")
        inv2 = self.inventory.find_item(res.items[1].raw_product)
        self.assertIsNotNone(inv2)
        self.assertEqual(inv2.id, "PROD-002")

    def test_english_only_input(self):
        """3. English-only input: Two kilos of rice and one litre of oil."""
        transcript = "Two kilos of rice and one litre of oil."
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)
        self.assertEqual(res.items[0].quantity, 2.0)
        self.assertEqual(res.items[0].unit, "kg")
        self.assertEqual(res.items[1].quantity, 1.0)
        self.assertEqual(res.items[1].unit, "litre")

    def test_hinglish_input(self):
        """4. Hinglish input: Bhai, ek kilo rice aur half kilo sugar dena."""
        transcript = "Bhai, ek kilo rice aur half kilo sugar dena."
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)

        # Rice
        self.assertEqual(res.items[0].quantity, 1.0)
        self.assertEqual(res.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res.items[0].raw_product).id, "PROD-001")

        # Sugar
        self.assertEqual(res.items[1].quantity, 0.5)
        self.assertEqual(res.items[1].unit, "kg")
        self.assertEqual(self.inventory.find_item(res.items[1].raw_product).id, "PROD-003")

    def test_tenglish_input_variations(self):
        """5. Tenglish input: Telugu + English code-switching."""
        # Example A: "Anna, two kilos biyyam kavali."
        res_a = self.extractor.extract("Anna, two kilos biyyam kavali.")
        self.assertEqual(len(res_a.items), 1)
        self.assertEqual(res_a.items[0].quantity, 2.0)
        self.assertEqual(res_a.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res_a.items[0].raw_product).id, "PROD-001")

        # Example B: "అన్నా, one packet oil మరియు two kilos rice ఇవ్వండి."
        res_b = self.extractor.extract("అన్నా, one packet oil మరియు two kilos rice ఇవ్వండి.")
        self.assertEqual(len(res_b.items), 2)
        self.assertEqual(res_b.items[0].quantity, 1.0)
        self.assertEqual(res_b.items[0].unit, "packet")
        self.assertEqual(self.inventory.find_item(res_b.items[0].raw_product).id, "PROD-002")
        self.assertEqual(res_b.items[1].quantity, 2.0)
        self.assertEqual(res_b.items[1].unit, "kg")
        self.assertEqual(self.inventory.find_item(res_b.items[1].raw_product).id, "PROD-001")

        # Example C: "Anna, sugar one kilo, oil half litre kavali."
        res_c = self.extractor.extract("Anna, sugar one kilo, oil half litre kavali.")
        self.assertEqual(len(res_c.items), 2)
        self.assertEqual(res_c.items[0].quantity, 1.0)
        self.assertEqual(res_c.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res_c.items[0].raw_product).id, "PROD-003")
        self.assertEqual(res_c.items[1].quantity, 0.5)
        self.assertEqual(res_c.items[1].unit, "litre")
        self.assertEqual(self.inventory.find_item(res_c.items[1].raw_product).id, "PROD-002")

    def test_romanized_telugu_input(self):
        """6. Romanized Telugu: 'rendu kilo biyyam mariyu ara litre noone'."""
        transcript = "rendu kilo biyyam mariyu ara litre noone"
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)

        self.assertEqual(res.items[0].quantity, 2.0)
        self.assertEqual(res.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res.items[0].raw_product).id, "PROD-001")

        self.assertEqual(res.items[1].quantity, 0.5)
        self.assertEqual(res.items[1].unit, "litre")
        self.assertEqual(self.inventory.find_item(res.items[1].raw_product).id, "PROD-002")

    def test_romanized_hindi_input(self):
        """7. Romanized Hindi: 'aadha kilo cheeni aur do kilo chawal'."""
        transcript = "aadha kilo cheeni aur do kilo chawal"
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 2)

        self.assertEqual(res.items[0].quantity, 0.5)
        self.assertEqual(res.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res.items[0].raw_product).id, "PROD-003")

        self.assertEqual(res.items[1].quantity, 2.0)
        self.assertEqual(res.items[1].unit, "kg")
        self.assertEqual(self.inventory.find_item(res.items[1].raw_product).id, "PROD-001")

    def test_mixed_three_language_input(self):
        """8. Mixed 3-language input: Telugu + Hindi + English."""
        # "Mujhe rendu kilo rice chahiye."
        res1 = self.extractor.extract("Mujhe rendu kilo rice chahiye.")
        self.assertEqual(len(res1.items), 1)
        self.assertEqual(res1.items[0].quantity, 2.0)
        self.assertEqual(res1.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res1.items[0].raw_product).id, "PROD-001")

        # "Anna, two kilos biyyam aur ek kilo sugar dena."
        res2 = self.extractor.extract("Anna, two kilos biyyam aur ek kilo sugar dena.")
        self.assertEqual(len(res2.items), 2)
        self.assertEqual(res2.items[0].quantity, 2.0)
        self.assertEqual(res2.items[0].unit, "kg")
        self.assertEqual(self.inventory.find_item(res2.items[0].raw_product).id, "PROD-001")
        self.assertEqual(res2.items[1].quantity, 1.0)
        self.assertEqual(res2.items[1].unit, "kg")
        self.assertEqual(self.inventory.find_item(res2.items[1].raw_product).id, "PROD-003")

    def test_multilingual_grocery_name_mappings(self):
        """9. All spellings in Telugu, Hindi, and English map to the same catalog product."""
        # Rice: బియ్యం / biyyam / चावल / chawal / rice -> PROD-001
        for alias in ["బియ్యం", "biyyam", "चावल", "chawal", "rice"]:
            item = self.inventory.find_item(alias)
            self.assertIsNotNone(item, f"Failed to find item for '{alias}'")
            self.assertEqual(item.id, "PROD-001")

        # Dal: పప్పు / pappu / दाल / dal -> PROD-005
        for alias in ["పప్పు", "pappu", "दाल", "dal"]:
            item = self.inventory.find_item(alias)
            self.assertIsNotNone(item, f"Failed to find item for '{alias}'")
            self.assertEqual(item.id, "PROD-005")

        # Sugar: పంచదార / panchadara / चीनी / sugar -> PROD-003
        for alias in ["పంచదార", "panchadara", "चीनी", "sugar"]:
            item = self.inventory.find_item(alias)
            self.assertIsNotNone(item, f"Failed to find item for '{alias}'")
            self.assertEqual(item.id, "PROD-003")

        # Oil: నూనె / noone / तेल / oil -> PROD-002
        for alias in ["నూనె", "noone", "तेल", "oil"]:
            item = self.inventory.find_item(alias)
            self.assertIsNotNone(item, f"Failed to find item for '{alias}'")
            self.assertEqual(item.id, "PROD-002")

        # Salt: ఉప్పు / uppu / नमक / salt -> PROD-009
        for alias in ["ఉప్పు", "uppu", "नमक", "salt"]:
            item = self.inventory.find_item(alias)
            self.assertIsNotNone(item, f"Failed to find item for '{alias}'")
            self.assertEqual(item.id, "PROD-009")

    def test_multilingual_quantity_normalization(self):
        """10. Support expressions: అర కిలో, పావు కిలో, కిలోన్నర, dedh kilo, aadha kilo, అర లీటర్."""
        # అర కిలో -> 0.5 kg
        res = self.extractor.extract("అర కిలో పంచదార")
        self.assertEqual(res.items[0].quantity, 0.5)
        self.assertEqual(res.items[0].unit, "kg")

        # పావు కిలో -> 0.25 kg
        res = self.extractor.extract("పావు కిలో టీ పొడి")
        self.assertEqual(res.items[0].quantity, 0.25)
        self.assertEqual(res.items[0].unit, "kg")

        # కిలోన్నర -> 1.5 kg
        res = self.extractor.extract("కిలోన్నర బియ్యం")
        self.assertEqual(res.items[0].quantity, 1.5)
        self.assertEqual(res.items[0].unit, "kg")

        # dedh kilo -> 1.5 kg
        res = self.extractor.extract("dedh kilo chawal")
        self.assertEqual(res.items[0].quantity, 1.5)
        self.assertEqual(res.items[0].unit, "kg")

        # aadha kilo -> 0.5 kg
        res = self.extractor.extract("aadha kilo toor dal")
        self.assertEqual(res.items[0].quantity, 0.5)
        self.assertEqual(res.items[0].unit, "kg")

        # అర లీటర్ -> 0.5 litre
        res = self.extractor.extract("అర లీటర్ నూనె")
        self.assertEqual(res.items[0].quantity, 0.5)
        self.assertEqual(res.items[0].unit, "litre")


class TestMultilingualAssistantAndLanguagePersistence(unittest.TestCase):
    """Tests language detection, preference persistence, and response generation."""

    def setUp(self):
        self.config = GnaniConfig(
            api_key="mock-api-key-multilingual",
            base_url="https://api.vachana.ai",
            auth_header="X-API-Key-ID",
            prisma_language="hi-IN",
            timbre_model="timbre-v2.5",
            timbre_voice="Nalini",
        )
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_audio_path = Path(self.tmp_dir.name)
        self.assistant = VoiceAssistant(
            config=self.config,
            mock_mode=True,
            output_audio_dir=self.output_audio_path,
            language_mode=LanguageMode.AUTO,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_language_preference_persistence_manual_telugu(self):
        """11. Setting language to Telugu is maintained throughout all multi-turn interactions."""
        self.assistant.set_language_mode(LanguageMode.TELUGU)
        self.assertEqual(self.assistant.get_language_mode(), LanguageMode.TELUGU)

        # Turn 1: Order
        t1 = self.assistant.process_text("రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె")
        self.assertTrue(t1.success)
        self.assertEqual(t1.active_language, LanguageMode.TELUGU)
        self.assertIn("సరే అన్నా", t1.response_text)
        self.assertIn("రూపాయలు", t1.response_text)
        self.assertEqual(len(t1.normalized_items), 2)

        # Turn 2: Natural Correction
        t2 = self.assistant.correct_current_order("బియ్యం 3 కిలోలు చేయండి")
        self.assertTrue(t2.success)
        self.assertEqual(t2.active_language, LanguageMode.TELUGU)
        self.assertIn("రూపాయలు", t2.response_text)

        # Turn 3: Confirmation
        t3 = self.assistant.confirm_current_order()
        self.assertTrue(t3.success)
        self.assertEqual(t3.active_language, LanguageMode.TELUGU)
        self.assertIn("మీ ఆర్డర్ నిర్ధారించబడింది", t3.response_text)
        self.assertEqual(t3.order.status, OrderStatus.CONFIRMED)

    def test_language_preference_persistence_manual_hindi(self):
        """11B. Setting language to Hindi persists across order creation and confirmation."""
        self.assistant.set_language_mode(LanguageMode.HINDI)
        self.assertEqual(self.assistant.get_language_mode(), LanguageMode.HINDI)

        t1 = self.assistant.process_text("दो किलो चावल और एक लीटर तेल देना")
        self.assertTrue(t1.success)
        self.assertEqual(t1.active_language, LanguageMode.HINDI)
        self.assertIn("ठीक है", t1.response_text)
        self.assertIn("रुपये", t1.response_text)

        t2 = self.assistant.confirm_current_order()
        self.assertTrue(t2.success)
        self.assertEqual(t2.active_language, LanguageMode.HINDI)
        self.assertIn("आपका ऑर्डर कन्फर्म हो गया है", t2.response_text)

    def test_multilingual_order_summaries_all_modes(self):
        """12. Verifies order summaries in Telugu, Hindi, English, Hinglish, and Tenglish."""
        order_mgr = OrderManager(self.assistant.inventory)
        extractor = DeterministicProductExtractor()
        extracted = extractor.extract("2 kg rice and 1 litre oil")
        order = order_mgr.create_order_from_extraction(extracted)

        voice_service = self.assistant.voice_service

        # Telugu
        te_sum = voice_service.generate_order_summary(order, language=LanguageMode.TELUGU)
        self.assertIn("సరే అన్నా", te_sum)
        self.assertIn("రూపాయలు", te_sum)

        # Hindi
        hi_sum = voice_service.generate_order_summary(order, language=LanguageMode.HINDI)
        self.assertIn("ठीक है", hi_sum)
        self.assertIn("रुपये", hi_sum)

        # English
        en_sum = voice_service.generate_order_summary(order, language=LanguageMode.ENGLISH)
        self.assertIn("You ordered", en_sum)
        self.assertIn("260 rupees", en_sum)

        # Hinglish
        hing_sum = voice_service.generate_order_summary(order, language=LanguageMode.HINGLISH)
        self.assertIn("Theek hai", hing_sum)
        self.assertIn("Total bill", hing_sum)

        # Tenglish
        teng_sum = voice_service.generate_order_summary(order, language=LanguageMode.TENGLISH)
        self.assertIn("Sare anna", teng_sum)
        self.assertIn("Total bill", teng_sum)

    def test_task2_five_multilingual_input_styles_and_auto_detection(self):
        """Verifies end-to-end processing across all 5 requested language styles with auto detection."""
        test_cases = [
            {
                "input": "అన్నా రెండు కిలోల బియ్యం కావాలి",
                "expected_lang": LanguageMode.TELUGU,
                "expected_items": [("Basmati Rice", 2.0, "kg", 120.0)],
                "expected_voice": "Chitra",
                "expected_tts_lang": "te-IN",
            },
            {
                "input": "Anna, two kilos biyyam kavali",
                "expected_lang": LanguageMode.TENGLISH,
                "expected_items": [("Basmati Rice", 2.0, "kg", 120.0)],
                "expected_voice": "Chitra",
                "expected_tts_lang": "te-IN",
            },
            {
                "input": "भैया, एक किलो चावल देना",
                "expected_lang": LanguageMode.HINDI,
                "expected_items": [("Basmati Rice", 1.0, "kg", 60.0)],
                "expected_voice": "Nalini",
                "expected_tts_lang": "hi-IN",
            },
            {
                "input": "Bhai, ek kilo rice aur half kilo sugar dena",
                "expected_lang": LanguageMode.HINGLISH,
                "expected_items": [("Basmati Rice", 1.0, "kg", 60.0), ("Refined Sugar", 0.5, "kg", 21.0)],
                "expected_voice": "Nalini",
                "expected_tts_lang": "hi-IN",
            },
            {
                "input": "I need two kilos of rice",
                "expected_lang": LanguageMode.ENGLISH,
                "expected_items": [("Basmati Rice", 2.0, "kg", 120.0)],
                "expected_voice": "Nalini",
                "expected_tts_lang": "en-IN",
            },
        ]

        for tc in test_cases:
            # Fresh assistant instance per test case in Auto mode
            asst = VoiceAssistant(
                config=self.config,
                mock_mode=True,
                output_audio_dir=self.output_audio_path,
                language_mode=LanguageMode.AUTO,
            )
            res = asst.process_text(tc["input"])

            # 1. Preserves transcript
            self.assertEqual(res.transcript, tc["input"])
            self.assertTrue(res.success)

            # 2. Consistent language detection
            self.assertEqual(res.active_language, tc["expected_lang"])

            # 3. Item identification and quantity normalization
            self.assertIsNotNone(res.order)
            self.assertEqual(len(res.order.items), len(tc["expected_items"]))

            for idx, (exp_name, exp_qty, exp_unit, exp_total) in enumerate(tc["expected_items"]):
                item = res.order.items[idx]
                self.assertEqual(item.product_name, exp_name)
                self.assertEqual(item.requested_quantity, exp_qty)
                self.assertEqual(item.inventory_unit, exp_unit)
                self.assertEqual(item.item_total, exp_total)

            # 4. Correct voice mapping for language
            from gnani.languages import TIMBRE_VOICE_CONFIG
            voice_cfg = TIMBRE_VOICE_CONFIG[res.active_language]
            self.assertEqual(voice_cfg["voice"], tc["expected_voice"])
            self.assertEqual(voice_cfg["language"], tc["expected_tts_lang"])

            # 5. Order remains active in PENDING_CONFIRMATION state with audio generated
            self.assertEqual(res.order.status, OrderStatus.PENDING_CONFIRMATION)
            self.assertIsNotNone(res.audio_path)


if __name__ == "__main__":
    unittest.main()

