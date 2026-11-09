"""
tests.test_order
~~~~~~~~~~~~~~~~
Unit tests for Order lifecycle, bill calculation, confirmation,
and item modifications/corrections.
"""

import unittest

from gnani.extractor import DeterministicProductExtractor
from gnani.inventory import InventoryItem, InventoryManager
from gnani.order import OrderManager, OrderStatus


class TestOrderManager(unittest.TestCase):

    def setUp(self):
        items = [
            InventoryItem("PROD-001", "Basmati Rice", "Grains", 60.0, "kg", 20.0, ["rice", "chawal"]),
            InventoryItem("PROD-002", "Sunflower Oil", "Oils", 140.0, "litre", 15.0, ["oil", "tel"]),
            InventoryItem("PROD-003", "Refined Sugar", "Sweeteners", 40.0, "kg", 10.0, ["sugar", "cheeni"]),
        ]
        self.inventory = InventoryManager(items=items)
        self.order_mgr = OrderManager(inventory=self.inventory)
        self.extractor = DeterministicProductExtractor()

    def test_order_creation_and_bill_calculation(self):
        """Creates order and computes grand total for 'Two kilos of rice and one litre of oil.'"""
        ext = self.extractor.extract("Two kilos of rice and one litre of oil.")
        order = self.order_mgr.create_order_from_extraction(ext)

        self.assertEqual(order.status, OrderStatus.PENDING_CONFIRMATION)
        self.assertEqual(len(order.items), 2)
        # Rice: 2 kg * 60 = 120
        # Oil: 1 litre * 140 = 140
        # Total: 260
        self.assertEqual(order.total_amount, 260.0)

    def test_order_confirmation_deducts_stock(self):
        """Confirming an order deducts inventory stock and locks status."""
        ext = self.extractor.extract("2 kg rice")
        order = self.order_mgr.create_order_from_extraction(ext)

        initial_rice_stock = self.inventory.find_item("PROD-001").available_quantity
        self.assertEqual(initial_rice_stock, 20.0)

        success, msg = self.order_mgr.confirm_order(order)
        self.assertTrue(success)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertIn("confirmed successfully", msg.lower())

        # Stock reduced from 20 to 18
        remaining = self.inventory.find_item("PROD-001").available_quantity
        self.assertEqual(remaining, 18.0)

    def test_modify_item_quantity_and_recalculate(self):
        """Modifying item quantity updates item total and overall bill."""
        ext = self.extractor.extract("2 kg rice and 1 kg sugar")
        order = self.order_mgr.create_order_from_extraction(ext)
        # 2*60 + 1*40 = 120 + 40 = 160
        self.assertEqual(order.total_amount, 160.0)

        # User corrects: change rice to 3 kilos
        success, msg = self.order_mgr.modify_item_quantity(order, "rice", new_quantity=3.0)
        self.assertTrue(success)
        # 3*60 + 1*40 = 180 + 40 = 220
        self.assertEqual(order.total_amount, 220.0)

    def test_remove_item_and_recalculate(self):
        """Removing an item recalculates the bill accurately."""
        ext = self.extractor.extract("2 kg rice and 1 litre oil")
        order = self.order_mgr.create_order_from_extraction(ext)
        self.assertEqual(order.total_amount, 260.0)

        # Remove oil
        success, msg = self.order_mgr.remove_item(order, "oil")
        self.assertTrue(success)
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.total_amount, 120.0)

    def test_add_new_item_to_order(self):
        """Adding a product to existing order updates items and total."""
        ext = self.extractor.extract("2 kg rice")
        order = self.order_mgr.create_order_from_extraction(ext)
        self.assertEqual(order.total_amount, 120.0)

        # Add 1 kg sugar
        success, msg = self.order_mgr.add_item(order, "sugar", quantity=1.0, unit="kg")
        self.assertTrue(success)
        self.assertEqual(len(order.items), 2)
        self.assertEqual(order.total_amount, 160.0)

    def test_natural_language_correction(self):
        """Handles conversational correction phrase 'Remove oil'."""
        ext = self.extractor.extract("2 kg rice and 1 litre oil")
        order = self.order_mgr.create_order_from_extraction(ext)
        self.assertEqual(order.total_amount, 260.0)

        success, msg = self.order_mgr.apply_natural_correction(order, "Remove oil", self.extractor)
        self.assertTrue(success)
        self.assertEqual(order.total_amount, 120.0)
        self.assertIn("Removed", msg)


if __name__ == "__main__":
    unittest.main()

