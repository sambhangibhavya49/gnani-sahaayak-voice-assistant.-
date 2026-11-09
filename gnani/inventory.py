"""
gnani.inventory
~~~~~~~~~~~~~~~
Local Kirana Inventory and Pricing Manager.

Provides:
- In-memory inventory catalog with sample staple products.
- Product matching with alias resolution and fuzzy keyword matching.
- Unit conversion (e.g. grams to kg, ml to litre).
- Stock level verification (available, insufficient stock, unavailable).
- Item and grand total pricing calculations.
- Stock deduction and replenishment upon order confirmation or cancellation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class InventoryItem:
    """Represents a product item in the local inventory."""
    id: str
    name: str
    category: str
    price_per_unit: float
    unit: str
    available_quantity: float
    aliases: List[str] = field(default_factory=list)

    def matches_query(self, query: str) -> bool:
        """
        Checks whether query matches this item's name or any alias.
        Case-insensitive and handles multi-word variations.
        """
        q = query.lower().strip()
        if not q:
            return False

        if q == self.name.lower():
            return True

        for alias in self.aliases:
            if q == alias.lower():
                return True

        # Token overlap matching (e.g. 'basmati' matches 'basmati rice')
        query_words = set(q.split())
        name_words = set(self.name.lower().split())
        if query_words.issubset(name_words):
            return True

        for alias in self.aliases:
            alias_words = set(alias.lower().split())
            if query_words.issubset(alias_words) or alias_words.issubset(query_words):
                return True

        return False


@dataclass
class StockCheckResult:
    """Result of checking product availability and calculating price."""
    status: str  # 'available', 'insufficient_stock', 'unavailable', 'incompatible_unit'
    item: Optional[InventoryItem] = None
    requested_quantity: float = 0.0
    requested_unit: str = ""
    normalized_quantity: float = 0.0
    unit_price: float = 0.0
    item_total: float = 0.0
    available_quantity: float = 0.0
    message: str = ""

    @property
    def is_available(self) -> bool:
        return self.status == "available"


class InventoryManager:
    """Manages local store inventory, stock queries, and pricing."""

    # Unit conversion factors to canonical base units ('kg' or 'litre')
    UNIT_CONVERSIONS: Dict[str, Dict[str, float]] = {
        "kg": {
            "kg": 1.0,
            "kilo": 1.0,
            "kilos": 1.0,
            "kilogram": 1.0,
            "kilograms": 1.0,
            "g": 0.001,
            "gm": 0.001,
            "gms": 0.001,
            "gram": 0.001,
            "grams": 0.001,
            # Telugu units
            "కిలో": 1.0,
            "కిలోలు": 1.0,
            "కేజీ": 1.0,
            "గ్రాములు": 0.001,
            "గ్రాం": 0.001,
            "kilolu": 1.0,
            "gramulu": 0.001,
            # Hindi units
            "किलो": 1.0,
            "किलोग्राम": 1.0,
            "ग्राम": 0.001,
        },
        "litre": {
            "litre": 1.0,
            "litres": 1.0,
            "liter": 1.0,
            "liters": 1.0,
            "l": 1.0,
            "lt": 1.0,
            "ltr": 1.0,
            "ml": 0.001,
            "mls": 0.001,
            "millilitre": 0.001,
            "millilitres": 0.001,
            "milliliter": 0.001,
            # Telugu units
            "లీటర్": 1.0,
            "లీటర్లు": 1.0,
            "మిల్లీలీటర్": 0.001,
            "మిలీ": 0.001,
            "litrelu": 1.0,
            # Hindi units
            "लीटर": 1.0,
            "मिलीलीटर": 0.001,
        },
        "packet": {
            "packet": 1.0,
            "packets": 1.0,
            "pkt": 1.0,
            "pkts": 1.0,
            "pouch": 1.0,
            "pouches": 1.0,
            "pack": 1.0,
            "box": 1.0,
            "boxes": 1.0,
            # Telugu units
            "ప్యాకెట్": 1.0,
            "ప్యాకెట్లు": 1.0,
            "packetlu": 1.0,
            # Hindi units
            "पैकेट": 1.0,
            "पॉकेट": 1.0,
        },
        "piece": {
            "piece": 1.0,
            "pieces": 1.0,
            "pc": 1.0,
            "pcs": 1.0,
            "unit": 1.0,
            "units": 1.0,
        },
    }

    def __init__(self, items: Optional[List[InventoryItem]] = None):
        self._items: Dict[str, InventoryItem] = {}
        if items:
            for it in items:
                self._items[it.id] = it

    @classmethod
    def from_json(cls, json_path: Union[str, Path]) -> InventoryManager:
        """Loads inventory from a JSON file."""
        p = Path(json_path)
        if not p.is_file():
            raise FileNotFoundError(f"Inventory file not found: {json_path}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = []
        for raw in data:
            items.append(
                InventoryItem(
                    id=raw["id"],
                    name=raw["name"],
                    category=raw.get("category", "General"),
                    price_per_unit=float(raw["price_per_unit"]),
                    unit=raw["unit"].lower(),
                    available_quantity=float(raw["available_quantity"]),
                    aliases=raw.get("aliases", []),
                )
            )
        return cls(items=items)

    @classmethod
    def default_inventory(cls) -> InventoryManager:
        """Instantiates default sample inventory (from sample_inventory.json or built-in)."""
        candidate = Path(__file__).resolve().parent.parent / "data" / "sample_inventory.json"
        if candidate.is_file():
            return cls.from_json(candidate)

        # Fallback built-in items
        default_items = [
            InventoryItem("PROD-001", "Basmati Rice", "Grains & Cereals", 60.0, "kg", 50.0, [
                "rice", "basmati", "basmati rice", "chawal", "चावल", "biyyam", "beeyam", "బియ్యం"
            ]),
            InventoryItem("PROD-002", "Sunflower Cooking Oil", "Edible Oils", 140.0, "litre", 30.0, [
                "oil", "tel", "cooking oil", "sunflower oil", "तेल", "noone", "vanta noone", "నూనె"
            ]),
            InventoryItem("PROD-003", "Refined Sugar", "Sweeteners", 42.0, "kg", 40.0, [
                "sugar", "cheeni", "shakkar", "चीनी", "panchadara", "chakkera", "పంచదార", "చక్కెర"
            ]),
            InventoryItem("PROD-004", "Whole Wheat Atta", "Flours", 40.0, "kg", 35.0, [
                "atta", "wheat flour", "flour", "आटा", "godhuma pindi", "గోధుమ పిండి"
            ]),
            InventoryItem("PROD-005", "Toor Dal", "Pulses & Lentils", 150.0, "kg", 20.0, [
                "dal", "toor dal", "daal", "दाल", "pappu", "kandi pappu", "పప్పు"
            ]),
            InventoryItem("PROD-006", "Fresh Cow Milk", "Dairy", 60.0, "litre", 25.0, [
                "milk", "doodh", "cow milk", "दूध", "paalu", "palu", "పాలు"
            ]),
            InventoryItem("PROD-007", "Parle-G Biscuits", "Snacks & Bakery", 10.0, "packet", 50.0, [
                "biscuit", "biscuits", "parle-g", "बिस्कुट", "biscuitlu", "బిస్కెట్లు"
            ]),
            InventoryItem("PROD-008", "Premium Tea Leaves", "Beverages", 280.0, "kg", 15.0, [
                "tea", "chai", "chai patti", "चाय", "tea podi", "టీ పొడి"
            ]),
            InventoryItem("PROD-009", "Iodized Salt", "Spices & Seasoning", 22.0, "kg", 45.0, [
                "salt", "namak", "नमक", "uppu", "ఉప్పు"
            ]),
            InventoryItem("PROD-010", "Turmeric Powder", "Spices & Seasoning", 180.0, "kg", 10.0, [
                "turmeric", "haldi", "हल्दी", "pasupu", "పసుపు"
            ]),
        ]
        return cls(items=default_items)

    def find_item(self, query: str) -> Optional[InventoryItem]:
        """Looks up an inventory item matching a product name or alias."""
        clean_query = query.strip()
        if not clean_query:
            return None

        # 1. Exact match on ID
        if clean_query.upper() in self._items:
            return self._items[clean_query.upper()]

        # 2. Check query match against all items
        for item in self._items.values():
            if item.matches_query(clean_query):
                return item

        return None

    def convert_quantity(
        self,
        requested_qty: float,
        requested_unit: str,
        target_unit: str,
    ) -> Optional[float]:
        """
        Converts requested quantity to the target inventory unit.
        Returns None if units are incompatible.
        """
        req_u = requested_unit.lower().strip()
        tgt_u = target_unit.lower().strip()

        if req_u == tgt_u:
            return requested_qty

        # Check conversion table
        if tgt_u in self.UNIT_CONVERSIONS:
            factors = self.UNIT_CONVERSIONS[tgt_u]
            if req_u in factors:
                return requested_qty * factors[req_u]

        return None

    def check_and_price_item(
        self,
        product_name: str,
        requested_qty: float,
        requested_unit: Optional[str] = None,
    ) -> StockCheckResult:
        """
        Matches a product, checks stock, normalizes units, and computes item price.
        """
        item = self.find_item(product_name)
        if not item:
            return StockCheckResult(
                status="unavailable",
                requested_quantity=requested_qty,
                requested_unit=requested_unit or "",
                message=f"'{product_name}' is not currently available in our inventory.",
            )

        # Determine unit: if user didn't specify unit, fall back to item default unit
        effective_unit = requested_unit.lower() if requested_unit else item.unit

        # Convert quantity to inventory unit
        normalized_qty = self.convert_quantity(requested_qty, effective_unit, item.unit)
        if normalized_qty is None:
            return StockCheckResult(
                status="incompatible_unit",
                item=item,
                requested_quantity=requested_qty,
                requested_unit=effective_unit,
                available_quantity=item.available_quantity,
                message=f"Requested unit '{effective_unit}' cannot be converted to '{item.unit}' for {item.name}.",
            )

        # Check stock availability
        if item.available_quantity <= 0:
            return StockCheckResult(
                status="insufficient_stock",
                item=item,
                requested_quantity=requested_qty,
                requested_unit=effective_unit,
                normalized_quantity=normalized_qty,
                unit_price=item.price_per_unit,
                available_quantity=0.0,
                message=f"{item.name} is completely out of stock.",
            )

        if item.available_quantity < normalized_qty:
            return StockCheckResult(
                status="insufficient_stock",
                item=item,
                requested_quantity=requested_qty,
                requested_unit=effective_unit,
                normalized_quantity=normalized_qty,
                unit_price=item.price_per_unit,
                available_quantity=item.available_quantity,
                message=(
                    f"Only {item.available_quantity:g} {item.unit} of {item.name} available "
                    f"(requested {normalized_qty:g} {item.unit})."
                ),
            )

        item_total = round(normalized_qty * item.price_per_unit, 2)

        return StockCheckResult(
            status="available",
            item=item,
            requested_quantity=requested_qty,
            requested_unit=effective_unit,
            normalized_quantity=normalized_qty,
            unit_price=item.price_per_unit,
            item_total=item_total,
            available_quantity=item.available_quantity,
            message=f"{item.name}: {normalized_qty:g} {item.unit} available at Rs. {item.price_per_unit:g}/{item.unit}.",
        )

    def deduct_stock(self, item_id: str, quantity: float) -> bool:
        """Deducts stock when an order item is confirmed."""
        if item_id not in self._items:
            return False
        item = self._items[item_id]
        if item.available_quantity >= quantity:
            item.available_quantity = round(item.available_quantity - quantity, 3)
            return True
        return False

    def restore_stock(self, item_id: str, quantity: float) -> bool:
        """Restores stock when an order is cancelled or modified downwards."""
        if item_id not in self._items:
            return False
        item = self._items[item_id]
        item.available_quantity = round(item.available_quantity + quantity, 3)
        return True

    def get_all_items(self) -> List[InventoryItem]:
        """Returns all items in inventory."""
        return list(self._items.values())
