"""
scripts.smoke_test
~~~~~~~~~~~~~~~~~~
Smoke test runner for Gnani AI Prisma v2.5 and Timbre v2.5.

Usage:
  # 1. Offline Dry-Run (Default - No live API calls, zero credit consumption):
  python scripts/smoke_test.py --mock

  # 2. Live API Connectivity Test (Requires valid GNANI_API_KEY in .env):
  python scripts/smoke_test.py --live
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# Ensure workspace root is in python path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gnani.config import ConfigError, load_config, mask_secret
from gnani.prisma import PrismaAPIError, PrismaClient
from gnani.timbre import TimbreAPIError, TimbreClient


def print_banner(title: str) -> None:
    print("\n" + "=" * 65)
    print(f" {title}")
    print("=" * 65)


def validate_wav_bytes(audio_bytes: Optional[bytes]) -> Tuple[bool, str]:
    """
    Validates that audio_bytes is non-empty and contains a valid RIFF/WAVE header.

    Checks:
    1. Response is non-empty.
    2. First four bytes are b'RIFF'.
    3. Bytes 8–11 (offset 8 to 12) are b'WAVE'.

    Returns:
        (True, "") if valid, or (False, error_message) if invalid.
    """
    if not audio_bytes:
        return False, "Audio response is empty (0 bytes)."
    if len(audio_bytes) < 12:
        return False, f"Audio response is too short ({len(audio_bytes)} bytes; minimum 12 bytes for RIFF/WAVE header)."
    if not audio_bytes.startswith(b"RIFF"):
        return False, f"Invalid audio header: expected 'RIFF', got {audio_bytes[:4]!r}."
    if audio_bytes[8:12] != b"WAVE":
        return False, f"Invalid audio format: expected 'WAVE' at offset 8-11, got {audio_bytes[8:12]!r}."
    return True, ""


def run_mock_smoke_test(config) -> bool:
    """Runs a simulated offline smoke test to verify logic and payload construction."""
    print_banner("RUNNING OFFLINE MOCK SMOKE TEST (Zero Network Calls)")
    print(f"[OK] Configuration loaded.")
    print(f"     Base URL:        {config.base_url}")
    print(f"     Auth Header:     {config.auth_header}")
    print(f"     API Key (Mask):  {mask_secret(config.api_key)}")
    print(f"     Prisma Lang:     {config.prisma_language}")
    print(f"     Timbre Model:    {config.timbre_model} (Voice: {config.timbre_voice})")

    # 1. Test Mock Timbre
    print("\n[1/2] Testing Timbre v2.5 Client (Mock Mode)...")
    timbre = TimbreClient(config=config, mock_mode=True)
    sample_text = "Aapka order: do kilo Basmati Chawal aur ek kilo Cheeni. Kul rashi 240 rupaye hai."
    audio_bytes = timbre.synthesize(text=sample_text)
    if audio_bytes and len(audio_bytes) > 0 and audio_bytes.startswith(b"RIFF"):
        print(f"     [SUCCESS] Received simulated WAV audio ({len(audio_bytes)} bytes).")
    else:
        print("     [FAILED] Timbre mock did not return valid audio bytes.")
        return False

    # 2. Test Mock Prisma
    print("\n[2/2] Testing Prisma v2.5 Client (Mock Mode)...")
    prisma = PrismaClient(config=config, mock_mode=True)
    stt_result = prisma.transcribe(audio_source=audio_bytes, filename="test_order.wav")
    if stt_result.get("success") and "transcript" in stt_result:
        print(f"     [SUCCESS] Transcript returned: \"{stt_result['transcript']}\"")
        print(f"     [SUCCESS] Request ID: {stt_result.get('request_id')}")
    else:
        print("     [FAILED] Prisma mock did not return expected transcript.")
        return False

    print("\n" + "-" * 65)
    print(" ALL OFFLINE MOCK TESTS PASSED SUCCESSFULLY.")
    print("-" * 65)
    return True


def run_live_smoke_test(config) -> bool:
    """Runs live connectivity smoke test against official Gnani endpoints."""
    print_banner("RUNNING LIVE GNANI API SMOKE TEST")
    print(f"Target Gateway: {config.base_url}")
    print(f"Auth Header:    {config.auth_header}")
    print(f"API Key:        {mask_secret(config.api_key)}")

    # 1. Live TTS Test
    print("\n[1/2] Calling Timbre v2.5 (POST /api/v1/tts/inference)...")
    timbre = TimbreClient(config=config, mock_mode=False)
    test_phrase = "Namaste, Gnani Sahaayak."
    t0 = time.time()
    try:
        audio_bytes = timbre.synthesize(
            text=test_phrase,
            voice=config.timbre_voice,
            language=config.timbre_language,
        )
        latency = (time.time() - t0) * 1000
        print(f"     [SUCCESS] HTTP 200 OK received in {latency:.1f}ms")
        print(f"     [SUCCESS] Received binary audio: {len(audio_bytes)} bytes")
    except TimbreAPIError as e:
        print(f"     [FAILED] Timbre API error (status {e.status_code}): {e}")
        return False
    except Exception as e:
        print(f"     [FAILED] Unexpected connection error: {e}")
        return False

    # Validate received audio format before calling Prisma STT
    valid, err_msg = validate_wav_bytes(audio_bytes)
    if not valid:
        print(f"     [FAILED] Audio validation error: {err_msg}")
        return False

    # 2. Live STT Test
    print("\n[2/2] Calling Prisma v2.5 (POST /stt/v3)...")
    prisma = PrismaClient(config=config, mock_mode=False)
    t0 = time.time()
    try:
        stt_res = prisma.transcribe(
            audio_source=audio_bytes,
            filename="smoke_test.wav",
            language_code=config.prisma_language,
        )
        latency = (time.time() - t0) * 1000
        print(f"     [SUCCESS] HTTP 200 OK received in {latency:.1f}ms")
        print(f"     [SUCCESS] Request ID: {stt_res.get('request_id')}")
        print(f"     [SUCCESS] Transcript: \"{stt_res.get('transcript')}\"")
    except PrismaAPIError as e:
        print(f"     [FAILED] Prisma API error (status {e.status_code}): {e}")
        return False
    except Exception as e:
        print(f"     [FAILED] Unexpected connection error: {e}")
        return False

    print("\n" + "=" * 65)
    print(" LIVE API CONNECTIVITY VERIFIED WITH GNANI CLOUD.")
    print("=" * 65)
    return True


def main():
    parser = argparse.ArgumentParser(description="Gnani Sahaayak API Smoke Test")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute real live API requests to Gnani endpoints (requires valid GNANI_API_KEY).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Run offline mock test without sending network traffic (default behavior).",
    )
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(require_key=args.live)
    except ConfigError as e:
        print(f"\n[ERROR] Configuration failed: {e}")
        print("Please ensure your local .env file contains: GNANI_API_KEY=your_key")
        sys.exit(1)

    if args.live:
        success = run_live_smoke_test(config)
    else:
        success = run_mock_smoke_test(config)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
