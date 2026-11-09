"""
tests.test_inventory
~~~~~~~~~~~~~~~~~~~~
Unit tests for Local Inventory and Pricing, alias matching, unit conversion,
stock level checks, and stock deductions.
"""

import unittest

from gnani.inventory import InventoryItem, InventoryManager


class TestInventoryManager(unittest.TestCase):

    def setUp(self):
        # Create a controlled test inventory
        self.items = [
            InventoryItem("PROD-001", "Basmati Rice", "Grains", 60.0, "kg", 20.0, ["rice", "chawal"]),
            InventoryItem("PROD-002", "Sunflower Oil", "Oils", 140.0, "litre", 15.0, ["oil", "tel", "cooking oil"]),
            InventoryItem("PROD-003", "Refined Sugar", "Sweeteners", 42.0, "kg", 10.0, ["sugar", "cheeni"]),
            InventoryItem("PROD-004", "Parle-G Biscuits", "Snacks", 10.0, "packet", 5.0, ["biscuit", "biscuits"]),
        ]
        self.inventory = InventoryManager(items=self.items)

    def test_default_inventory_loads(self):
        """Default inventory loads items from sample_inventory.json."""
        default_inv = InventoryManager.default_inventory()
        items = default_inv.get_all_items()
        self.assertGreater(len(items), 5)
        # Check that Basmati Rice is present
        rice = default_inv.find_item("rice")
        self.assertIsNotNone(rice)
        self.assertEqual(rice.unit, "kg")

    def test_alias_matching(self):
        """Matches Hindi and vernacular aliases accurately."""
        self.assertEqual(self.inventory.find_item("rice").id, "PROD-001")
        self.assertEqual(self.inventory.find_item("chawal").id, "PROD-001")
        self.assertEqual(self.inventory.find_item("tel").id, "PROD-002")
        self.assertEqual(self.inventory.find_item("cheeni").id, "PROD-003")

    def test_pricing_and_total_calculation(self):
        """Calculates correct line item total for available stock."""
        res = self.inventory.check_and_price_item("rice", requested_qty=3.0, requested_unit="kg")
        self.assertTrue(res.is_available)
        self.assertEqual(res.unit_price, 60.0)
        self.assertEqual(res.normalized_quantity, 3.0)
        self.assertEqual(res.item_total, 180.0)  # 3 * 60

    def test_unit_conversion_grams_to_kg(self):
        """Converts grams to kilograms and calculates proportional price."""
        res = self.inventory.check_and_price_item("sugar", requested_qty=500.0, requested_unit="g")
        self.assertTrue(res.is_available)
        self.assertEqual(res.normalized_quantity, 0.5)
        self.assertEqual(res.item_total, 21.0)  # 0.5 * 42

    def test_insufficient_stock_detection(self):
        """Flags insufficient stock when requested quantity exceeds available stock."""
        # Available biscuit packets is 5.0, request 10.0
        res = self.inventory.check_and_price_item("biscuit", requested_qty=10.0, requested_unit="packet")
        self.assertEqual(res.status, "insufficient_stock")
        self.assertFalse(res.is_available)
        self.assertIn("Only 5", res.message)

    def test_unavailable_product(self):
        """Returns unavailable status for products not present in catalog."""
        res = self.inventory.check_and_price_item("imported avocado", requested_qty=1.0, requested_unit="piece")
        self.assertEqual(res.status, "unavailable")
        self.assertFalse(res.is_available)
        self.assertIn("not currently available", res.message)

    def test_stock_deduction_and_restore(self):
        """Stock can be deducted on confirmation and restored on cancellation."""
        initial_stock = self.inventory.find_item("PROD-001").available_quantity
        self.assertEqual(initial_stock, 20.0)

        # Deduct 5 kg
        success = self.inventory.deduct_stock("PROD-001", 5.0)
        self.assertTrue(success)
        self.assertEqual(self.inventory.find_item("PROD-001").available_quantity, 15.0)

        # Cannot deduct more than available
        over_deduct = self.inventory.deduct_stock("PROD-001", 20.0)
        self.assertFalse(over_deduct)

        # Restore stock
        self.inventory.restore_stock("PROD-001", 5.0)
        self.assertEqual(self.inventory.find_item("PROD-001").available_quantity, 20.0)


if __name__ == "__main__":
    unittest.main()

