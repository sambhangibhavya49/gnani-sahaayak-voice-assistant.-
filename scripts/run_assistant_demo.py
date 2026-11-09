"""
scripts.run_assistant_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~
Interactive and automated demonstration runner for Gnani Sahaayak Voice Assistant.

Features:
- Professional Language Preference Selector:
  * Auto Detect
  * Telugu (తెలుగు)
  * Hindi (हिन्दी)
  * English
  * Hinglish (Hindi + English)
  * Tenglish (Telugu + English)
- Maintains selected language throughout multi-turn conversations.
- Separately displays the original customer transcription and normalized inventory items.

Usage:
  # Run in mock mode with default Auto-Detect / English:
  python scripts/run_assistant_demo.py --mock

  # Run in Telugu mode:
  python scripts/run_assistant_demo.py --mock --language telugu

  # Run in Tenglish mode:
  python scripts/run_assistant_demo.py --mock --language tenglish

  # Run in Hindi mode:
  python scripts/run_assistant_demo.py --mock --language hindi

  # Run in Hinglish mode:
  python scripts/run_assistant_demo.py --mock --language hinglish
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles to safely display Indic scripts and Unicode
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gnani.assistant import VoiceAssistant
from gnani.audio_input import create_dummy_wav
from gnani.config import ConfigError, load_config, mask_secret
from gnani.languages import LanguageMode


def print_header(title: str) -> None:
    print("\n" + "=" * 75)
    print(f" {title}")
    print("=" * 75)


def print_step(step_num: int, title: str) -> None:
    print(f"\n--- [STEP {step_num}] {title} ---")


def display_language_selector_banner(active_mode: LanguageMode) -> None:
    print("\n+" + "-" * 73 + "+")
    print("|         GNANI SAHAAYAK -- MULTILINGUAL LANGUAGE SELECTOR                |")
    print("+" + "-" * 73 + "+")
    options = [
        (LanguageMode.AUTO, "1", "Auto Detect", "Auto-detect script & speech language"),
        (LanguageMode.TELUGU, "2", "Telugu (తెలుగు)", "Pure Telugu conversation & Chitra voice"),
        (LanguageMode.HINDI, "3", "Hindi (हिन्दी)", "Pure Hindi conversation & Nalini voice"),
        (LanguageMode.ENGLISH, "4", "English", "Indian English conversation & Nalini voice"),
        (LanguageMode.HINGLISH, "5", "Hinglish", "Hindi + English mixed conversation"),
        (LanguageMode.TENGLISH, "6", "Tenglish", "Telugu + English mixed conversation"),
    ]
    for mode, num, name, desc in options:
        selected_mark = " [*ACTIVE*]" if mode == active_mode else ""
        print(f"|  [{num}] {name:<17} : {desc:<42}{selected_mark:>8} |")
    print("+" + "-" * 73 + "+")


def get_sample_dialogue_for_language(lang: LanguageMode) -> tuple[str, str, str]:
    """Returns sample (turn1_order, turn2_correction, turn3_confirm) for each language."""
    if lang == LanguageMode.TELUGU:
        return (
            "రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె కావాలి",
            "బియ్యం 3 కిలోలు చేయండి",
            "సరే, ఆర్డర్ కన్ఫర్మ్ చేయండి",
        )
    elif lang == LanguageMode.TENGLISH:
        return (
            "Anna, two kilos biyyam mariyu one litre oil kavali.",
            "Change rice to 3 kilos",
            "Sare anna, confirm",
        )
    elif lang == LanguageMode.HINDI:
        return (
            "दो किलो चावल और एक लीटर तेल देना",
            "चावल 3 किलो कर दो",
            "हाँ, कन्फर्म कर दो",
        )
    elif lang == LanguageMode.HINGLISH:
        return (
            "Bhai, 2 kilos rice aur 1 litre oil dena.",
            "Change rice to 3 kilos",
            "Haan, confirm kar do",
        )
    else:  # English or Auto
        return (
            "Two kilos of rice and one litre of oil.",
            "Change rice to 3 kilos",
            "confirm",
        )


def run_demo(
    mock_mode: bool = True,
    language_mode_str: str = "auto",
    audio_path: Optional[str] = None,
) -> bool:
    try:
        lang_mode = LanguageMode.from_string(language_mode_str)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return False

    mode_str = "OFFLINE MOCK MODE (Zero Network Traffic)" if mock_mode else "LIVE GNANI CLOUD MODE"
    print_header(f"GNANI SAHAAYAK MULTILINGUAL VOICE ASSISTANT DEMO\n Execution Mode: {mode_str}")
    display_language_selector_banner(lang_mode)

    try:
        config = load_config(require_key=not mock_mode)
    except ConfigError as e:
        print(f"[ERROR] Configuration error: {e}")
        return False

    output_dir = WORKSPACE_ROOT / "output_audio"
    assistant = VoiceAssistant(
        config=config,
        mock_mode=mock_mode,
        output_audio_dir=output_dir,
        language_mode=lang_mode,
    )

    print(f"\n[OK] VoiceAssistant initialized.")
    print(f"     Active Language Mode:    {assistant.get_language_mode().display_name}")
    print(f"     Prisma STT Language:     {assistant.language_manager.get_prisma_language_code()}")
    print(f"     Timbre TTS Config:       {assistant.language_manager.get_timbre_config()}")
    print(f"     API Key:                 {mask_secret(config.api_key)}")
    print(f"     Output Audio Directory:  {output_dir}")

    # Prepare sample multi-turn customer dialogues
    t1_text, t2_text, t3_text = get_sample_dialogue_for_language(lang_mode)

    # -----------------------------------------------------------------
    # Step 1: Voice Order Simulation
    # -----------------------------------------------------------------
    print_step(1, f"Customer Speaks Order in {lang_mode.display_name}")
    print(f"Customer Spoken Input: \"{t1_text}\"")

    if audio_path:
        audio_file = Path(audio_path)
        if not audio_file.is_file():
            print(f"[ERROR] Audio file not found: {audio_path}")
            return False
        simulated_wav = audio_file.read_bytes()
        print(f"Audio Input: Loaded user audio from '{audio_file.name}' ({len(simulated_wav)} bytes).")
    elif not mock_mode:
        print(f"Synthesizing spoken audio via Timbre TTS: \"{t1_text}\"...")
        timbre_cfg = assistant.language_manager.get_timbre_config()
        simulated_wav = assistant.timbre_client.synthesize(
            text=t1_text,
            language=timbre_cfg["language"],
            voice=timbre_cfg["voice"],
        )
        print(f"Audio Input: Received synthesized speech ({len(simulated_wav)} bytes).")
    else:
        simulated_wav = create_dummy_wav(duration_seconds=2.0, sample_rate=16000)
        print(f"Audio Input: Generated mock WAV ({len(simulated_wav)} bytes, 2.0s duration).")
        assistant.prisma_client.transcribe = lambda **kwargs: {
            "success": True,
            "request_id": "demo_req_001",
            "timestamp": "20261103_demo",
            "transcript": t1_text,
        }

    turn1 = assistant.process_audio(simulated_wav, filename="customer_turn1.wav")

    # Display original transcription and normalized items separately
    print("\n" + "-" * 60)
    print(f"[ORIGINAL CUSTOMER SPEECH]:   \"{turn1.transcript}\"")
    print(f"[DETECTED LANGUAGE MODE]:     {turn1.detected_language.value if turn1.detected_language else 'N/A'}")
    print(f"[ACTIVE RESPONSE LANGUAGE]:   {turn1.active_language.display_name}")
    print("-" * 60)

    if not turn1.success or turn1.order is None:
        print(f"[SPOKEN ASSISTANT RESPONSE]:  \"{turn1.response_text}\"")
        if turn1.error:
            print(f"[STATUS] Pipeline notice: {turn1.error}")
        return False

    print(f"[NORMALIZED GROCERY ITEMS] ({len(turn1.normalized_items)} items):")
    for item in turn1.normalized_items:
        print(
            f"  * {item['product_name']:<25} | "
            f"Qty: {item['requested_quantity']:g} {item['requested_unit']:<6} | "
            f"Unit Price: Rs. {item['unit_price']:g}/{item['inventory_unit']} | "
            f"Item Total: Rs. {item['item_total']:g} [{item['status']}]"
        )
    print(f"[CALCULATED BILL TOTAL]:      Rs. {turn1.order.total_amount:g}")
    print(f"[SPOKEN ASSISTANT RESPONSE]:  \"{turn1.response_text}\"")
    if turn1.audio_path:
        print(f"[SAVED TTS AUDIO FILE]:       {turn1.audio_path.name}")

    # -----------------------------------------------------------------
    # Step 2: Customer Correction
    # -----------------------------------------------------------------
    print_step(2, f"Customer Correction: '{t2_text}'")
    print(f"Customer says: \"{t2_text}\"")
    turn2 = assistant.correct_current_order(t2_text)

    print("\n" + "-" * 60)
    print(f"[ORIGINAL CUSTOMER SPEECH]:   \"{turn2.transcript}\"")
    print(f"[ACTIVE RESPONSE LANGUAGE]:   {turn2.active_language.display_name}")
    print("-" * 60)

    if turn2.normalized_items:
        print(f"[UPDATED NORMALIZED ITEMS] ({len(turn2.normalized_items)} items):")
        for item in turn2.normalized_items:
            print(
                f"  * {item['product_name']:<25} | "
                f"Qty: {item['requested_quantity']:g} {item['requested_unit']:<6} | "
                f"Item Total: Rs. {item['item_total']:g} [{item['status']}]"
            )
    if turn2.order is not None:
        print(f"[RECALCULATED BILL TOTAL]:    Rs. {turn2.order.total_amount:g}")
    print(f"[SPOKEN ASSISTANT RESPONSE]:  \"{turn2.response_text}\"")
    if turn2.audio_path:
        print(f"[SAVED TTS AUDIO FILE]:       {turn2.audio_path.name}")

    # -----------------------------------------------------------------
    # Step 3: Order Confirmation
    # -----------------------------------------------------------------
    print_step(3, f"Customer Confirmation: '{t3_text}'")
    print(f"Customer says: \"{t3_text}\"")
    turn3 = assistant.confirm_current_order()

    print("\n" + "-" * 60)
    print(f"[ORIGINAL CUSTOMER SPEECH]:   \"{turn3.transcript}\"")
    print(f"[ACTIVE RESPONSE LANGUAGE]:   {turn3.active_language.display_name}")
    print("-" * 60)

    if turn3.order is not None:
        print(f"[FINAL ORDER STATUS]:         {turn3.order.status.value}")
        print(f"[FINAL AMOUNT BILLED]:        Rs. {turn3.order.total_amount:g}")
    print(f"[SPOKEN ASSISTANT RESPONSE]:  \"{turn3.response_text}\"")
    if turn3.audio_path:
        print(f"[SAVED FINAL TTS AUDIO]:      {turn3.audio_path.name}")

    print("\n" + "=" * 75)
    print(f" DEMO COMPLETED SUCCESSFULLY IN {turn3.active_language.display_name.upper()}")
    print("=" * 75)
    return True


def main():
    parser = argparse.ArgumentParser(description="Gnani Sahaayak Multilingual Voice Assistant Demo")
    parser.add_argument("--mock", action="store_true", default=True, help="Run in mock mode (default)")
    parser.add_argument("--live", action="store_true", help="Run with live Gnani APIs")
    parser.add_argument(
        "--language", "-l",
        type=str,
        default="auto",
        choices=["auto", "telugu", "hindi", "english", "hinglish", "tenglish"],
        help="Language mode (default: auto)",
    )
    parser.add_argument("--audio", type=str, default=None, help="Path to custom WAV audio file to test")
    args = parser.parse_args()

    mock = not args.live
    success = run_demo(mock_mode=mock, language_mode_str=args.language, audio_path=args.audio)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
