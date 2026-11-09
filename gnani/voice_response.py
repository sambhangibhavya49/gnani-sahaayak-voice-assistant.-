"""
gnani.voice_response
~~~~~~~~~~~~~~~~~~~~
Voice Response Generation and Text-to-Speech Output Service.

Handles:
- Natural, conversational multilingual order summary generation
  (Telugu, Hindi, English, Hinglish, Tenglish).
- Synthesis into speech using Gnani Timbre v2.5 client with language-matched voices.
- Saving generated audio response locally to disk.
- Graceful error handling if TTS synthesis encounters network or API issues.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .languages import LanguageMode, TIMBRE_VOICE_CONFIG
from .order import Order, OrderStatus
from .timbre import TimbreAPIError, TimbreClient, TimbreRateLimitError

logger = logging.getLogger(__name__)


@dataclass
class VoiceResponseResult:
    """Result of voice response generation."""
    summary_text: str
    audio_path: Optional[Path] = None
    audio_bytes: Optional[bytes] = None
    success: bool = True
    error: Optional[str] = None

    def __repr__(self) -> str:
        saved = f"saved to '{self.audio_path.name}'" if self.audio_path else "no audio file"
        return f"VoiceResponseResult(success={self.success}, {saved}, text='{self.summary_text[:40]}...')"


class VoiceResponseService:
    """Generates natural language order summaries and synthesizes them to audio files via Timbre v2.5."""

    DEFAULT_OUTPUT_DIR = Path("output_audio")

    def __init__(
        self,
        timbre_client: TimbreClient,
        output_dir: Optional[Path] = None,
    ):
        self.timbre_client = timbre_client
        self.output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_busy(self) -> bool:
        """Returns True if a TTS synthesis request is currently active."""
        return getattr(self.timbre_client, "is_busy", False)

    def generate_order_summary(
        self,
        order: Order,
        language: Union[LanguageMode, str] = LanguageMode.ENGLISH,
    ) -> str:
        """
        Formats a polite and clear spoken text summary of an order in the target language.
        Supported modes: English, Telugu, Hindi, Hinglish, Tenglish.
        """
        if isinstance(language, str):
            try:
                lang_mode = LanguageMode.from_string(language)
            except ValueError:
                lang_mode = LanguageMode.ENGLISH
        else:
            lang_mode = language

        # If AUTO, default to English for summary unless detected otherwise
        if lang_mode == LanguageMode.AUTO:
            lang_mode = LanguageMode.ENGLISH

        if lang_mode == LanguageMode.TELUGU:
            return self._generate_telugu_summary(order)
        elif lang_mode == LanguageMode.HINDI:
            return self._generate_hindi_summary(order)
        elif lang_mode == LanguageMode.TENGLISH:
            return self._generate_tenglish_summary(order)
        elif lang_mode == LanguageMode.HINGLISH:
            return self._generate_hinglish_summary(order)
        else:
            return self._generate_english_summary(order)

    def _generate_english_summary(self, order: Order) -> str:
        """Default English order summary (matches original milestone specification)."""
        if not order.items and not order.clarifications_needed:
            return "Your cart is currently empty. Please tell me which grocery items you would like to order."

        lines = []
        billable = [it for it in order.items if it.is_billable]
        if billable:
            item_phrases = [
                f"{it.requested_quantity:g} {it.requested_unit or it.inventory_unit} {it.product_name} for {int(it.item_total)} rupees"
                for it in billable
            ]
            if len(item_phrases) == 1:
                lines.append(f"You ordered: {item_phrases[0]}.")
            else:
                lines.append(f"You ordered: {', '.join(item_phrases[:-1])}, and {item_phrases[-1]}.")

        stock_issues = [it for it in order.items if it.status == "insufficient_stock"]
        if stock_issues:
            for it in stock_issues:
                lines.append(f"Notice: {it.note}")

        unavailable = [it for it in order.items if it.status == "unavailable"]
        if unavailable:
            names = ", ".join(it.product_name for it in unavailable)
            lines.append(f"Sorry, {names} is not available in our store.")

        if order.clarifications_needed:
            lines.append(" ".join(order.clarifications_needed))

        if order.status == OrderStatus.CONFIRMED:
            lines.append(f"Your order is confirmed! Total bill is {int(order.total_amount)} rupees. Thank you for shopping with us.")
        elif order.status == OrderStatus.CANCELLED:
            lines.append("Your order has been cancelled.")
        elif billable:
            lines.append(f"Total bill is {int(order.total_amount)} rupees. Would you like to confirm this order?")
        else:
            lines.append("No valid items could be added. Please tell me what you would like to order.")

        return " ".join(lines)

    def _generate_telugu_summary(self, order: Order) -> str:
        """Telugu (తెలుగు) order summary."""
        if not order.items and not order.clarifications_needed:
            return "మీ కార్ట్ ఖాళీగా ఉంది. దయచేసి మీకు కావలసిన కిరాణా సరుకులను చెప్పండి."

        lines = []
        billable = [it for it in order.items if it.is_billable]
        if billable:
            phrases = [
                f"{it.requested_quantity:g} {it.requested_unit or it.inventory_unit} {it.product_name}"
                for it in billable
            ]
            if len(phrases) == 1:
                lines.append(f"సరే అన్నా! {phrases[0]} మీ ఆర్డర్‌లో చేర్చాను.")
            else:
                lines.append(f"సరే అన్నా! {', '.join(phrases[:-1])} మరియు {phrases[-1]} మీ ఆర్డర్‌లో చేర్చాను.")

        stock_issues = [it for it in order.items if it.status == "insufficient_stock"]
        if stock_issues:
            for it in stock_issues:
                lines.append(f"గమనిక: {it.product_name} సరిపడా స్టాక్ లేదు.")

        unavailable = [it for it in order.items if it.status == "unavailable"]
        if unavailable:
            names = ", ".join(it.product_name for it in unavailable)
            lines.append(f"క్షమించండి, {names} మా స్టోర్‌లో అందుబాటులో లేదు.")

        if order.clarifications_needed:
            lines.append(" ".join(order.clarifications_needed))

        if order.status == OrderStatus.CONFIRMED:
            lines.append(f"మీ ఆర్డర్ నిర్ధారించబడింది! మొత్తం బిల్లు {int(order.total_amount)} రూపాయలు. మా వద్ద కొనుగోలు చేసినందుకు ధన్యవాదాలు.")
        elif order.status == OrderStatus.CANCELLED:
            lines.append("మీ ఆర్డర్ రద్దు చేయబడింది.")
        elif billable:
            lines.append(f"మొత్తం బిల్లు {int(order.total_amount)} రూపాయలు. ఈ ఆర్డర్‌ను నిర్ధారించాలా?")
        else:
            lines.append("సరైన సరుకులు నమోదు కాలేదు. దయచేసి మరలా చెప్పండి.")

        return " ".join(lines)

    def _generate_hindi_summary(self, order: Order) -> str:
        """Hindi (हिन्दी) order summary."""
        if not order.items and not order.clarifications_needed:
            return "आपकी कार्ट अभी खाली है। कृपया बताइए आपको कौन सा किराना सामान चाहिए।"

        lines = []
        billable = [it for it in order.items if it.is_billable]
        if billable:
            phrases = [
                f"{it.requested_quantity:g} {it.requested_unit or it.inventory_unit} {it.product_name}"
                for it in billable
            ]
            if len(phrases) == 1:
                lines.append(f"ठीक है! {phrases[0]} आपके ऑर्डर में जोड़ दिया है।")
            else:
                lines.append(f"ठीक है! {', '.join(phrases[:-1])} और {phrases[-1]} आपके ऑर्डर में जोड़ दिया है।")

        stock_issues = [it for it in order.items if it.status == "insufficient_stock"]
        if stock_issues:
            for it in stock_issues:
                lines.append(f"सूचना: {it.product_name} का पर्याप्त स्टॉक उपलब्ध नहीं है।")

        unavailable = [it for it in order.items if it.status == "unavailable"]
        if unavailable:
            names = ", ".join(it.product_name for it in unavailable)
            lines.append(f"क्षमा करें, {names} हमारे पास उपलब्ध नहीं है।")

        if order.clarifications_needed:
            lines.append(" ".join(order.clarifications_needed))

        if order.status == OrderStatus.CONFIRMED:
            lines.append(f"आपका ऑर्डर कन्फर्म हो गया है! कुल बिल {int(order.total_amount)} रुपये है। हमारे यहाँ खरीदारी करने के लिए धन्यवाद!")
        elif order.status == OrderStatus.CANCELLED:
            lines.append("आपका ऑर्डर रद्द कर दिया गया है।")
        elif billable:
            lines.append(f"कुल बिल {int(order.total_amount)} रुपये है। क्या आप यह ऑर्डर कन्फर्म करना चाहते हैं?")
        else:
            lines.append("कोई वैध सामान नहीं जुड़ सका। कृपया दोबारा बताएं।")

        return " ".join(lines)

    def _generate_tenglish_summary(self, order: Order) -> str:
        """Tenglish (Telugu + English) order summary."""
        if not order.items and not order.clarifications_needed:
            return "Mee cart empty ga undi. Please tell me which grocery items kavali."

        lines = []
        billable = [it for it in order.items if it.is_billable]
        if billable:
            phrases = [
                f"{it.requested_quantity:g} {it.requested_unit or it.inventory_unit} {it.product_name}"
                for it in billable
            ]
            if len(phrases) == 1:
                lines.append(f"Sare anna! {phrases[0]} mee order lo add chesanu.")
            else:
                lines.append(f"Sare anna! {', '.join(phrases[:-1])} mariyu {phrases[-1]} mee order lo add chesanu.")

        stock_issues = [it for it in order.items if it.status == "insufficient_stock"]
        if stock_issues:
            for it in stock_issues:
                lines.append(f"Notice: {it.product_name} stock saripodu.")

        unavailable = [it for it in order.items if it.status == "unavailable"]
        if unavailable:
            names = ", ".join(it.product_name for it in unavailable)
            lines.append(f"Sorry, {names} store lo ledu.")

        if order.clarifications_needed:
            lines.append(" ".join(order.clarifications_needed))

        if order.status == OrderStatus.CONFIRMED:
            lines.append(f"Mee order confirm ayindi! Total bill {int(order.total_amount)} rupees. Shopping chesinanduku thanks!")
        elif order.status == OrderStatus.CANCELLED:
            lines.append("Mee order cancel ayindi.")
        elif billable:
            lines.append(f"Total bill {int(order.total_amount)} rupees. Order confirm cheddama?")
        else:
            lines.append("Items add kaledu. Please malli cheppandi.")

        return " ".join(lines)

    def _generate_hinglish_summary(self, order: Order) -> str:
        """Hinglish (Hindi + English) order summary."""
        if not order.items and not order.clarifications_needed:
            return "Aapka cart abhi empty hai. Please batayein aapko kaunsa grocery items chahiye."

        lines = []
        billable = [it for it in order.items if it.is_billable]
        if billable:
            phrases = [
                f"{it.requested_quantity:g} {it.requested_unit or it.inventory_unit} {it.product_name}"
                for it in billable
            ]
            if len(phrases) == 1:
                lines.append(f"Theek hai! {phrases[0]} aapke order mein add kar diya hai.")
            else:
                lines.append(f"Theek hai! {', '.join(phrases[:-1])} aur {phrases[-1]} aapke order mein add kar diya hai.")

        stock_issues = [it for it in order.items if it.status == "insufficient_stock"]
        if stock_issues:
            for it in stock_issues:
                lines.append(f"Notice: {it.product_name} ka stock kam hai.")

        unavailable = [it for it in order.items if it.status == "unavailable"]
        if unavailable:
            names = ", ".join(it.product_name for it in unavailable)
            lines.append(f"Sorry, {names} available nahi hai.")

        if order.clarifications_needed:
            lines.append(" ".join(order.clarifications_needed))

        if order.status == OrderStatus.CONFIRMED:
            lines.append(f"Aapka order confirm ho gaya hai! Total bill {int(order.total_amount)} rupees hai. Shopping karne ke liye dhanyavaad!")
        elif order.status == OrderStatus.CANCELLED:
            lines.append("Aapka order cancel ho gaya hai.")
        elif billable:
            lines.append(f"Total bill {int(order.total_amount)} rupees hai. Kya aap order confirm karna chahte hain?")
        else:
            lines.append("Koi items add nahi hue. Please dobara batayein.")

        return " ".join(lines)

    def synthesize_response(
        self,
        text: str,
        filename_prefix: str = "response",
        language: Optional[Union[LanguageMode, str]] = None,
        voice: Optional[str] = None,
    ) -> VoiceResponseResult:
        """
        Converts text summary to speech via TimbreClient and saves audio locally.
        Routes to language-matched voice where available.
        Gracefully handles TTS failures without breaking caller execution.
        """
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return VoiceResponseResult(
                summary_text="",
                success=False,
                error="Summary text cannot be empty.",
            )

        # Resolve language config
        lang_mode = LanguageMode.ENGLISH
        if language is not None:
            if isinstance(language, str):
                try:
                    lang_mode = LanguageMode.from_string(language)
                except ValueError:
                    lang_mode = LanguageMode.ENGLISH
            else:
                lang_mode = language

        timbre_cfg = TIMBRE_VOICE_CONFIG.get(lang_mode, {"language": "hi-IN", "voice": "Nalini"})
        req_lang = timbre_cfg["language"]
        req_voice = voice or timbre_cfg["voice"]

        try:
            audio_bytes = self.timbre_client.synthesize(
                text=cleaned_text,
                language=req_lang,
                voice=req_voice,
            )
        except TimbreRateLimitError as e:
            logger.warning("Timbre TTS synthesis rate limited: %s", e)
            return VoiceResponseResult(
                summary_text=cleaned_text,
                success=False,
                error=f"Timbre TTS rate limited (HTTP 429): Only one active request is allowed at a time. Please wait for the current audio to finish and retry.",
            )
        except TimbreAPIError as e:
            # If a custom voice failed, safely attempt fallback to standard supported voice 'Nalini'
            if req_voice != "Nalini":
                logger.warning(
                    "Timbre TTS failed for voice '%s' (%s). Attempting safe fallback with 'Nalini'...",
                    req_voice,
                    e,
                )
                try:
                    fallback_lang = req_lang if req_lang in ("te-IN", "hi-IN", "en-IN") else "hi-IN"
                    audio_bytes = self.timbre_client.synthesize(
                        text=cleaned_text,
                        language=fallback_lang,
                        voice="Nalini",
                    )
                except Exception as fb_err:
                    logger.warning("Timbre TTS fallback also failed: %s", fb_err)
                    return VoiceResponseResult(
                        summary_text=cleaned_text,
                        success=False,
                        error=f"Timbre TTS API error: {str(e)}",
                    )
            else:
                logger.warning("Timbre TTS synthesis API error: %s", e)
                return VoiceResponseResult(
                    summary_text=cleaned_text,
                    success=False,
                    error=f"Timbre TTS API error: {str(e)}",
                )
        except Exception as e:
            logger.warning("Failed to synthesize audio response: %s", e)
            return VoiceResponseResult(
                summary_text=cleaned_text,
                success=False,
                error=f"TTS synthesis failure: {str(e)}",
            )

        # Save audio file locally
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        filename = f"{filename_prefix}_{timestamp_str}_{unique_id}.wav"
        output_file = self.output_dir / filename

        try:
            output_file.write_bytes(audio_bytes)
        except IOError as e:
            logger.error("Failed to write audio file to %s: %s", output_file, e)
            return VoiceResponseResult(
                summary_text=cleaned_text,
                audio_bytes=audio_bytes,
                success=False,
                error=f"File save error: {str(e)}",
            )

        return VoiceResponseResult(
            summary_text=cleaned_text,
            audio_path=output_file,
            audio_bytes=audio_bytes,
            success=True,
        )
