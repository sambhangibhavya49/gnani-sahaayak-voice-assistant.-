"""
gnani.order
~~~~~~~~~~~
Order Processing, Confirmation, and Correction Management.

Manages:
- Conversion of extracted items into structured Order with pricing.
- Recalculation of item totals and grand total bill.
- Order state transitions (PENDING_CONFIRMATION, CONFIRMED, CANCELLED).
- User corrections: modifying quantities, adding items, removing items.
- Handling natural language correction commands (e.g. "change rice to 3 kilos", "remove oil").
- Inventory stock reservation / deduction upon confirmation.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from .extractor import BaseProductExtractor, ExtractionResult
from .inventory import InventoryManager


class OrderStatus(str, Enum):
    """Lifecycle status of a customer order."""
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderItem:
    """An individual line item within an order."""
    product_id: Optional[str]
    product_name: str
    requested_quantity: float
    requested_unit: str
    normalized_quantity: float
    inventory_unit: str
    unit_price: float
    item_total: float
    status: str  # 'available', 'insufficient_stock', 'unavailable', 'incompatible_unit', 'ambiguous'
    note: str = ""

    @property
    def is_billable(self) -> bool:
        """Only available items with non-zero quantity are billable."""
        return self.status == "available" and self.normalized_quantity > 0


@dataclass
class Order:
    """Complete customer order representation."""
    order_id: str
    items: List[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING_CONFIRMATION
    total_amount: float = 0.0
    clarifications_needed: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_all_available(self) -> bool:
        """True if every item in the order is fully in stock and priced."""
        if not self.items:
            return False
        return all(it.status == "available" for it in self.items) and not self.clarifications_needed


class OrderManager:
    """Handles order creation, stock verification, recalculation, confirmation, and corrections."""

    def __init__(self, inventory: InventoryManager):
        self.inventory = inventory

    def create_order_from_extraction(
        self,
        extraction: ExtractionResult,
        order_id: Optional[str] = None,
    ) -> Order:
        """
        Creates an Order from an ExtractionResult, looking up items in inventory
        and computing prices and line totals.
        """
        oid = order_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order = Order(order_id=oid)

        # Collect extraction-level ambiguities
        for clarification in extraction.clarifications:
            order.clarifications_needed.append(clarification)

        for item in extraction.items:
            if item.is_ambiguous or item.quantity is None:
                order_item = OrderItem(
                    product_id=None,
                    product_name=item.raw_product,
                    requested_quantity=item.quantity or 0.0,
                    requested_unit=item.unit or "",
                    normalized_quantity=0.0,
                    inventory_unit="",
                    unit_price=0.0,
                    item_total=0.0,
                    status="ambiguous",
                    note=item.clarification_prompt or "Quantity or unit unspecified.",
                )
                order.items.append(order_item)
                continue

            stock_res = self.inventory.check_and_price_item(
                product_name=item.raw_product,
                requested_qty=item.quantity,
                requested_unit=item.unit,
            )

            if stock_res.is_available and stock_res.item:
                order_item = OrderItem(
                    product_id=stock_res.item.id,
                    product_name=stock_res.item.name,
                    requested_quantity=stock_res.requested_quantity,
                    requested_unit=stock_res.requested_unit,
                    normalized_quantity=stock_res.normalized_quantity,
                    inventory_unit=stock_res.item.unit,
                    unit_price=stock_res.unit_price,
                    item_total=stock_res.item_total,
                    status="available",
                    note="In stock",
                )
            elif stock_res.status == "insufficient_stock" and stock_res.item:
                order_item = OrderItem(
                    product_id=stock_res.item.id,
                    product_name=stock_res.item.name,
                    requested_quantity=stock_res.requested_quantity,
                    requested_unit=stock_res.requested_unit,
                    normalized_quantity=stock_res.normalized_quantity,
                    inventory_unit=stock_res.item.unit,
                    unit_price=stock_res.unit_price,
                    item_total=0.0,
                    status="insufficient_stock",
                    note=stock_res.message,
                )
            else:
                order_item = OrderItem(
                    product_id=None,
                    product_name=item.raw_product,
                    requested_quantity=stock_res.requested_quantity,
                    requested_unit=stock_res.requested_unit,
                    normalized_quantity=0.0,
                    inventory_unit="",
                    unit_price=0.0,
                    item_total=0.0,
                    status=stock_res.status,
                    note=stock_res.message,
                )

            order.items.append(order_item)

        self.recalculate(order)
        return order

    def recalculate(self, order: Order) -> Order:
        """Recalculates the grand total amount and updates timestamp."""
        total = sum(item.item_total for item in order.items if item.is_billable)
        order.total_amount = round(total, 2)
        order.updated_at = datetime.now(timezone.utc).isoformat()
        return order

    def confirm_order(self, order: Order) -> Tuple[bool, str]:
        """
        Confirms the order and permanently deducts available stock from inventory.
        """
        if order.status == OrderStatus.CONFIRMED:
            return True, f"Order {order.order_id} is already confirmed."

        if order.status == OrderStatus.CANCELLED:
            return False, f"Order {order.order_id} has been cancelled and cannot be confirmed."

        if not order.items:
            return False, "Cannot confirm an empty order."

        # Check if any billable items can be deducted
        billable_items = [it for it in order.items if it.is_billable]
        if not billable_items:
            return False, "Order contains no in-stock billable items."

        # Verify stock one more time before deduction
        for it in billable_items:
            if it.product_id:
                inv_item = self.inventory.find_item(it.product_id)
                if not inv_item or inv_item.available_quantity < it.normalized_quantity:
                    return False, f"Insufficient stock for {it.product_name} during checkout."

        # Apply deductions
        for it in billable_items:
            if it.product_id:
                self.inventory.deduct_stock(it.product_id, it.normalized_quantity)

        order.status = OrderStatus.CONFIRMED
        order.updated_at = datetime.now(timezone.utc).isoformat()
        return True, f"Order {order.order_id} confirmed successfully. Total: Rs. {order.total_amount:g}."

    def cancel_order(self, order: Order) -> Tuple[bool, str]:
        """Cancels an order."""
        if order.status == OrderStatus.CONFIRMED:
            # If already confirmed, restore stock
            for it in order.items:
                if it.is_billable and it.product_id:
                    self.inventory.restore_stock(it.product_id, it.normalized_quantity)

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc).isoformat()
        return True, f"Order {order.order_id} has been cancelled."

    def modify_item_quantity(
        self,
        order: Order,
        product_query: str,
        new_quantity: float,
        new_unit: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Updates the quantity and optionally unit of an existing item in the order.
        """
        target_idx = None
        cand_item = self.inventory.find_item(product_query)
        for i, item in enumerate(order.items):
            if cand_item and item.product_id == cand_item.id:
                target_idx = i
                break
            # Check match against item name or product_query
            if (
                product_query.lower() in item.product_name.lower()
                or item.product_name.lower() in product_query.lower()
            ):
                target_idx = i
                break

        if target_idx is None:
            return False, f"Product '{product_query}' not found in current order."

        effective_unit = new_unit or order.items[target_idx].requested_unit
        stock_res = self.inventory.check_and_price_item(
            product_name=product_query,
            requested_qty=new_quantity,
            requested_unit=effective_unit,
        )

        if stock_res.is_available and stock_res.item:
            order.items[target_idx] = OrderItem(
                product_id=stock_res.item.id,
                product_name=stock_res.item.name,
                requested_quantity=stock_res.requested_quantity,
                requested_unit=stock_res.requested_unit,
                normalized_quantity=stock_res.normalized_quantity,
                inventory_unit=stock_res.item.unit,
                unit_price=stock_res.unit_price,
                item_total=stock_res.item_total,
                status="available",
                note="Quantity updated.",
            )
            self.recalculate(order)
            return True, f"Updated {stock_res.item.name} to {new_quantity:g} {effective_unit}. New total: Rs. {order.total_amount:g}."
        elif stock_res.status == "insufficient_stock" and stock_res.item:
            order.items[target_idx] = OrderItem(
                product_id=stock_res.item.id,
                product_name=stock_res.item.name,
                requested_quantity=stock_res.requested_quantity,
                requested_unit=stock_res.requested_unit,
                normalized_quantity=stock_res.normalized_quantity,
                inventory_unit=stock_res.item.unit,
                unit_price=stock_res.unit_price,
                item_total=0.0,
                status="insufficient_stock",
                note=stock_res.message,
            )
            self.recalculate(order)
            return False, stock_res.message
        else:
            return False, stock_res.message

    def remove_item(self, order: Order, product_query: str) -> Tuple[bool, str]:
        """Removes a product from the current order."""
        cand_item = self.inventory.find_item(product_query)
        for i, item in enumerate(order.items):
            if (
                (cand_item and item.product_id == cand_item.id)
                or product_query.lower() in item.product_name.lower()
                or item.product_name.lower() in product_query.lower()
            ):
                removed = order.items.pop(i)
                self.recalculate(order)
                return True, f"Removed {removed.product_name} from the order. New total: Rs. {order.total_amount:g}."

        return False, f"Product '{product_query}' not found in current order."

    def add_item(
        self,
        order: Order,
        product_name: str,
        quantity: float,
        unit: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Adds a new item to the order."""
        stock_res = self.inventory.check_and_price_item(
            product_name=product_name,
            requested_qty=quantity,
            requested_unit=unit,
        )

        if stock_res.is_available and stock_res.item:
            order.items.append(
                OrderItem(
                    product_id=stock_res.item.id,
                    product_name=stock_res.item.name,
                    requested_quantity=stock_res.requested_quantity,
                    requested_unit=stock_res.requested_unit,
                    normalized_quantity=stock_res.normalized_quantity,
                    inventory_unit=stock_res.item.unit,
                    unit_price=stock_res.unit_price,
                    item_total=stock_res.item_total,
                    status="available",
                    note="Added item.",
                )
            )
            self.recalculate(order)
            return True, f"Added {stock_res.item.name} ({quantity:g} {unit or stock_res.item.unit}) for Rs. {stock_res.item_total:g}. Total: Rs. {order.total_amount:g}."
        elif stock_res.status == "insufficient_stock" and stock_res.item:
            order.items.append(
                OrderItem(
                    product_id=stock_res.item.id,
                    product_name=stock_res.item.name,
                    requested_quantity=quantity,
                    requested_unit=unit or stock_res.item.unit,
                    normalized_quantity=stock_res.normalized_quantity,
                    inventory_unit=stock_res.item.unit,
                    unit_price=stock_res.unit_price,
                    item_total=0.0,
                    status="insufficient_stock",
                    note=stock_res.message,
                )
            )
            self.recalculate(order)
            return False, stock_res.message
        else:
            return False, stock_res.message

    def apply_natural_correction(
        self,
        order: Order,
        correction_text: str,
        extractor: BaseProductExtractor,
    ) -> Tuple[bool, str]:
        """
        Parses conversational correction intents such as:
        - "Remove oil" / "Hata do tel" / "Delete sugar"
        - "Change rice to 3 kilos" / "Rice ko 3 kg kar do" / "Make sugar 2 kg"
        - "Add 1 litre milk" / "Ek litre doodh aur add karo"
        """
        text = correction_text.strip().lower()

        # Intent 1: Remove / Delete
        remove_match = re.search(
            r"\b(?:remove|delete|cancel|hata|hatao|mat lo|tiseyi|teeseyi|vaddu|తొలగించు|తీసివేయి|వద్దు|हटाओ|हटा दो)\s+(?:of\s+)?(.+)",
            text,
        )
        if remove_match:
            prod = remove_match.group(1).replace("please", "").strip()
            return self.remove_item(order, prod)

        # Intent 2: Modify / Change
        change_match = re.search(
            r"\b(?:change|make|set|badlo|karo|marchu|మార్చు|बदलो)\s+(.+?)\s+(?:to|ko|as|గా|కి|లోనికి)\s+(.+)",
            text,
        )
        if change_match:
            prod = change_match.group(1).strip()
            spec = change_match.group(2).strip()
            extracted = extractor.extract(f"{spec} of {prod}")
            if extracted.items and extracted.items[0].quantity is not None:
                item = extracted.items[0]
                return self.modify_item_quantity(order, prod, item.quantity, item.unit)

        # Intent 3: Add new item
        add_match = re.search(r"\b(?:add|plus|aur|inka|మరియు|ఇంకా|और|जोड़ो)\s+(.+)", text)
        if add_match:
            spec = add_match.group(1).strip()
            extracted = extractor.extract(spec)
            if extracted.items and extracted.items[0].quantity is not None:
                item = extracted.items[0]
                return self.add_item(order, item.raw_product, item.quantity, item.unit)

        # Fallback: Extract via standard extractor and apply items
        extracted = extractor.extract(correction_text)
        if extracted.items:
            for item in extracted.items:
                if item.quantity is not None:
                    matched_inv = self.inventory.find_item(item.raw_product)
                    existing = any(
                        (matched_inv and it.product_id == matched_inv.id)
                        or (item.raw_product.lower() in it.product_name.lower())
                        or (it.product_name.lower() in item.raw_product.lower())
                        for it in order.items
                    )
                    if existing:
                        return self.modify_item_quantity(order, item.raw_product, item.quantity, item.unit)
                    else:
                        return self.add_item(order, item.raw_product, item.quantity, item.unit)

        return False, f"Could not understand correction: '{correction_text}'. Please say e.g. 'Change rice to 3 kilos' or 'Remove oil'."
