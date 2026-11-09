"""
gnani.extractor
~~~~~~~~~~~~~~~
Product, quantity, and unit extraction engine.

Extracts structured order items from natural speech transcripts:
- Handles English, Hindi, Hinglish, Telugu, and Tenglish spoken numbers and units.
- Understands Telugu script, Devanagari script, and Romanized forms.
- Splits compound sentences with multiple items and multilingual conjunctions.
- Supports complex quantity expressions (e.g., 'అర కిలో', 'పావు కిలో', 'కిలోన్నర', 'aadha kilo').
- Detects ambiguities (missing quantity, missing unit, unclear product) and generates targeted clarification prompts.
- Designed as a modular extractor base for future AI/LLM integration.
"""

from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ExtractedItem:
    """Represents a structured product item extracted from speech transcript."""
    raw_product: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    raw_text: str = ""
    is_ambiguous: bool = False
    clarification_prompt: Optional[str] = None

    def __repr__(self) -> str:
        q_str = f"{self.quantity:g}" if self.quantity is not None else "None"
        return (
            f"ExtractedItem(product='{self.raw_product}', "
            f"quantity={q_str}, "
            f"unit='{self.unit}', "
            f"ambiguous={self.is_ambiguous})"
        )


@dataclass
class ExtractionResult:
    """Aggregated output of transcript extraction."""
    items: List[ExtractedItem] = field(default_factory=list)
    unparsed_segments: List[str] = field(default_factory=list)

    @property
    def has_ambiguities(self) -> bool:
        """True if any item requires user clarification."""
        return any(item.is_ambiguous for item in self.items)

    @property
    def clarifications(self) -> List[str]:
        """List of clarification prompts for ambiguous items."""
        return [
            item.clarification_prompt
            for item in self.items
            if item.is_ambiguous and item.clarification_prompt
        ]


class BaseProductExtractor(ABC):
    """Abstract interface for order item extractors."""

    @abstractmethod
    def extract(self, transcript: str) -> ExtractionResult:
        """Parse natural text transcript into structured ExtractionResult."""
        pass


class DeterministicProductExtractor(BaseProductExtractor):
    """
    Deterministic rule-based and regex extractor for spoken grocery orders.
    Supports English, Hindi, Hinglish, Telugu, and Tenglish numerical expressions and units.
    """

    # Spoken number conversion (English, Hindi, Telugu, Romanized and native scripts)
    WORD_TO_NUMBER: Dict[str, float] = {
        # English numbers
        "zero": 0.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0,
        "five": 5.0, "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0,
        "ten": 10.0, "eleven": 11.0, "twelve": 12.0, "fifteen": 15.0,
        "twenty": 20.0, "half": 0.5, "quarter": 0.25,

        # Hindi / Hinglish numbers (Romanized)
        "ek": 1.0, "do": 2.0, "teen": 3.0, "char": 4.0, "chaar": 4.0,
        "paanch": 5.0, "panch": 5.0, "che": 6.0, "chhah": 6.0, "chhe": 6.0,
        "saat": 7.0, "sat": 7.0, "aath": 8.0, "ath": 8.0, "nau": 9.0,
        "das": 10.0, "aadha": 0.5, "adha": 0.5, "pav": 0.25, "paav": 0.25,
        "dedh": 1.5, "deedh": 1.5, "dhai": 2.5, "dhayi": 2.5,

        # Hindi numbers (Devanagari)
        "एक": 1.0, "दो": 2.0, "तीन": 3.0, "चार": 4.0,
        "पांच": 5.0, "पाँच": 5.0, "छह": 6.0, "सात": 7.0,
        "आठ": 8.0, "नौ": 9.0, "दस": 10.0,
        "आधा": 0.5, "पाव": 0.25, "डेढ़": 1.5, "ढाई": 2.5,

        # Telugu / Tenglish numbers (Romanized)
        "okati": 1.0, "oka": 1.0, "rendu": 2.0, "moodu": 3.0,
        "naalugu": 4.0, "nalugu": 4.0, "aidu": 5.0, "aaru": 6.0,
        "yedu": 7.0, "edu": 7.0, "enimidi": 8.0, "tommidi": 9.0, "padi": 10.0,
        "ara": 0.5, "paavu": 0.25, "pavu": 0.25, "muppaavu": 0.75, "muppavu": 0.75,
        "kilonnaara": 1.5, "kilonnara": 1.5, "rendunnara": 2.5,

        # Telugu numbers (Telugu script)
        "ఒకటి": 1.0, "ఒక": 1.0, "రెండు": 2.0, "మూడు": 3.0,
        "నాలుగు": 4.0, "ఐదు": 5.0, "ఆరు": 6.0, "ఏడు": 7.0,
        "ఎనిమిది": 8.0, "తొమ్మిది": 9.0, "పది": 10.0,
        "అర": 0.5, "పావు": 0.25, "ముప్పావు": 0.75,
        "కిలోన్నర": 1.5, "రెండున్నర": 2.5,
    }

    # Unit canonicalization mapping
    UNIT_MAPPING: Dict[str, str] = {
        # Weight
        "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
        "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
        # Telugu weight units
        "కిలో": "kg", "కిలోలు": "kg", "కిలోల": "kg", "కేజీ": "kg", "కేజీలు": "kg",
        "గ్రాములు": "g", "గ్రాం": "g", "గ్రాము": "g", "గ్రా": "g",
        "kilolu": "kg", "kilola": "kg", "gramulu": "g",
        # Hindi weight units
        "किलो": "kg", "किलोग्राम": "kg", "ग्राम": "g",

        # Volume
        "l": "litre", "lt": "litre", "ltr": "litre", "ltrs": "litre",
        "litre": "litre", "litres": "litre", "liter": "liters",
        "ml": "ml", "mls": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml",
        # Telugu volume units
        "లీటర్": "litre", "లీటర్లు": "litre", "లీటర్ల": "litre", "మిల్లీలీటర్": "ml", "మిలీ": "ml",
        "litrelu": "litre", "liters": "litre",
        # Hindi volume units
        "लीटर": "litre", "मिलीलीटर": "ml",

        # Count / Package
        "packet": "packet", "packets": "packet", "pkt": "packet", "pkts": "packet",
        "pouch": "packet", "pouches": "packet", "pack": "packet", "packs": "packet",
        "bottle": "bottle", "bottles": "bottle", "btl": "bottle",
        "piece": "piece", "pieces": "piece", "pc": "piece", "pcs": "piece",
        "box": "box", "boxes": "box", "unit": "piece", "units": "piece",
        # Telugu package units
        "ప్యాకెట్": "packet", "ప్యాకెట్లు": "packet", "ప్యాకెట్ల": "packet", "ప్యాక్": "packet", "బాటిల్": "bottle",
        "packetlu": "packet",
        # Hindi package units
        "पैकेट": "packet", "पॉकेट": "packet", "बोतल": "bottle",
    }

    # Compound multilingual expressions mapped directly to (quantity, canonical_unit)
    COMPOUND_QUANTITY_MAPPING: Dict[str, Tuple[float, str]] = {
        # Telugu script compounds
        "కిలోన్నర": (1.5, "kg"),
        "రెండున్నర కిలోలు": (2.5, "kg"),
        "రెండున్నర కిలోల": (2.5, "kg"),
        "రెండున్నర కిలో": (2.5, "kg"),
        "రెండున్నర": (2.5, "kg"),
        "అర కిలో": (0.5, "kg"),
        "పావు కిలో": (0.25, "kg"),
        "ముప్పావు కిలో": (0.75, "kg"),
        "అర లీటర్": (0.5, "litre"),
        "పావు లీటర్": (0.25, "litre"),
        "ఒక కిలో": (1.0, "kg"),
        "ఒక లీటర్": (1.0, "litre"),
        "ఒక ప్యాకెట్": (1.0, "packet"),
        "రెండు కిలోల": (2.0, "kg"),
        "రెండు కిలోలు": (2.0, "kg"),
        "రెండు కిలో": (2.0, "kg"),
        "రెండు లీటర్లు": (2.0, "litre"),
        "మూడు కిలోలు": (3.0, "kg"),

        # Romanized Telugu compounds
        "kilonnaara": (1.5, "kg"),
        "kilonnara": (1.5, "kg"),
        "rendunnara": (2.5, "kg"),
        "ara kilo": (0.5, "kg"),
        "ara kilolu": (0.5, "kg"),
        "ara kilola": (0.5, "kg"),
        "paavu kilo": (0.25, "kg"),
        "pavu kilo": (0.25, "kg"),
        "muppaavu kilo": (0.75, "kg"),
        "muppavu kilo": (0.75, "kg"),
        "ara litre": (0.5, "litre"),
        "ara liter": (0.5, "litre"),
        "paavu litre": (0.25, "litre"),
        "pavu litre": (0.25, "litre"),
        "okati kilo": (1.0, "kg"),
        "oka kilo": (1.0, "kg"),
        "rendu kilo": (2.0, "kg"),
        "rendu kilolu": (2.0, "kg"),
        "rendu kilola": (2.0, "kg"),
        "moodu kilo": (3.0, "kg"),
        "okati litre": (1.0, "litre"),
        "oka litre": (1.0, "litre"),
        "rendu litre": (2.0, "litre"),
        "okati packet": (1.0, "packet"),
        "oka packet": (1.0, "packet"),

        # English compounds
        "one and a half kilo": (1.5, "kg"),
        "one and a half kilos": (1.5, "kg"),
        "two and a half kilos": (2.5, "kg"),
        "one and a half litre": (1.5, "litre"),
        "half kilo": (0.5, "kg"),
        "half a kilo": (0.5, "kg"),
        "quarter kilo": (0.25, "kg"),
        "half litre": (0.5, "litre"),
        "half liter": (0.5, "litre"),
        "quarter litre": (0.25, "litre"),
        "one kilo": (1.0, "kg"),
        "one kg": (1.0, "kg"),
        "two kilos": (2.0, "kg"),
        "two kilo": (2.0, "kg"),
        "three kilos": (3.0, "kg"),
        "one litre": (1.0, "litre"),
        "one liter": (1.0, "litre"),
        "two litres": (2.0, "litre"),
        "one packet": (1.0, "packet"),
        "two packets": (2.0, "packet"),

        # Hindi / Hinglish compounds (Romanized)
        "aadha kilo": (0.5, "kg"),
        "adha kilo": (0.5, "kg"),
        "pav kilo": (0.25, "kg"),
        "paav kilo": (0.25, "kg"),
        "dedh kilo": (1.5, "kg"),
        "deedh kilo": (1.5, "kg"),
        "dhai kilo": (2.5, "kg"),
        "dhayi kilo": (2.5, "kg"),
        "aadha litre": (0.5, "litre"),
        "aadha liter": (0.5, "litre"),
        "adha litre": (0.5, "litre"),
        "ek kilo": (1.0, "kg"),
        "do kilo": (2.0, "kg"),
        "teen kilo": (3.0, "kg"),
        "chaar kilo": (4.0, "kg"),
        "char kilo": (4.0, "kg"),
        "paanch kilo": (5.0, "kg"),
        "panch kilo": (5.0, "kg"),
        "ek litre": (1.0, "litre"),
        "do litre": (2.0, "litre"),
        "ek packet": (1.0, "packet"),
        "do packet": (2.0, "packet"),

        # Hindi compounds (Devanagari)
        "आधा किलो": (0.5, "kg"),
        "पाव किलो": (0.25, "kg"),
        "डेढ़ किलो": (1.5, "kg"),
        "ढाई किलो": (2.5, "kg"),
        "आधा लीटर": (0.5, "litre"),
        "एक किलो": (1.0, "kg"),
        "दो किलो": (2.0, "kg"),
        "तीन किलो": (3.0, "kg"),
        "चार किलो": (4.0, "kg"),
        "पांच किलो": (5.0, "kg"),
        "एक लीटर": (1.0, "litre"),
        "दो लीटर": (2.0, "litre"),
        "एक पैकेट": (1.0, "packet"),
    }

    # Leading filler prefixes, greetings, and courtesy markers
    LEADING_FILLERS = {
        "anna", "bhaiya", "bhai", "please", "kripya", "mujhe", "can", "i", "get", "want", "give", "me",
        "need", "needs", "would", "like", "take",
        "send", "order", "hello", "namaste", "hey", "babu", "garu", "ayya", "koddiga",
        "దయచేసి", "అన్నా", "బాబు", "గారు", "కొద్దిగా", "నాకు",
        "कृपया", "भैया", "भाई", "मुझे", "नमस्ते", "जरा",
    }

    # Trailing request words, verbs, and politeness markers
    TRAILING_VERBS = {
        "chahiye", "dena", "de", "do", "bhejo", "karo", "dal do", "please",
        "kavali", "kaavali", "ivvandi", "ivvu", "pettandi", "veeyandi", "veye", "kuda",
        "cheyandi", "cheyi", "kar do",
        "కావాలి", "ఇవ్వండి", "ఇవ్వు", "పెట్టండి", "వేయండి", "కూడా", "చేయండి", "చేయి",
        "चाहिए", "देना", "दो", "दीजिए", "भेजो", "करो", "डालो", "कर दो", "कर",
    }

    # Intermediate linking words
    LINK_WORDS = {"of", "ka", "ki", "ke", "la", "ల", "యొక్క", "లో", "కోసం"}

    def _clean_segment(self, text: str) -> str:
        """Removes punctuation while preserving decimals, hyphens, and Unicode Indic characters."""
        # Replace dots not followed by digits with space
        text_without_trailing_dots = re.sub(r"\.(?!\d)", " ", text)
        cleaned_chars = []
        for c in text_without_trailing_dots:
            cat = unicodedata.category(c)
            # Remove punctuation characters (cat startswith 'P'), except hyphen, slash, and decimal dot
            if cat.startswith("P") and c not in "-/.":
                cleaned_chars.append(" ")
            else:
                cleaned_chars.append(c)
        return " ".join("".join(cleaned_chars).split()).strip()

    def _split_clauses(self, transcript: str) -> List[str]:
        """
        Splits a compound sentence into separate item clauses across languages.
        Supports English ('and'), Hindi ('aur', 'और'), Telugu ('mariyu', 'మరియు', 'inka', 'ఇంకా').
        """
        delimiters = (
            r",|;|\band\b|\baur\b|\bplus\b|&|\balso\b|\bwith\b|\n|"
            r"(?:\s+|^)(?:మరియు|ఇంకా|కూడా|और|mariyu|inka)(?:\s+|$)"
        )
        raw_parts = re.split(delimiters, transcript, flags=re.IGNORECASE)

        clauses = []
        for part in raw_parts:
            cleaned = self._clean_segment(part)
            if cleaned:
                # Filter out single-word filler clauses
                words = cleaned.lower().split()
                if len(words) == 1 and (words[0] in self.LEADING_FILLERS or words[0] in self.TRAILING_VERBS):
                    continue
                clauses.append(cleaned)
        return clauses

    def _parse_number(self, token: str) -> Optional[float]:
        """Attempts to parse a token into a float number."""
        token_lower = token.lower().strip()

        if token_lower in self.WORD_TO_NUMBER:
            return self.WORD_TO_NUMBER[token_lower]

        if "/" in token_lower:
            parts = token_lower.split("/")
            if len(parts) == 2:
                try:
                    num = float(parts[0])
                    denom = float(parts[1])
                    if denom != 0:
                        return num / denom
                except ValueError:
                    pass

        try:
            return float(token_lower)
        except ValueError:
            return None

    def _extract_from_clause(self, clause: str) -> Optional[ExtractedItem]:
        """
        Parses an individual clause into an ExtractedItem supporting multilingual patterns.
        """
        tokens = clause.split()
        if not tokens:
            return None

        # 1. Strip leading greetings and courtesy words
        while tokens and tokens[0].lower() in self.LEADING_FILLERS:
            tokens.pop(0)

        # 2. Strip trailing verbs and courtesy words
        while tokens and tokens[-1].lower() in self.TRAILING_VERBS:
            tokens.pop()

        if not tokens:
            return None

        clean_clause = " ".join(tokens)
        lower_clause = clean_clause.lower()

        # 3. Check compound quantity expressions (e.g., 'అర కిలో', 'aadha kilo', 'two kilos', 'కిలోన్నర')
        # Sorted by length descending so longer phrases match first
        sorted_compounds = sorted(self.COMPOUND_QUANTITY_MAPPING.items(), key=lambda x: len(x[0]), reverse=True)

        # 3A. Pattern: Starts with compound quantity (e.g., 'two kilos biyyam', 'అర కిలో పంచదార')
        for comp_phrase, (c_qty, c_unit) in sorted_compounds:
            if lower_clause.startswith(comp_phrase):
                rem_text = clean_clause[len(comp_phrase):].strip()
                rem_tokens = rem_text.split()
                while rem_tokens and rem_tokens[0].lower() in self.LINK_WORDS:
                    rem_tokens.pop(0)
                product_name = " ".join(rem_tokens).strip(" .,!?;:")
                if product_name:
                    return ExtractedItem(
                        raw_product=product_name,
                        quantity=c_qty,
                        unit=c_unit,
                        raw_text=clean_clause,
                        is_ambiguous=False,
                    )

        # 3B. Pattern: Ends with compound quantity (e.g., 'sugar one kilo', 'oil half litre')
        for comp_phrase, (c_qty, c_unit) in sorted_compounds:
            if lower_clause.endswith(comp_phrase):
                prod_text = clean_clause[:-len(comp_phrase)].strip()
                prod_tokens = prod_text.split()
                while prod_tokens and prod_tokens[-1].lower() in self.LINK_WORDS:
                    prod_tokens.pop()
                product_name = " ".join(prod_tokens).strip(" .,!?;:")
                if product_name:
                    return ExtractedItem(
                        raw_product=product_name,
                        quantity=c_qty,
                        unit=c_unit,
                        raw_text=clean_clause,
                        is_ambiguous=False,
                    )

        # 4. Standard pattern: '<number> <unit> [of/ka/la] <product>' or '<number> <product>'
        first_num = self._parse_number(tokens[0])
        if first_num is not None and len(tokens) > 1:
            qty = first_num
            remaining = tokens[1:]

            # Check if token after number is a known unit
            first_rem = remaining[0].lower()
            if first_rem in self.UNIT_MAPPING:
                unit = self.UNIT_MAPPING[first_rem]
                prod_words = remaining[1:]
                while prod_words and prod_words[0].lower() in self.LINK_WORDS:
                    prod_words.pop(0)
                product_name = " ".join(prod_words).strip(" .,!?;:")
            else:
                unit = None
                prod_words = remaining
                while prod_words and prod_words[0].lower() in self.LINK_WORDS:
                    prod_words.pop(0)
                product_name = " ".join(prod_words).strip(" .,!?;:")

            if product_name:
                if not unit:
                    return ExtractedItem(
                        raw_product=product_name,
                        quantity=qty,
                        unit=None,
                        raw_text=clean_clause,
                        is_ambiguous=True,
                        clarification_prompt=f"Please specify the unit for {product_name} (for example, packets, kg, or litres).",
                    )
                return ExtractedItem(
                    raw_product=product_name,
                    quantity=qty,
                    unit=unit,
                    raw_text=clean_clause,
                    is_ambiguous=False,
                )

        # 5. Pattern: '<product> <quantity> <unit>' (e.g., 'rice 2 kg', 'నూనె 1 లీటర్')
        if len(tokens) >= 3:
            last_unit_cand = tokens[-1].lower()
            if last_unit_cand in self.UNIT_MAPPING:
                num_cand = self._parse_number(tokens[-2])
                if num_cand is not None:
                    product_name = " ".join(tokens[:-2]).strip(" .,!?;:")
                    if product_name:
                        return ExtractedItem(
                            raw_product=product_name,
                            quantity=num_cand,
                            unit=self.UNIT_MAPPING[last_unit_cand],
                            raw_text=clean_clause,
                            is_ambiguous=False,
                        )

        # 6. Pattern: Product mentioned with missing quantity (e.g., 'give me sugar', 'oil kavali')
        candidate_prod = " ".join([
            t for t in tokens
            if t.lower() not in self.LEADING_FILLERS and t.lower() not in self.TRAILING_VERBS
        ]).strip(" .,!?;:")

        if candidate_prod:
            return ExtractedItem(
                raw_product=candidate_prod,
                quantity=None,
                unit=None,
                raw_text=clean_clause,
                is_ambiguous=True,
                clarification_prompt=f"How much {candidate_prod} would you like? (Please specify quantity and unit, e.g. 1 kg or 2 litres).",
            )

        return None

    def extract(self, transcript: str) -> ExtractionResult:
        """
        Parses the full transcript, extracting items and flagging ambiguities.
        """
        if not transcript or not transcript.strip():
            return ExtractionResult()

        clauses = self._split_clauses(transcript)
        items: List[ExtractedItem] = []
        unparsed: List[str] = []

        for clause in clauses:
            item = self._extract_from_clause(clause)
            if item is not None and item.raw_product:
                items.append(item)
            else:
                unparsed.append(clause)

        return ExtractionResult(items=items, unparsed_segments=unparsed)
