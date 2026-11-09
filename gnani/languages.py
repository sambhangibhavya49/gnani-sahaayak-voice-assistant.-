"""
gnani.languages
~~~~~~~~~~~~~~~
Multilingual definitions, language detection, and preference management
for Gnani Sahaayak Voice Assistant.

Supports:
- Auto Detect
- Telugu (తెలుగు)
- Hindi (हिन्दी)
- English
- Hinglish (Hindi + English)
- Tenglish (Telugu + English)
- Code-mixed conversations (Telugu + Hindi + English)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class LanguageMode(str, Enum):
    """Supported language modes in Gnani Sahaayak."""
    AUTO = "auto"
    TELUGU = "te"
    HINDI = "hi"
    ENGLISH = "en"
    HINGLISH = "hinglish"
    TENGLISH = "tenglish"

    @property
    def display_name(self) -> str:
        names = {
            LanguageMode.AUTO: "Auto Detect",
            LanguageMode.TELUGU: "Telugu (తెలుగు)",
            LanguageMode.HINDI: "Hindi (हिन्दी)",
            LanguageMode.ENGLISH: "English",
            LanguageMode.HINGLISH: "Hinglish (Hindi + English)",
            LanguageMode.TENGLISH: "Tenglish (Telugu + English)",
        }
        return names.get(self, self.value)

    @classmethod
    def from_string(cls, val: str) -> LanguageMode:
        """Parses a user input or string into a LanguageMode safely."""
        norm = (val or "").strip().lower()
        mapping = {
            "auto": cls.AUTO,
            "autodetect": cls.AUTO,
            "auto-detect": cls.AUTO,
            "auto detect": cls.AUTO,
            "te": cls.TELUGU,
            "tel": cls.TELUGU,
            "telugu": cls.TELUGU,
            "తెలుగు": cls.TELUGU,
            "hi": cls.HINDI,
            "hin": cls.HINDI,
            "hindi": cls.HINDI,
            "हिन्दी": cls.HINDI,
            "हिंदी": cls.HINDI,
            "en": cls.ENGLISH,
            "eng": cls.ENGLISH,
            "english": cls.ENGLISH,
            "hinglish": cls.HINGLISH,
            "tenglish": cls.TENGLISH,
        }
        if norm in mapping:
            return mapping[norm]
        raise ValueError(f"Unsupported language mode: '{val}'. Choose from: {[m.value for m in cls]}")


# Verified Gnani API configurations
# Prisma STT official BCP-47 language codes
PRISMA_LANGUAGE_CODES: Dict[LanguageMode, str] = {
    LanguageMode.TELUGU: "te-IN",
    LanguageMode.HINDI: "hi-IN",
    LanguageMode.ENGLISH: "en-IN",
    LanguageMode.HINGLISH: "hi-IN",
    LanguageMode.TENGLISH: "te-IN",
    LanguageMode.AUTO: "hi-IN",  # Default fallback when audio language is unknown
}

# Timbre TTS official voice identifiers and BCP-47 codes
TIMBRE_VOICE_CONFIG: Dict[LanguageMode, Dict[str, str]] = {
    LanguageMode.TELUGU: {
        "language": "te-IN",
        "voice": "Chitra",       # Verified official Telugu female voice for timbre-v2.5
    },
    LanguageMode.HINDI: {
        "language": "hi-IN",
        "voice": "Nalini",       # Verified official Hindi female voice for timbre-v2.5
    },
    LanguageMode.ENGLISH: {
        "language": "en-IN",
        "voice": "Nalini",       # Verified official Indian English voice for timbre-v2.5
    },
    LanguageMode.HINGLISH: {
        "language": "hi-IN",
        "voice": "Nalini",
    },
    LanguageMode.TENGLISH: {
        "language": "te-IN",
        "voice": "Chitra",
    },
    LanguageMode.AUTO: {
        "language": "hi-IN",
        "voice": "Nalini",
    },
}


@dataclass
class DetectionResult:
    """Result of language detection on transcript."""
    primary_language: LanguageMode
    confidence: float
    detected_scripts: List[str]
    has_telugu: bool = False
    has_hindi: bool = False
    has_english: bool = False
    is_code_mixed: bool = False
    raw_transcript: str = ""

    def __repr__(self) -> str:
        return (
            f"DetectionResult(lang={self.primary_language.value}, "
            f"conf={self.confidence:.2f}, "
            f"mixed={self.is_code_mixed})"
        )


class LanguageDetector:
    """
    Deterministic rule-based language detector for Indic grocery conversations.
    Inspects Unicode script ranges (Telugu, Devanagari) and Romanized lexicons.
    """

    # Unicode ranges
    TELUGU_SCRIPT_RE = re.compile(r"[\u0C00-\u0C7F]")
    DEVANAGARI_SCRIPT_RE = re.compile(r"[\u0900-\u097F]")
    LATIN_SCRIPT_RE = re.compile(r"[a-zA-Z]")

    # Romanized vocabulary markers
    ROMAN_TELUGU_WORDS: Set[str] = {
        "anna", "kavali", "ivvandi", "ivvu", "pettandi", "veeyandi", "garu", "babu",
        "biyyam", "beeyam", "noone", "pappu", "panchadara", "chakkera", "uppu", "paalu", "palu",
        "pasupu", "godhuma", "pindi", "chintapandu", "bellam", "mirapakayalu", "karam",
        "rendu", "moodu", "naalugu", "nalugu", "aidu", "aaru", "yedu", "edu", "enimidi", "tommidi", "padi",
        "ara", "paavu", "pavu", "muppaavu", "muppavu", "kilonnaara", "kilonnara", "rendunnara",
        "mariyu", "kuda", "undi", "leda", "inka", "inkaa", "dhaani", "idi",
    }

    ROMAN_HINDI_WORDS: Set[str] = {
        "bhaiya", "bhai", "chahiye", "dena", "de", "do", "kripya", "mujhe", "aur",
        "chawal", "cheeni", "shakkar", "chini", "tel", "atta", "aata", "doodh", "dudh",
        "haldi", "namak", "chai", "patti", "masala", "dhaniya", "mirch",
        "ek", "do", "teen", "char", "chaar", "paanch", "panch", "che", "chhah", "saat", "aath", "nau", "das",
        "aadha", "adha", "pav", "paav", "dedh", "dhai", "dhayi", "bhejo", "karo", "hatao",
    }

    ENGLISH_COMMON_WORDS: Set[str] = {
        "rice", "oil", "sugar", "milk", "tea", "salt", "flour", "biscuit", "biscuits",
        "kilo", "kilos", "kg", "kgs", "gram", "grams", "litre", "litres", "liter", "liters", "packet", "packets",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "half", "quarter",
        "please", "give", "and", "want", "need", "confirm", "change", "remove", "cancel", "yes", "no", "order",
    }

    def detect(self, text: str) -> DetectionResult:
        """
        Detects language mode and code-mixing from text.
        Returns DetectionResult with confidence.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return DetectionResult(
                primary_language=LanguageMode.ENGLISH,
                confidence=0.5,
                detected_scripts=[],
                raw_transcript=cleaned,
            )

        # 1. Script-level detection
        has_telugu_script = bool(self.TELUGU_SCRIPT_RE.search(cleaned))
        has_devanagari_script = bool(self.DEVANAGARI_SCRIPT_RE.search(cleaned))
        has_latin_script = bool(self.LATIN_SCRIPT_RE.search(cleaned))

        scripts = []
        if has_telugu_script:
            scripts.append("Telugu")
        if has_devanagari_script:
            scripts.append("Devanagari")
        if has_latin_script:
            scripts.append("Latin")

        # 2. Token-level analysis for Latin/Romanized text
        words = re.findall(r"[^\s,;!?._-]+", cleaned.lower())

        telugu_word_count = sum(1 for w in words if w in self.ROMAN_TELUGU_WORDS)
        hindi_word_count = sum(1 for w in words if w in self.ROMAN_HINDI_WORDS)
        english_word_count = sum(1 for w in words if w in self.ENGLISH_COMMON_WORDS)

        # Flag presence
        has_telugu = has_telugu_script or telugu_word_count > 0
        has_hindi = has_devanagari_script or hindi_word_count > 0
        has_english = has_latin_script and (english_word_count > 0 or (not has_telugu_script and not has_devanagari_script))

        # 3. Decision logic
        if has_telugu and has_english and not has_hindi:
            # Tenglish: combination of Telugu (script or romanized) and English
            confidence = min(1.0, 0.6 + (telugu_word_count + (2 if has_telugu_script else 0)) * 0.1)
            return DetectionResult(
                primary_language=LanguageMode.TENGLISH,
                confidence=confidence,
                detected_scripts=scripts,
                has_telugu=True,
                has_hindi=False,
                has_english=True,
                is_code_mixed=True,
                raw_transcript=cleaned,
            )

        if has_hindi and has_english and not has_telugu:
            # Hinglish: combination of Hindi (script or romanized) and English
            confidence = min(1.0, 0.6 + (hindi_word_count + (2 if has_devanagari_script else 0)) * 0.1)
            return DetectionResult(
                primary_language=LanguageMode.HINGLISH,
                confidence=confidence,
                detected_scripts=scripts,
                has_telugu=False,
                has_hindi=True,
                has_english=True,
                is_code_mixed=True,
                raw_transcript=cleaned,
            )

        if has_telugu and has_hindi:
            # 3-language mixed conversation (e.g. "Mujhe rendu kilo rice chahiye" or "Anna, rice aur sugar kavali")
            # Determine dominant Indian language
            if telugu_word_count >= hindi_word_count or has_telugu_script:
                primary = LanguageMode.TENGLISH
            else:
                primary = LanguageMode.HINGLISH
            return DetectionResult(
                primary_language=primary,
                confidence=0.75,
                detected_scripts=scripts,
                has_telugu=True,
                has_hindi=True,
                has_english=has_english,
                is_code_mixed=True,
                raw_transcript=cleaned,
            )

        if has_telugu_script or (telugu_word_count > 0 and not has_hindi and english_word_count == 0):
            # Pure Telugu or Romanized Telugu
            conf = 0.95 if has_telugu_script else 0.8
            return DetectionResult(
                primary_language=LanguageMode.TELUGU,
                confidence=conf,
                detected_scripts=scripts,
                has_telugu=True,
                has_hindi=False,
                has_english=False,
                is_code_mixed=False,
                raw_transcript=cleaned,
            )

        if has_devanagari_script or (hindi_word_count > 0 and not has_telugu and english_word_count == 0):
            # Pure Hindi or Romanized Hindi
            conf = 0.95 if has_devanagari_script else 0.8
            return DetectionResult(
                primary_language=LanguageMode.HINDI,
                confidence=conf,
                detected_scripts=scripts,
                has_telugu=False,
                has_hindi=True,
                has_english=False,
                is_code_mixed=False,
                raw_transcript=cleaned,
            )

        # Default to English
        return DetectionResult(
            primary_language=LanguageMode.ENGLISH,
            confidence=0.85,
            detected_scripts=scripts,
            has_telugu=False,
            has_hindi=False,
            has_english=True,
            is_code_mixed=False,
            raw_transcript=cleaned,
        )


class LanguagePreferenceManager:
    """
    Manages customer language preference throughout conversation turns.
    Supports manual selection and automatic detection with confidence thresholds.
    """

    def __init__(
        self,
        default_mode: LanguageMode = LanguageMode.AUTO,
        confidence_threshold: float = 0.6,
    ):
        self.selected_mode: LanguageMode = default_mode
        self.confidence_threshold: float = confidence_threshold
        self.detector = LanguageDetector()
        # Active resolved response language
        self._active_response_language: LanguageMode = (
            LanguageMode.ENGLISH if default_mode == LanguageMode.AUTO else default_mode
        )
        self.last_detection: Optional[DetectionResult] = None

    @property
    def is_auto(self) -> bool:
        return self.selected_mode == LanguageMode.AUTO

    @property
    def active_language(self) -> LanguageMode:
        """Returns the current language to be used for spoken and text responses."""
        if not self.is_auto:
            return self.selected_mode
        return self._active_response_language

    def set_language(self, mode: LanguageMode) -> None:
        """Manually sets the language preference."""
        self.selected_mode = mode
        if mode != LanguageMode.AUTO:
            self._active_response_language = mode

    def process_transcript(self, transcript: str) -> LanguageMode:
        """
        Inspects incoming customer transcript.
        If in AUTO mode and detection is confident, updates active response language.
        Preserves preference if confidence is low.
        Returns the resolved active language.
        """
        detection = self.detector.detect(transcript)
        self.last_detection = detection

        if self.is_auto:
            if detection.confidence >= self.confidence_threshold:
                self._active_response_language = detection.primary_language

        return self.active_language

    def get_prisma_language_code(self) -> str:
        """Returns verified BCP-47 language code for Prisma STT."""
        target = self.active_language
        return PRISMA_LANGUAGE_CODES.get(target, "hi-IN")

    def get_timbre_config(self) -> Dict[str, str]:
        """Returns verified (language, voice) dict for Timbre TTS."""
        target = self.active_language
        return TIMBRE_VOICE_CONFIG.get(
            target,
            {"language": "hi-IN", "voice": "Nalini"},
        )

