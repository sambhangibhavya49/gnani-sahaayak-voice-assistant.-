"""
tests.test_extractor
~~~~~~~~~~~~~~~~~~~~
Unit tests for Product and Quantity Extraction, number word parsing,
multilingual unit canonicalization, and ambiguity detection.
"""

import unittest

from gnani.extractor import DeterministicProductExtractor


class TestProductExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = DeterministicProductExtractor()

    def test_single_item_extraction_english(self):
        """Extracts standard product, word quantity, and unit."""
        res = self.extractor.extract("two kilos of rice")
        self.assertEqual(len(res.items), 1)
        item = res.items[0]
        self.assertEqual(item.raw_product.lower(), "rice")
        self.assertEqual(item.quantity, 2.0)
        self.assertEqual(item.unit, "kg")
        self.assertFalse(item.is_ambiguous)

    def test_multiple_items_in_one_sentence(self):
        """Example from prompt: 'Two kilos of rice and one litre of oil.'"""
        res = self.extractor.extract("Two kilos of rice and one litre of oil.")
        self.assertEqual(len(res.items), 2)
        
        rice_item = res.items[0]
        self.assertEqual(rice_item.raw_product.lower(), "rice")
        self.assertEqual(rice_item.quantity, 2.0)
        self.assertEqual(rice_item.unit, "kg")

        oil_item = res.items[1]
        self.assertEqual(oil_item.raw_product.lower(), "oil")
        self.assertEqual(oil_item.quantity, 1.0)
        self.assertEqual(oil_item.unit, "litre")

    def test_multilingual_hindi_hinglish_numerals(self):
        """Extracts items with Hindi numbers 'ek', 'do', and 'aur'."""
        transcript = "Anna, two kilos of rice, one litre of oil, aur ek kilo sugar."
        res = self.extractor.extract(transcript)
        self.assertEqual(len(res.items), 3)

        self.assertEqual(res.items[0].raw_product.lower(), "rice")
        self.assertEqual(res.items[0].quantity, 2.0)
        self.assertEqual(res.items[0].unit, "kg")

        self.assertEqual(res.items[1].raw_product.lower(), "oil")
        self.assertEqual(res.items[1].quantity, 1.0)
        self.assertEqual(res.items[1].unit, "litre")

        self.assertEqual(res.items[2].raw_product.lower(), "sugar")
        self.assertEqual(res.items[2].quantity, 1.0)
        self.assertEqual(res.items[2].unit, "kg")

    def test_fractional_quantities(self):
        """Parses 'half', 'one and a half', and decimal numbers."""
        res = self.extractor.extract("half kg toor dal and 1.5 litre milk")
        self.assertEqual(len(res.items), 2)

        self.assertEqual(res.items[0].raw_product.lower(), "toor dal")
        self.assertEqual(res.items[0].quantity, 0.5)
        self.assertEqual(res.items[0].unit, "kg")

        self.assertEqual(res.items[1].raw_product.lower(), "milk")
        self.assertEqual(res.items[1].quantity, 1.5)
        self.assertEqual(res.items[1].unit, "litre")

    def test_packet_and_piece_units(self):
        """Parses discrete package units like packets and boxes."""
        res = self.extractor.extract("3 packets parle-g biscuit and 2 boxes tea")
        self.assertEqual(len(res.items), 2)

        self.assertEqual(res.items[0].raw_product.lower(), "parle-g biscuit")
        self.assertEqual(res.items[0].quantity, 3.0)
        self.assertEqual(res.items[0].unit, "packet")

        self.assertEqual(res.items[1].raw_product.lower(), "tea")
        self.assertEqual(res.items[1].quantity, 2.0)
        self.assertEqual(res.items[1].unit, "box")

    def test_ambiguity_missing_quantity(self):
        """Asks for clarification when product is named without quantity."""
        res = self.extractor.extract("please give me sugar")
        self.assertEqual(len(res.items), 1)
        item = res.items[0]
        self.assertTrue(item.is_ambiguous)
        self.assertIsNone(item.quantity)
        self.assertIn("how much sugar", item.clarification_prompt.lower())
        self.assertTrue(res.has_ambiguities)
        self.assertGreater(len(res.clarifications), 0)

    def test_ambiguity_missing_unit(self):
        """Asks for clarification when number is provided but unit is omitted."""
        res = self.extractor.extract("two milk")
        self.assertEqual(len(res.items), 1)
        item = res.items[0]
        self.assertTrue(item.is_ambiguous)
        self.assertEqual(item.quantity, 2.0)
        self.assertIsNone(item.unit)
        self.assertIn("specify the unit", item.clarification_prompt.lower())

    def test_empty_transcript(self):
        """Empty transcript returns empty ExtractionResult."""
        res = self.extractor.extract("")
        self.assertEqual(len(res.items), 0)
        self.assertFalse(res.has_ambiguities)


if __name__ == "__main__":
    unittest.main()

