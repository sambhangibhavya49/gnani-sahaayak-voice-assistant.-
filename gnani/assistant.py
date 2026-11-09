"""
gnani.assistant
~~~~~~~~~~~~~~~
Voice Assistant Core Orchestrator for Gnani Sahaayak.

Coordinates the end-to-end multilingual voice shopping pipeline:
1. Audio Input Validation (RIFF/WAV inspection, duration and size limits)
2. Speech Recognition (Gnani Prisma v2.5 STT with language-aware routing)
3. Language Detection & Preference Management (Auto Detect, Telugu, Hindi, English, Hinglish, Tenglish)
4. Product & Quantity Extraction (Multilingual extraction with ambiguity detection)
5. Local Inventory Lookup & Pricing (Stock availability and billing)
6. Order Lifecycle (Creation, confirmation, natural language corrections)
7. Multilingual Voice Response (Gnani Timbre v2.5 TTS and local audio output)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

from .audio_input import AudioInputHandler
from .config import GnaniConfig
from .extractor import BaseProductExtractor, DeterministicProductExtractor
from .inventory import InventoryManager
from .languages import LanguageMode, LanguagePreferenceManager
from .order import Order, OrderManager, OrderStatus
from .prisma import PrismaClient
from .speech import SpeechRecognizer
from .timbre import TimbreClient
from .voice_response import VoiceResponseService


@dataclass
class AssistantTurnResponse:
    """Encapsulates the result of a single conversation turn with the Voice Assistant."""
    success: bool
    transcript: str
    response_text: str
    order: Optional[Order] = None
    audio_path: Optional[Path] = None
    audio_bytes: Optional[bytes] = None
    error: Optional[str] = None
    detected_language: Optional[LanguageMode] = None
    active_language: LanguageMode = LanguageMode.ENGLISH
    normalized_items: List[Dict[str, Any]] = field(default_factory=list)

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED({self.error})"
        total = f"Rs. {self.order.total_amount:g}" if self.order else "N/A"
        return (
            f"AssistantTurnResponse({status}, "
            f"lang={self.active_language.value}, "
            f"transcript='{self.transcript}', "
            f"total={total}, "
            f"audio='{self.audio_path.name if self.audio_path else None}')"
        )


class VoiceAssistant:
    """Core Voice Assistant engine for Kirana grocery ordering."""

    CONFIRMATION_KEYWORDS = {
        # English
        "yes", "confirm", "confirm order", "ok", "okay", "done", "proceed", "sure",
        "yes please", "please confirm", "yes confirm", "yep", "yeah", "correct",
        # Hindi / Hinglish
        "haan", "ha", "theek hai", "sahi hai", "order confirm kar do", "confirm karo",
        "हाँ", "कन्फर्म", "ठीक है", "हां", "हाँ कन्फर्म", "हां कर दो", "पक्का",
        # Telugu / Tenglish
        "sare", "avunu", "sare anna", "confirm cheyi", "order confirm cheddam", "cheddam",
        "సరే", "అవును", "కన్ఫర్మ్", "కన్ఫర్మ్ చేయి", "సరే అన్నా", "ఆర్డర్ కన్ఫర్మ్ చేయి", "చేద్దాం", "కన్ఫర్మ్ చేద్దాం",
    }

    REJECTION_KEYWORDS = {
        # English
        "no", "cancel", "cancel order", "don't confirm", "dont confirm", "do not confirm",
        "reject", "stop", "clear order", "no cancel", "no don't", "no dont",
        # Hindi / Hinglish
        "nahi", "nahin", "nahi chahiye", "cancel karo", "order cancel kar do", "cancel kar do",
        "mat karo", "नहीं", "कैंसिल", "रद्द", "रद्द करो", "नहीं चाहिए", "मत करो",
        # Telugu / Tenglish
        "vaddu", "vaddhu", "vaddu anna", "cancel cheyi", "order cancel cheyi", "voddu",
        "వద్దు", "వద్దు అన్నా", "రద్దు చేయి", "క్యాన్సిల్", "క్యాన్సిల్ చేయి", "వద్దు వద్దు",
    }

    CORRECTION_KEYWORDS = {
        "change", "remove", "delete", "make", "hata", "badlo", "aur add", "set",
        "మార్చు", "తీసివేయి", "తొలగించు", "marchu", "tiseyi", "teeseyi",
        "बदलो", "हटाओ", "जोड़ो",
    }

    def __init__(
        self,
        config: GnaniConfig,
        mock_mode: bool = False,
        inventory: Optional[InventoryManager] = None,
        extractor: Optional[BaseProductExtractor] = None,
        output_audio_dir: Optional[Path] = None,
        language_mode: Union[LanguageMode, str] = LanguageMode.AUTO,
    ):
        self.config = config
        self.mock_mode = mock_mode

        # Language preference manager
        initial_mode = (
            LanguageMode.from_string(language_mode)
            if isinstance(language_mode, str)
            else language_mode
        )
        self.language_manager = LanguagePreferenceManager(default_mode=initial_mode)

        # Core services
        self.audio_handler = AudioInputHandler()
        self.prisma_client = PrismaClient(
            config=config,
            timeout=config.prisma_timeout,
            mock_mode=mock_mode,
        )
        self.timbre_client = TimbreClient(
            config=config,
            timeout=config.timbre_timeout,
            mock_mode=mock_mode,
        )

        self.speech_recognizer = SpeechRecognizer(
            config=config,
            client=self.prisma_client,
            audio_handler=self.audio_handler,
            mock_mode=mock_mode,
        )

        self.extractor = extractor or DeterministicProductExtractor()
        self.inventory = inventory or InventoryManager.default_inventory()
        self.order_manager = OrderManager(inventory=self.inventory)
        self.voice_service = VoiceResponseService(
            timbre_client=self.timbre_client,
            output_dir=output_audio_dir,
        )

        # Active conversation session state
        self.current_order: Optional[Order] = None

    def set_language_mode(self, mode: Union[LanguageMode, str]) -> None:
        """Sets the active language mode preference."""
        if isinstance(mode, str):
            mode = LanguageMode.from_string(mode)
        self.language_manager.set_language(mode)

    def get_language_mode(self) -> LanguageMode:
        """Returns the currently active response language mode."""
        return self.language_manager.active_language

    @property
    def is_stt_busy(self) -> bool:
        """Returns True if an STT transcription request is currently active."""
        return getattr(self.speech_recognizer, "is_busy", False)

    @property
    def is_tts_busy(self) -> bool:
        """Returns True if a TTS synthesis request is currently active."""
        return getattr(self.voice_service, "is_busy", False)

    @property
    def is_busy(self) -> bool:
        """Returns True if either STT transcription or TTS synthesis is active."""
        return self.is_stt_busy or self.is_tts_busy

    def _get_empty_audio_prompt(self, lang: LanguageMode) -> str:
        if lang == LanguageMode.TELUGU:
            return "సరిగ్గా వినబడలేదు. దయచేసి మీకు కావలసిన సరుకులను స్పష్టంగా చెప్పండి."
        elif lang == LanguageMode.HINDI:
            return "आपकी आवाज सुनाई नहीं दी। कृपया बताइए आपको क्या चाहिए।"
        elif lang == LanguageMode.TENGLISH:
            return "Audio vinapadaledu. Please clearly tell me what items you want."
        elif lang == LanguageMode.HINGLISH:
            return "Aapki awaaz sunayi nahi di. Please batayein aapko kya chahiye."
        return "I did not hear any items. Please speak clearly and tell me what you would like to order."

    def _get_stt_error_prompt(self, lang: LanguageMode) -> str:
        if lang == LanguageMode.TELUGU:
            return "క్షమించండి, మీ మాట వినబడలేదు. దయచేసి మరలా చెప్పండి."
        elif lang == LanguageMode.HINDI:
            return "माफ़ कीजिए, आवाज़ समझ नहीं आई। कृपया दोबारा बोलें।"
        elif lang == LanguageMode.TENGLISH:
            return "Sorry, speech artham kaledu. Please repeat cheyandi."
        elif lang == LanguageMode.HINGLISH:
            return "Sorry, audio samajh nahi aaya. Please dobara boliye."
        return "Sorry, I could not understand the audio. Please try speaking again."

    def _extract_normalized_items(self) -> List[Dict[str, Any]]:
        """Extracts serializable normalized items from the current active order."""
        if not self.current_order:
            return []
        return [
            {
                "product_id": it.product_id,
                "product_name": it.product_name,
                "requested_quantity": it.requested_quantity,
                "requested_unit": it.requested_unit,
                "normalized_quantity": it.normalized_quantity,
                "inventory_unit": it.inventory_unit,
                "unit_price": it.unit_price,
                "item_total": it.item_total,
                "status": it.status,
            }
            for it in self.current_order.items
        ]

    def process_audio(
        self,
        audio_source: Union[str, Path, bytes, BinaryIO],
        filename: str = "customer_order.wav",
        language_code: Optional[str] = None,
    ) -> AssistantTurnResponse:
        """
        Executes the full voice pipeline from spoken audio to synthesized voice response.
        """
        # Determine language code for Prisma STT
        lang_code = language_code or self.language_manager.get_prisma_language_code()

        # Step 1: Speech-to-Text via Prisma v2.5
        stt_result = self.speech_recognizer.transcribe(
            audio_source=audio_source,
            filename=filename,
            language_code=lang_code,
        )

        active_lang = self.language_manager.active_language

        if not stt_result.success:
            err_msg = stt_result.error or "Speech recognition failed."
            reply_text = self._get_stt_error_prompt(active_lang)
            voice_res = self.voice_service.synthesize_response(
                reply_text,
                filename_prefix="error",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript="",
                response_text=reply_text,
                order=self.current_order,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error=err_msg,
                active_language=active_lang,
                normalized_items=self._extract_normalized_items(),
            )

        if stt_result.is_empty:
            reply_text = self._get_empty_audio_prompt(active_lang)
            voice_res = self.voice_service.synthesize_response(
                reply_text,
                filename_prefix="empty",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript="",
                response_text=reply_text,
                order=self.current_order,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error="Empty transcription received.",
                active_language=active_lang,
                normalized_items=self._extract_normalized_items(),
            )

        # Step 2: Process transcript through business logic
        return self.process_text(stt_result.transcript)

    @staticmethod
    def _clean_intent_text(text: str) -> str:
        """Strips punctuation and normalizes whitespace while strictly preserving Indic vowel signs/matras."""
        return re.sub(r'[\s!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~]+', ' ', (text or "").lower()).strip()

    @classmethod
    def _is_confirmation(cls, text: str) -> bool:
        cleaned = cls._clean_intent_text(text)
        if not cleaned:
            return False
        if cleaned in cls.CONFIRMATION_KEYWORDS:
            return True
        tokens = set(cleaned.split())
        if tokens.intersection(cls.CONFIRMATION_KEYWORDS):
            return True
        for kw in cls.CONFIRMATION_KEYWORDS:
            if re.search(r'(?:^|\s)' + re.escape(kw) + r'(?:$|\s)', cleaned):
                return True
        return False

    @classmethod
    def _is_rejection(cls, text: str) -> bool:
        cleaned = cls._clean_intent_text(text)
        if not cleaned:
            return False
        if cleaned in cls.REJECTION_KEYWORDS:
            return True
        tokens = set(cleaned.split())
        if tokens.intersection(cls.REJECTION_KEYWORDS):
            return True
        for kw in cls.REJECTION_KEYWORDS:
            if re.search(r'(?:^|\s)' + re.escape(kw) + r'(?:$|\s)', cleaned):
                return True
        return False

    def process_text(self, transcript: str) -> AssistantTurnResponse:
        """
        Processes natural text transcript into extracted products, pricing, and voice response.
        Preserves original customer transcription while maintaining active language preference.
        """
        clean_text = (transcript or "").strip()
        active_lang = self.language_manager.process_transcript(clean_text)
        detected_lang = (
            self.language_manager.last_detection.primary_language
            if self.language_manager.last_detection
            else None
        )

        if not clean_text:
            reply_text = self._get_empty_audio_prompt(active_lang)
            voice_res = self.voice_service.synthesize_response(
                reply_text,
                filename_prefix="empty",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript="",
                response_text=reply_text,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error="Empty transcript.",
                detected_language=detected_lang,
                active_language=active_lang,
            )

        lower = clean_text.lower()

        # Check if this is a correction on an existing pending order (e.g. "Change rice to 3 kilos")
        if self.current_order and self.current_order.status == OrderStatus.PENDING_CONFIRMATION:
            if any(k in lower for k in self.CORRECTION_KEYWORDS):
                return self.correct_current_order(clean_text)

        # Check for conversational confirmation or rejection intent
        if self.current_order and self.current_order.status == OrderStatus.PENDING_CONFIRMATION:
            if self._is_rejection(clean_text):
                return self.cancel_current_order(transcript=clean_text)
            if self._is_confirmation(clean_text):
                return self.confirm_current_order(transcript=clean_text)

        # Step 3: Product & quantity extraction
        extraction_result = self.extractor.extract(clean_text)

        # If order is already pending confirmation and no unambiguous grocery items were extracted, preserve order
        has_new_products = any(not it.is_ambiguous for it in extraction_result.items)
        if not has_new_products and self.current_order and self.current_order.status == OrderStatus.PENDING_CONFIRMATION:
            summary_text = self.voice_service.generate_order_summary(self.current_order, language=active_lang)
            voice_res = self.voice_service.synthesize_response(
                summary_text,
                filename_prefix="summary",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=True,
                transcript=clean_text,
                response_text=summary_text,
                order=self.current_order,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                detected_language=detected_lang,
                active_language=active_lang,
                normalized_items=self._extract_normalized_items(),
                error=voice_res.error if not voice_res.success else None,
            )

        # Step 4: Inventory pricing & order creation
        self.current_order = self.order_manager.create_order_from_extraction(extraction_result)

        # Step 5: Voice summary generation & synthesis in customer's language
        summary_text = self.voice_service.generate_order_summary(self.current_order, language=active_lang)
        voice_res = self.voice_service.synthesize_response(
            summary_text,
            filename_prefix="summary",
            language=active_lang,
        )

        return AssistantTurnResponse(
            success=True,
            transcript=clean_text,
            response_text=summary_text,
            order=self.current_order,
            audio_path=voice_res.audio_path,
            audio_bytes=voice_res.audio_bytes,
            detected_language=detected_lang,
            active_language=active_lang,
            normalized_items=self._extract_normalized_items(),
            error=voice_res.error if not voice_res.success else None,
        )

    def confirm_current_order(self, transcript: str = "confirm") -> AssistantTurnResponse:
        """Confirms the active pending order and generates voice confirmation."""
        active_lang = self.language_manager.active_language

        if not self.current_order:
            if active_lang == LanguageMode.TELUGU:
                reply = "నిర్ధారించడానికి ఎటువంటి ఆర్డర్ లేదు. దయచేసి ముందుగా సరుకులు ఆర్డర్ చేయండి."
            elif active_lang == LanguageMode.HINDI:
                reply = "कन्फर्म करने के लिए कोई सक्रिय ऑर्डर नहीं है। कृपया पहले सामान ऑर्डर करें।"
            elif active_lang == LanguageMode.TENGLISH:
                reply = "Confirm cheyadaniki active order ledu. First items order cheyandi."
            elif active_lang == LanguageMode.HINGLISH:
                reply = "Confirm karne ke liye koi active order nahi hai. Pehle items order kijiye."
            else:
                reply = "There is no active order to confirm. Please start by ordering some items."

            voice_res = self.voice_service.synthesize_response(
                reply,
                filename_prefix="no_order",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript=transcript,
                response_text=reply,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error="No active order.",
                active_language=active_lang,
            )

        success, msg = self.order_manager.confirm_order(self.current_order)
        summary_text = self.voice_service.generate_order_summary(self.current_order, language=active_lang)
        voice_res = self.voice_service.synthesize_response(
            summary_text,
            filename_prefix="confirmed",
            language=active_lang,
        )

        return AssistantTurnResponse(
            success=success,
            transcript=transcript,
            response_text=summary_text,
            order=self.current_order,
            audio_path=voice_res.audio_path,
            audio_bytes=voice_res.audio_bytes,
            error=voice_res.error if not voice_res.success else (None if success else msg),
            active_language=active_lang,
            normalized_items=self._extract_normalized_items(),
        )

    def correct_current_order(self, correction_command: str) -> AssistantTurnResponse:
        """Applies a natural language correction to the active order."""
        active_lang = self.language_manager.active_language

        if not self.current_order:
            if active_lang == LanguageMode.TELUGU:
                reply = "సవరించడానికి ఎటువంటి ఆర్డర్ లేదు."
            elif active_lang == LanguageMode.HINDI:
                reply = "बदलने के लिए कोई सक्रिय ऑर्डर नहीं है।"
            else:
                reply = "There is no active order to modify."

            voice_res = self.voice_service.synthesize_response(
                reply,
                filename_prefix="no_order",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript=correction_command,
                response_text=reply,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error="No active order.",
                active_language=active_lang,
            )

        success, msg = self.order_manager.apply_natural_correction(
            order=self.current_order,
            correction_text=correction_command,
            extractor=self.extractor,
        )

        summary_text = self.voice_service.generate_order_summary(self.current_order, language=active_lang)
        voice_res = self.voice_service.synthesize_response(
            summary_text,
            filename_prefix="updated",
            language=active_lang,
        )

        return AssistantTurnResponse(
            success=success,
            transcript=correction_command,
            response_text=f"{msg} {summary_text}",
            order=self.current_order,
            audio_path=voice_res.audio_path,
            audio_bytes=voice_res.audio_bytes,
            error=voice_res.error if not voice_res.success else (None if success else msg),
            active_language=active_lang,
            normalized_items=self._extract_normalized_items(),
        )

    def cancel_current_order(self, transcript: str = "cancel") -> AssistantTurnResponse:
        """Cancels the active order."""
        active_lang = self.language_manager.active_language

        if not self.current_order:
            if active_lang == LanguageMode.TELUGU:
                reply = "రద్దు చేయడానికి ఎటువంటి ఆర్డర్ లేదు."
            elif active_lang == LanguageMode.HINDI:
                reply = "रद्द करने के लिए कोई सक्रिय ऑर्डर नहीं है।"
            elif active_lang == LanguageMode.TENGLISH:
                reply = "Cancel cheyadaniki active order ledu."
            elif active_lang == LanguageMode.HINGLISH:
                reply = "Cancel karne ke liye koi active order nahi hai."
            else:
                reply = "There is no active order to cancel."

            voice_res = self.voice_service.synthesize_response(
                reply,
                filename_prefix="no_order",
                language=active_lang,
            )
            return AssistantTurnResponse(
                success=False,
                transcript=transcript,
                response_text=reply,
                audio_path=voice_res.audio_path,
                audio_bytes=voice_res.audio_bytes,
                error="No active order.",
                active_language=active_lang,
            )

        success, msg = self.order_manager.cancel_order(self.current_order)
        if active_lang == LanguageMode.TELUGU:
            reply = "మీ ఆర్డర్ రద్దు చేయబడింది."
        elif active_lang == LanguageMode.HINDI:
            reply = "आपका ऑर्डर रद्द कर दिया गया है।"
        elif active_lang == LanguageMode.TENGLISH:
            reply = "Mee order cancel ayindi."
        elif active_lang == LanguageMode.HINGLISH:
            reply = "Aapka order cancel ho gaya hai."
        else:
            reply = "Your order has been cancelled."

        voice_res = self.voice_service.synthesize_response(
            reply,
            filename_prefix="cancelled",
            language=active_lang,
        )

        return AssistantTurnResponse(
            success=success,
            transcript=transcript,
            response_text=reply,
            order=self.current_order,
            audio_path=voice_res.audio_path,
            audio_bytes=voice_res.audio_bytes,
            error=voice_res.error if not voice_res.success else (None if success else msg),
            active_language=active_lang,
            normalized_items=self._extract_normalized_items(),
        )

    def reset(self) -> None:
        """Resets session state."""
        self.current_order = None
