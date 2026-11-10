"""
GNANI — VOXORA
==============
A Voice-Powered Indian Kirana Experience.

Features:
- Screen A: Welcome / Landing Screen (Voice Threshold)
- Screen B: The Living Bazaar (Asymmetric 42% / 58% Sound Chamber & Grocery Canvas)
- Screen C: Confirmation Seal (Traditional Mercantile Receipt Slate)

Uses existing backend modules:
- gnani.assistant.VoiceAssistant
- gnani.languages.LanguageMode, LanguagePreferenceManager
- gnani.inventory.InventoryManager
- gnani.order.OrderManager, OrderStatus
- gnani.config.load_config
"""

from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gnani.assistant import VoiceAssistant
from gnani.config import GnaniConfig, load_config
from gnani.languages import LanguageMode, TIMBRE_VOICE_CONFIG
from gnani.order import OrderStatus
from gnani.prisma import PrismaClient
from gnani.timbre import TimbreClient


# =============================================================================
# 1. PAGE CONFIGURATION & VOXORA DESIGN SYSTEM (CSS)
# =============================================================================

st.set_page_config(
    page_title="GNANI — VOXORA | Voice Kirana Experience",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

VOXORA_CSS = """
<style>
/* -------------------------------------------------------------
   GNANI — VOXORA DESIGN SYSTEM & DESIGN TOKENS
   Palette:
     Market Orange: #FF6B35
     Electric Blue: #155EEF
     Fresh Teal:    #00A896
     Kinetic Lime:  #D7F75B
     Warm Cream:    #FFF8ED
     Deep Charcoal: #20252B
     Parchment:     #F3ECE0
------------------------------------------------------------- */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;700&family=Noto+Sans+Telugu:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');

:root {
  --market-orange: #FF6B35;
  --electric-blue: #155EEF;
  --fresh-teal: #00A896;
  --kinetic-lime: #D7F75B;
  --warm-cream: #FFF8ED;
  --deep-charcoal: #20252B;
  --parchment: #F3ECE0;
  --ink-muted: #6C747D;
}

/* Background & Global Canvas */
.stApp {
  background-color: #FFF8ED !important;
  color: #20252B !important;
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
}

header[data-testid="stHeader"] {
  background: transparent !important;
}

/* Base typography */
h1, h2, h3, h4, h5, h6 {
  font-family: 'Outfit', sans-serif !important;
  color: #20252B !important;
  letter-spacing: -0.02em;
}

/* Masthead Bar */
.voxora-navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  background-color: #FFF8ED;
  border-bottom: 2px solid #20252B;
  margin-bottom: 24px;
}

.voxora-brand-mark {
  font-family: 'Outfit', sans-serif;
  font-weight: 800;
  font-size: 24px;
  letter-spacing: -0.03em;
  color: #20252B;
  display: flex;
  align-items: center;
  gap: 10px;
}

.voxora-brand-badge {
  background-color: #FF6B35;
  color: #FFF8ED;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1.5px solid #20252B;
  box-shadow: 2px 2px 0px #20252B;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* Tactile Card Containers */
.tactile-card {
  background: #FFFFFF;
  border: 2px solid #20252B;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 4px 4px 0px #20252B;
  margin-bottom: 18px;
}

.tactile-card-inset {
  background: #F3ECE0;
  border: 1.5px solid #20252B;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 14px;
}

/* -------------------------------------------------------------
   LIVING VOICE CORE (PRANA RING)
------------------------------------------------------------- */
.voice-chamber-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 10px;
  background: #FFFFFF;
  border: 2px solid #20252B;
  border-radius: 16px;
  box-shadow: 4px 4px 0px #20252B;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}

.prana-ring-idle {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px solid #FF6B35;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(255,107,53,0.15) 0%, rgba(255,248,237,0) 70%);
  animation: pranaBreathe 3.2s ease-in-out infinite;
  box-shadow: 0 0 25px rgba(255, 107, 53, 0.25);
  cursor: pointer;
}

.prana-ring-listening {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px solid #155EEF;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(21,94,239,0.2) 0%, rgba(215,247,91,0.1) 70%);
  animation: acousticRipple 1.4s ease-out infinite;
  box-shadow: 0 0 35px rgba(21, 94, 239, 0.45);
}

.prana-ring-processing {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px dashed #00A896;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(0,168,150,0.2) 0%, rgba(255,248,237,0) 70%);
  animation: gyroSpin 1.6s linear infinite;
  box-shadow: 0 0 30px rgba(0, 168, 150, 0.35);
}

.prana-ring-speaking {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px solid #FF6B35;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(255,107,53,0.25) 0%, rgba(215,247,91,0.15) 80%);
  animation: speechWave 1.1s ease-in-out infinite;
  box-shadow: 0 0 45px rgba(255, 107, 53, 0.5);
}

.prana-ring-recorded {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px solid #00A896;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(0,168,150,0.2) 0%, rgba(255,248,237,0) 70%);
  animation: pranaBreathe 2.0s ease-in-out infinite;
  box-shadow: 0 0 25px rgba(0, 168, 150, 0.35);
}

.prana-ring-generating {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px dashed #D7F75B;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(215,247,91,0.25) 0%, rgba(255,248,237,0) 70%);
  animation: gyroSpin 1.2s linear infinite;
  box-shadow: 0 0 35px rgba(215, 247, 91, 0.45);
}

.prana-ring-error {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  border: 4px solid #E63946;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle, rgba(230,57,70,0.2) 0%, rgba(255,248,237,0) 70%);
  animation: pranaBreathe 1.5s ease-in-out infinite;
  box-shadow: 0 0 30px rgba(230, 57, 70, 0.4);
}

.prana-center-node {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #20252B;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFF8ED;
  font-size: 20px;
}

@keyframes pranaBreathe {
  0% { transform: scale(1.0); box-shadow: 0 0 15px rgba(255,107,53,0.2); }
  50% { transform: scale(1.08); box-shadow: 0 0 35px rgba(255,107,53,0.45); }
  100% { transform: scale(1.0); box-shadow: 0 0 15px rgba(255,107,53,0.2); }
}

@keyframes acousticRipple {
  0% { transform: scale(0.96); border-color: #155EEF; }
  50% { transform: scale(1.14); border-color: #D7F75B; box-shadow: 0 0 40px rgba(21,94,239,0.55); }
  100% { transform: scale(0.96); border-color: #155EEF; }
}

@keyframes gyroSpin {
  0% { transform: rotate(0deg) scale(1.0); }
  50% { transform: rotate(180deg) scale(1.05); }
  100% { transform: rotate(360deg) scale(1.0); }
}

@keyframes speechWave {
  0% { transform: scale(1.0); border-width: 4px; }
  50% { transform: scale(1.12); border-width: 7px; border-color: #D7F75B; }
  100% { transform: scale(1.0); border-width: 4px; }
}

/* -------------------------------------------------------------
   DYNAMIC GROCERY TILES
------------------------------------------------------------- */
.grocery-tile {
  background: #FFFFFF;
  border: 2px solid #20252B;
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: 3px 3px 0px #20252B;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s ease;
}

.grocery-tile:hover {
  transform: translateY(-2px);
  box-shadow: 5px 5px 0px #20252B;
}

.grocery-tile-title {
  font-family: 'Outfit', sans-serif;
  font-size: 17px;
  font-weight: 700;
  color: #20252B;
}

.grocery-tile-alias {
  font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif;
  font-size: 13px;
  color: #FF6B35;
  font-weight: 600;
  background: #FFF8ED;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(255, 107, 53, 0.3);
  margin-left: 6px;
}

.grocery-tile-price {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
  color: #20252B;
}

.stock-badge-available {
  background: #00A896;
  color: #FFF8ED;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
  letter-spacing: 0.04em;
  display: inline-block;
}

.stock-badge-low {
  background: #FF6B35;
  color: #FFF8ED;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
  display: inline-block;
}

/* -------------------------------------------------------------
   THE VYAPAR CONFIRMATION SEAL
------------------------------------------------------------- */
.vyapar-seal-frame {
  background: #FFFFFF;
  border: 3px solid #20252B;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 6px 6px 0px #20252B;
  position: relative;
  margin-top: 10px;
}

.vyapar-stamp {
  display: inline-block;
  padding: 8px 18px;
  background: #00A896;
  color: #FFF8ED;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 800;
  font-size: 13px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  border: 2px solid #20252B;
  box-shadow: 3px 3px 0px #20252B;
  transform: rotate(-2deg);
  margin-bottom: 20px;
}

/* Grand Total Ledger */
.ledger-total-card {
  background: #20252B;
  color: #FFF8ED;
  border-radius: 10px;
  padding: 18px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
  border: 2px solid #20252B;
  box-shadow: 4px 4px 0px #FF6B35;
}

.ledger-total-amount {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 800;
  color: #D7F75B;
}

/* Streamlit button customizations */
div.stButton > button {
  background-color: #FF6B35 !important;
  color: #FFF8ED !important;
  font-family: 'Space Grotesk', sans-serif !important;
  font-weight: 700 !important;
  font-size: 15px !important;
  border: 2px solid #20252B !important;
  border-radius: 8px !important;
  box-shadow: 3px 3px 0px #20252B !important;
  transition: all 0.15s ease !important;
  padding: 10px 20px !important;
}

div.stButton > button:hover {
  transform: translate(-1px, -1px) !important;
  box-shadow: 4px 4px 0px #20252B !important;
}

div.stButton > button:active {
  transform: translate(2px, 2px) !important;
  box-shadow: 1px 1px 0px #20252B !important;
}

/* Secondary Button Styling */
.stButton button[kind="secondary"] {
  background-color: #F3ECE0 !important;
  color: #20252B !important;
}
</style>
"""

st.markdown(VOXORA_CSS, unsafe_allow_html=True)


# =============================================================================
# 2. SESSION STATE & BACKEND CONNECTION
# =============================================================================

if "screen" not in st.session_state:
    st.session_state.screen = "landing"

if "language_mode" not in st.session_state:
    st.session_state.language_mode = LanguageMode.AUTO

if "voice_state" not in st.session_state:
    st.session_state.voice_state = "idle"

if "last_turn" not in st.session_state:
    st.session_state.last_turn = None

if "last_audio_file" not in st.session_state:
    st.session_state.last_audio_file = None

if "last_mic_hash" not in st.session_state:
    st.session_state.last_mic_hash = None

if "last_upload_hash" not in st.session_state:
    st.session_state.last_upload_hash = None

if "last_recorded_audio" not in st.session_state:
    st.session_state.last_recorded_audio = None

if "last_recorded_filename" not in st.session_state:
    st.session_state.last_recorded_filename = None

try:
    _loaded_config = load_config(require_key=False)
    _has_real_key = bool(
        _loaded_config.api_key
        and _loaded_config.api_key.strip()
        and not _loaded_config.api_key.startswith("mock")
    )
except Exception:
    _loaded_config = GnaniConfig(api_key="mock-key-voxora")
    _has_real_key = False

if "mock_mode" not in st.session_state:
    # If a real API key is configured in .env, default to Live API; otherwise offline mock mode
    st.session_state.mock_mode = not _has_real_key

if "assistant" not in st.session_state:
    # Initialize VoiceAssistant with existing backend configuration
    output_dir = WORKSPACE_ROOT / "output_audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.assistant = VoiceAssistant(
        config=_loaded_config,
        mock_mode=st.session_state.mock_mode,
        output_audio_dir=output_dir,
        language_mode=st.session_state.language_mode,
    )

assistant: VoiceAssistant = st.session_state.assistant
# Synchronize mock_mode across assistant and active sub-clients
assistant.mock_mode = st.session_state.mock_mode
assistant.prisma_client.mock_mode = st.session_state.mock_mode
assistant.timbre_client.mock_mode = st.session_state.mock_mode
assistant.speech_recognizer.mock_mode = st.session_state.mock_mode


# =============================================================================
# 3. TOP NAVIGATION & MASTHEAD BAR
# =============================================================================

def render_top_navbar():
    col1, col2 = st.columns([4, 6])
    with col1:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-family: 'Outfit', sans-serif; font-weight: 800; font-size: 26px; color: #20252B;">
                    GNANI <span style="color: #FF6B35;">— VOXORA</span>
                </span>
                <span class="voxora-brand-badge">Kirana Voice AI</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        # Language Selector Bar
        lang_options = [
            ("auto", "Auto Detect"),
            ("telugu", "తెలుగు"),
            ("hindi", "हिन्दी"),
            ("english", "English"),
            ("hinglish", "Hinglish"),
            ("tenglish", "Tenglish"),
        ]
        mode_to_key = {
            LanguageMode.AUTO: "auto",
            LanguageMode.TELUGU: "telugu",
            LanguageMode.HINDI: "hindi",
            LanguageMode.ENGLISH: "english",
            LanguageMode.HINGLISH: "hinglish",
            LanguageMode.TENGLISH: "tenglish",
        }
        current_expected_key = mode_to_key.get(st.session_state.language_mode, "auto")
        if st.session_state.get("lang_radio_select") != current_expected_key:
            st.session_state["lang_radio_select"] = current_expected_key

        selected_key = st.radio(
            label="Language Selection",
            options=[opt[0] for opt in lang_options],
            format_func=lambda k: next(opt[1] for opt in lang_options if opt[0] == k),
            horizontal=True,
            label_visibility="collapsed",
            key="lang_radio_select",
        )

        target_mode = LanguageMode.from_string(selected_key)
        if target_mode != st.session_state.language_mode:
            st.session_state.language_mode = target_mode
            assistant.set_language_mode(target_mode)
            st.rerun()


def render_screen_nav():
    nav1, nav2, nav3, nav4, nav5 = st.columns([1.1, 1.4, 1.1, 1.8, 1.4])
    with nav1:
        is_active = (st.session_state.screen == "landing")
        label = "● 🏠 Welcome" if is_active else "🏠 Welcome"
        if st.button(label, key="nav_btn_landing", use_container_width=True):
            st.session_state.screen = "landing"
            st.session_state.voice_state = "idle"
            st.rerun()
    with nav2:
        is_active = (st.session_state.screen == "interaction")
        label = "● 🛒 Living Bazaar" if is_active else "🛒 Living Bazaar"
        if st.button(label, key="nav_btn_interaction", use_container_width=True):
            st.session_state.screen = "interaction"
            st.rerun()
    with nav3:
        is_active = (st.session_state.screen == "confirmation")
        label = "● 🧾 Vyapar Seal" if is_active else "🧾 Vyapar Seal"
        if st.button(label, key="nav_btn_confirmation", use_container_width=True):
            st.session_state.screen = "confirmation"
            st.rerun()
    with nav4:
        mode_text = "OFFLINE MOCK" if st.session_state.mock_mode else "LIVE API"
        mode_color = "#6C747D" if st.session_state.mock_mode else "#00A896"
        st.markdown(
            f"""
            <div style="text-align: right; font-size: 11px; font-weight: 700; color: #6C747D; padding-top: 10px;">
                STATUS: <span style="color: #00A896;">● READY</span> &bull; 
                ENGINE: <span style="color: {mode_color};">{mode_text}</span> &bull; 
                ACTIVE: <span style="color: #155EEF;">{st.session_state.language_mode.display_name}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with nav5:
        btn_label = "Switch to Live API 🌐" if st.session_state.mock_mode else "Switch to Mock 🧪"
        if st.button(btn_label, key="btn_toggle_engine", use_container_width=True):
            new_mode = not st.session_state.mock_mode
            if not new_mode and not _has_real_key:
                st.warning("No GNANI_API_KEY found in .env. Running Live API requires valid credentials.")
            st.session_state.mock_mode = new_mode
            assistant.mock_mode = new_mode
            assistant.prisma_client.mock_mode = new_mode
            assistant.timbre_client.mock_mode = new_mode
            assistant.speech_recognizer.mock_mode = new_mode
            st.rerun()


render_top_navbar()
render_screen_nav()
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)


# =============================================================================
# 4. SCREEN A: LANDING / WELCOME SCREEN ("The Voice Threshold")
# =============================================================================

def render_landing_screen():
    st.session_state.voice_state = "idle"
    is_stt_busy = getattr(assistant, "is_stt_busy", False) or PrismaClient.is_transcribing()
    is_tts_busy = getattr(assistant, "is_tts_busy", False) or TimbreClient.is_synthesizing()
    is_api_busy = is_stt_busy or is_tts_busy

    if is_stt_busy:
        st.info("⏳ Speech transcription (Prisma STT) is currently in progress. Only one active STT request is permitted at a time. Please wait a moment...")
    elif is_tts_busy:
        st.info("⏳ Spoken audio generation (Timbre TTS) is currently in progress. Only one active TTS request is permitted at a time. Please wait a moment...")

    st.markdown(
        """
        <div style="text-align: center; max-width: 820px; margin: 24px auto 32px auto;">
            <h1 style="font-size: 44px; font-weight: 800; line-height: 1.15; margin-bottom: 14px;">
                Kirana shopping at the speed of spoken thought.
            </h1>
            <p style="font-size: 17px; color: #6C747D; font-weight: 500;">
                Speak naturally in Telugu, Hindi, English, Hinglish, or Tenglish.
                Zero typing. Immediate product recognition. Automated billing.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Centerpiece: Large Living Voice Core (Idle State)
    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        st.markdown(
            """
            <div class="voice-chamber-container" style="border: 2.5px solid #20252B;">
                <div class="prana-ring-idle">
                    <div class="prana-center-node">🎙️</div>
                </div>
                <div style="margin-top: 18px; font-weight: 700; font-size: 14px; color: #20252B; letter-spacing: 0.05em;">
                    PRANA VOICE CORE • READY
                </div>
                <div style="font-size: 12px; color: #6C747D; margin-top: 4px;">
                    Language: <b style="color: #FF6B35;">{}</b>
                </div>
            </div>
            """.format(st.session_state.language_mode.display_name),
            unsafe_allow_html=True,
        )

        if st.button("▶  START VOICE ORDERING", use_container_width=True, disabled=is_api_busy):
            st.session_state.screen = "interaction"
            st.session_state.voice_state = "idle"
            st.rerun()

    # Conversational Starter Prompt Chips
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="max-width: 860px; margin: 0 auto; text-align: center;">
            <div style="font-size: 13px; font-weight: 700; color: #20252B; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px;">
                TRY SPEAKING ANY OF THESE COLLOQUIAL ORDERS:
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        if st.button('🗣️ "రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె" (Telugu)', use_container_width=True, disabled=is_api_busy):
            st.session_state.language_mode = LanguageMode.TELUGU
            assistant.set_language_mode(LanguageMode.TELUGU)
            st.session_state.screen = "interaction"
            res = assistant.process_text("రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె")
            st.session_state.last_turn = res
            st.session_state.voice_state = "speaking"
            st.rerun()

        if st.button('🗣️ "Anna, two kilos biyyam kavali" (Tenglish)', use_container_width=True, disabled=is_api_busy):
            st.session_state.language_mode = LanguageMode.TENGLISH
            assistant.set_language_mode(LanguageMode.TENGLISH)
            st.session_state.screen = "interaction"
            res = assistant.process_text("Anna, two kilos biyyam kavali")
            st.session_state.last_turn = res
            st.session_state.voice_state = "speaking"
            st.rerun()

    with p_col2:
        if st.button('🗣️ "दो किलो चावल और एक लीटर तेल देना" (Hindi)', use_container_width=True, disabled=is_api_busy):
            st.session_state.language_mode = LanguageMode.HINDI
            assistant.set_language_mode(LanguageMode.HINDI)
            st.session_state.screen = "interaction"
            res = assistant.process_text("दो किलो चावल और एक लीटर तेल देना")
            st.session_state.last_turn = res
            st.session_state.voice_state = "speaking"
            st.rerun()

        if st.button('🗣️ "Bhai, ek kilo rice aur half kilo sugar dena" (Hinglish)', use_container_width=True, disabled=is_api_busy):
            st.session_state.language_mode = LanguageMode.HINGLISH
            assistant.set_language_mode(LanguageMode.HINGLISH)
            st.session_state.screen = "interaction"
            res = assistant.process_text("Bhai, ek kilo rice aur half kilo sugar dena")
            st.session_state.last_turn = res
            st.session_state.voice_state = "speaking"
            st.rerun()


# =============================================================================
# 5. SCREEN B: THE LIVING BAZAAR — VOICE INTERACTION & GROCERY CANVAS
# =============================================================================

def render_interaction_screen():
    # Detect if either STT or TTS is actively processing
    is_stt_busy = getattr(assistant, "is_stt_busy", False) or PrismaClient.is_transcribing()
    is_tts_busy = getattr(assistant, "is_tts_busy", False) or TimbreClient.is_synthesizing()
    is_api_busy = is_stt_busy or is_tts_busy

    # Auto-heal orphaned 'transcribing' state if no background STT request is actually active
    if st.session_state.voice_state == "transcribing" and not is_stt_busy:
        st.session_state.voice_state = (
            "error"
            if (st.session_state.last_turn and not st.session_state.last_turn.success)
            else "idle"
        )

    # Asymmetric Split: 42% Left Sound Chamber, 58% Right Grocery Canvas
    col_sound, col_canvas = st.columns([42, 58])

    # -------------------------------------------------------------
    # LEFT SOUND CHAMBER (42%)
    # -------------------------------------------------------------
    with col_sound:
        st.markdown(
            f"""
            <div style="font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 800; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                <span>ACOUSTIC SOUND CHAMBER</span>
                <span style="font-size: 12px; font-weight: 700; background: #D7F75B; padding: 2px 8px; border-radius: 4px; border: 1.5px solid #20252B;">
                    MODE: {st.session_state.language_mode.display_name.upper()}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Dynamic Living Voice Core (8 State Matrix)
        v_state = st.session_state.voice_state
        state_info = {
            "mic_ready": ("MICROPHONE READY", "prana-ring-idle", "🎙️"),
            "idle": ("MICROPHONE READY", "prana-ring-idle", "🎙️"),
            "recording": ("RECORDING LIVE AUDIO...", "prana-ring-listening", "🔴"),
            "recording_complete": ("RECORDING COMPLETE", "prana-ring-recorded", "⏹️"),
            "transcribing": ("TRANSCRIBING (PRISMA v2.5)...", "prana-ring-processing", "🌐"),
            "order_processing": ("ORDER PROCESSING...", "prana-ring-processing", "🛒"),
            "generating_voice": ("GENERATING AI VOICE (TIMBRE v2.5)...", "prana-ring-generating", "🔊"),
            "voice_ready": ("AI VOICE READY", "prana-ring-speaking", "📢"),
            "speaking": ("AI VOICE READY", "prana-ring-speaking", "📢"),
            "error": ("PLAYBACK FAILED / API ERROR", "prana-ring-error", "⚠️"),
        }.get(v_state, ("MICROPHONE READY", "prana-ring-idle", "🎙️"))

        state_label, ring_class, center_icon = state_info

        st.markdown(
            f"""
            <div class="voice-chamber-container">
                <div class="{ring_class}">
                    <div class="prana-center-node">{center_icon}</div>
                </div>
                <div style="margin-top: 14px; font-weight: 800; font-size: 13px; color: #20252B; letter-spacing: 0.06em;">
                    {state_label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if v_state not in ("idle", "mic_ready"):
            if st.button("🔄 Reset Voice Core to Ready (Idle)", key="btn_reset_idle", use_container_width=True):
                PrismaClient.reset_lock()
                TimbreClient.reset_lock()
                st.session_state["last_mic_hash"] = None
                st.session_state["last_upload_hash"] = None
                st.session_state.voice_state = "idle"
                st.rerun()

        # Voice & Speech Controls with 3 Input Methods
        st.markdown(
            """
            <div style="font-family: 'Outfit', sans-serif; font-size: 13px; font-weight: 800; color: #20252B; text-transform: uppercase; letter-spacing: 0.06em; margin: 12px 0 6px 0;">
                🎙️ Voice & Speech Input Controls
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_stt_busy:
            st.info("⏳ Speech transcription (Prisma STT) is currently in progress. The Prisma STT service allows only one active request at a time. Please wait a moment...")
        elif is_tts_busy:
            st.info("⏳ Spoken audio generation (Timbre TTS) is currently in progress. The Timbre TTS service allows only one active request at a time. Please wait a moment...")

        tab_mic, tab_upload, tab_text = st.tabs([
            "🎤 Live Microphone",
            "📁 Upload .WAV",
            "⌨️ Typed Speech",
        ])

        with tab_mic:
            st.caption("Record live customer speech via browser microphone (16 kHz PCM WAV):")

            with st.expander("🔒 Browser Microphone Permissions & Setup Help", expanded=False):
                st.markdown(
                    """
                    **How to enable microphone access:**
                    1. Click **Allow** when your browser prompts for microphone permission.
                    2. If blocked: Click the **Lock / Tune icon (🔒)** in the address bar next to `localhost:8501`.
                    3. Under **Permissions**, set **Microphone** to **Allow**.
                    4. Refresh this tab to activate recording.
                    """
                )

            mic_audio = st.audio_input(
                "Record Voice Order",
                label_visibility="collapsed",
                key="live_mic_recorder",
                help="Click to start recording your grocery order",
            )

            if mic_audio is None:
                st.info("🎙️ Microphone Ready. Click the microphone button above to record your spoken order.")
            elif not isinstance(mic_audio, list):
                audio_bytes = mic_audio.getvalue()
                audio_hash = hashlib.md5(audio_bytes).hexdigest()
                duration_s = max(0.1, len(audio_bytes) / 32000.0)
                size_kb = len(audio_bytes) / 1024.0

                # Customer Recorded Audio Preview & Session Preservation
                st.session_state["last_recorded_audio"] = audio_bytes
                st.session_state["last_recorded_filename"] = "live_mic_recording.wav"

                st.markdown(
                    f"""
                    <div class="tactile-card-inset" style="margin-top: 8px; border-left: 4px solid #155EEF; padding: 10px 14px;">
                        <div style="font-size: 11px; font-weight: 700; color: #155EEF; text-transform: uppercase;">
                            🎧 Your Recorded Voice Preview
                        </div>
                        <div style="font-size: 12px; color: #6C747D; margin-top: 2px;">
                            Duration: <b>{duration_s:.1f}s</b> &bull; Size: <b>{size_kb:.1f} KB</b> &bull; Format: <b>16 kHz PCM WAV</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.audio(audio_bytes, format="audio/wav")

                auto_proc = st.checkbox("Auto-process order immediately on record", value=True, key="chk_auto_proc")

                c_proc, c_canc = st.columns([2, 1])
                proc_clicked = False
                with c_proc:
                    if st.button("⚡ Transcribe & Process Voice Order", key="btn_proc_mic_explicit", use_container_width=True, disabled=is_api_busy):
                        proc_clicked = True
                with c_canc:
                    if st.button("✕ Discard Recording", key="btn_discard_mic", use_container_width=True):
                        st.session_state["last_mic_hash"] = None
                        st.session_state["last_recorded_audio"] = None
                        st.session_state.voice_state = "idle"
                        st.rerun()

                should_process = (auto_proc and st.session_state.get("last_mic_hash") != audio_hash) or proc_clicked
                if should_process and not is_api_busy:
                    st.session_state["last_mic_hash"] = audio_hash
                    st.session_state.voice_state = "transcribing"
                    try:
                        turn_res = assistant.process_audio(audio_bytes, filename="live_mic_recording.wav")
                        st.session_state.last_turn = turn_res
                        if turn_res.success:
                            st.session_state.voice_state = "voice_ready" if turn_res.audio_path else "speaking"
                            if turn_res.order and turn_res.order.status == OrderStatus.CONFIRMED:
                                st.session_state.screen = "confirmation"
                        else:
                            st.session_state.voice_state = "error"
                    except Exception:
                        st.session_state.voice_state = "error"
                    finally:
                        if st.session_state.voice_state == "transcribing":
                            st.session_state.voice_state = "error"
                    st.rerun()

        with tab_upload:
            st.caption("Upload pre-recorded audio file (.wav format, &le; 60 seconds):")
            uploaded_audio = st.file_uploader(
                "Upload .wav audio",
                type=["wav"],
                label_visibility="collapsed",
                key="customer_audio_file",
            )
            if uploaded_audio is not None and not isinstance(uploaded_audio, list):
                audio_bytes = uploaded_audio.getvalue()
                audio_hash = hashlib.md5(audio_bytes).hexdigest()
                file_name = getattr(uploaded_audio, "name", "customer_audio.wav")
                st.session_state["last_recorded_audio"] = audio_bytes
                st.session_state["last_recorded_filename"] = file_name
                st.audio(audio_bytes, format="audio/wav")
                if st.session_state.get("last_upload_hash") != audio_hash and not is_api_busy:
                    st.session_state["last_upload_hash"] = audio_hash
                    st.session_state.voice_state = "transcribing"
                    try:
                        turn_res = assistant.process_audio(audio_bytes, filename=file_name)
                        st.session_state.last_turn = turn_res
                        if turn_res.success:
                            st.session_state.voice_state = "voice_ready" if turn_res.audio_path else "speaking"
                            if turn_res.order and turn_res.order.status == OrderStatus.CONFIRMED:
                                st.session_state.screen = "confirmation"
                        else:
                            st.session_state.voice_state = "error"
                    except Exception:
                        st.session_state.voice_state = "error"
                    finally:
                        if st.session_state.voice_state == "transcribing":
                            st.session_state.voice_state = "error"
                    st.rerun()

        with tab_text:
            st.caption("Type customer spoken speech or grocery query directly:")
            user_speech_input = st.text_input(
                "Customer Speech Query:",
                placeholder="e.g. రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె కావాలి",
                label_visibility="collapsed",
                key="customer_speech_text",
            )
            if st.button("⚡ Process Text Order Turn", use_container_width=True, key="btn_proc_text", disabled=is_api_busy):
                if user_speech_input.strip() and not is_api_busy:
                    st.session_state.voice_state = "order_processing"
                    turn_res = assistant.process_text(user_speech_input)
                    st.session_state.last_turn = turn_res
                    if turn_res.success:
                        st.session_state.voice_state = "voice_ready" if turn_res.audio_path else "speaking"
                        if turn_res.order and turn_res.order.status == OrderStatus.CONFIRMED:
                            st.session_state.screen = "confirmation"
                    else:
                        st.session_state.voice_state = "error"
                    st.rerun()

        # Verbatim Transcript & Assistant Response Display with Error/Success states
        if st.session_state.last_turn:
            turn = st.session_state.last_turn
            if not turn.success:
                err_text = str(turn.error or "")
                if "429" in err_text or "rate limit" in err_text.lower() or "already in progress" in err_text.lower():
                    st.warning(
                        "⚠️ Prisma STT Rate Limited (HTTP 429): Only one active speech recognition request is permitted at a time. "
                        "Your recorded voice audio and current grocery cart are safely preserved. Click below to retry once the current request completes."
                    )
                elif any(code in err_text for code in ["504", "502", "503"]) or "gateway" in err_text.lower() or "timeout" in err_text.lower():
                    st.warning(
                        "⚠️ Speech Recognition Gateway Latency / Timeout (HTTP 504): The speech recognition service experienced temporary latency. "
                        "Your recorded voice audio and current grocery cart are safely preserved. Click 'Retry Speech Recognition' below to re-submit without recording again."
                    )
                else:
                    st.error(f"⚠️ Speech-to-Text / Audio Error: {turn.error or 'Speech recognition failed. Please try again.'}")

                # Manual Retry Button for Prisma STT using preserved recorded audio
                if st.session_state.get("last_recorded_audio"):
                    if st.button("🔄 Retry Speech Recognition (Prisma STT)", key="btn_retry_stt", use_container_width=True, disabled=is_api_busy):
                        st.session_state.voice_state = "transcribing"
                        rec_bytes = st.session_state["last_recorded_audio"]
                        rec_name = st.session_state.get("last_recorded_filename", "customer_order.wav")
                        try:
                            retry_turn = assistant.process_audio(rec_bytes, filename=rec_name)
                            st.session_state.last_turn = retry_turn
                            if retry_turn.success:
                                st.session_state.voice_state = "voice_ready" if retry_turn.audio_path else "speaking"
                                if retry_turn.order and retry_turn.order.status == OrderStatus.CONFIRMED:
                                    st.session_state.screen = "confirmation"
                                st.success("✓ Speech recognized and order processed successfully!")
                            else:
                                st.session_state.voice_state = "error"
                        except Exception:
                            st.session_state.voice_state = "error"
                        finally:
                            if st.session_state.voice_state == "transcribing":
                                st.session_state.voice_state = "error"
                        st.rerun()
            else:
                st.success("✓ Spoken order turn processed and updated on Grocery Canvas!")

            st.markdown(
                f"""
                <div class="tactile-card" style="padding: 16px; margin-top: 10px;">
                    <div style="font-size: 11px; font-weight: 700; color: #155EEF; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                        Customer Verbatim Speech (Prisma STT)
                    </div>
                    <div style="font-size: 16px; font-weight: 600; color: #20252B; font-family: 'Space Grotesk', sans-serif;">
                        "{turn.transcript}"
                    </div>
                    <div style="margin-top: 6px; font-size: 12px; color: #6C747D;">
                        Detected Language: <b style="color: #20252B;">{turn.active_language.display_name}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            voice_cfg = TIMBRE_VOICE_CONFIG.get(turn.active_language, {"voice": "Nalini", "language": "hi-IN"})
            st.markdown(
                f"""
                <div class="tactile-card-inset" style="border-left: 4px solid #FF6B35;">
                    <div style="font-size: 11px; font-weight: 700; color: #FF6B35; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                        Assistant Spoken Response ({voice_cfg['voice']} • {voice_cfg['language']})
                    </div>
                    <div style="font-size: 15px; font-weight: 600; color: #20252B;">
                        "{turn.response_text}"
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Localized Audio Playback (Timbre TTS)
            if turn.audio_path and turn.audio_path.is_file():
                # Standard visible HTML5 audio player with autoplay
                st.audio(
                    str(turn.audio_path),
                    format="audio/wav",
                    autoplay=True,
                )

                # Browser Autoplay Attempt with Data URI
                try:
                    raw_audio = turn.audio_path.read_bytes()
                    b64_audio = base64.b64encode(raw_audio).decode("ascii")
                    st.markdown(
                        f"""
                        <audio id="voxora-spoken-response" src="data:audio/wav;base64,{b64_audio}" autoplay style="display:none;"></audio>
                        <script>
                            const audioElem = document.getElementById('voxora-spoken-response');
                            if (audioElem) {{
                                audioElem.play().catch(function(err) {{
                                    console.log('Browser autoplay policy deferred playback:', err);
                               }});
                            }}
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception:
                    pass

                # Play / Replay button controls
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    if st.button("▶️ Play AI Response", key="btn_play_audio", use_container_width=True, disabled=is_api_busy):
                        st.session_state.voice_state = "speaking"
                        st.rerun()
                with p_col2:
                    if st.button("🔁 Replay Voice Response", key="btn_replay_audio", use_container_width=True, disabled=is_api_busy):
                        st.session_state.voice_state = "speaking"
                        st.rerun()
            else:
                # TTS failure notice with Retry button
                if is_tts_busy:
                    st.info("⏳ Spoken audio generation is currently in progress. The Timbre TTS service allows only one active request at a time. Please wait a moment...")
                else:
                    err_str = str(turn.error or "")
                    if "429" in err_str or "rate limit" in err_str.lower() or "already in progress" in err_str.lower():
                        st.warning(
                            "⚠️ Timbre TTS Rate Limited (HTTP 429): Only one active voice synthesis request is permitted at a time. "
                            "Your customer transcript and grocery cart remain intact on the canvas."
                        )
                    else:
                        st.warning(
                            f"⚠️ AI Voice Synthesis unavailable: {turn.error or 'Spoken audio could not be synthesized.'} "
                            "Your grocery items and transcript remain intact on the canvas."
                        )
                    if st.button("🔄 Retry Voice Response (Timbre TTS)", key="btn_retry_tts", use_container_width=True, disabled=is_api_busy):
                        st.session_state.voice_state = "generating_voice"
                        retry_res = assistant.voice_service.synthesize_response(
                            turn.response_text,
                            language=turn.active_language,
                        )
                        if retry_res.success and retry_res.audio_path:
                            turn.audio_path = retry_res.audio_path
                            turn.audio_bytes = retry_res.audio_bytes
                            turn.error = None
                            st.session_state.voice_state = "voice_ready"
                            st.success("✓ Spoken voice response synthesized successfully!")
                            st.rerun()
                        else:
                            st.session_state.voice_state = "error"
                            turn.error = retry_res.error
                            st.error(f"⚠️ Retry synthesis failed: {retry_res.error}")

        # Conversational Corrections Quick-Chips
        st.markdown("<div style='font-size: 12px; font-weight: 700; margin: 14px 0 6px 0;'>CONVERSATIONAL CORRECTION CHIPS:</div>", unsafe_allow_html=True)
        c_chip1, c_chip2 = st.columns(2)
        with c_chip1:
            if st.button('✏️ "బియ్యం 3 కిలోలు చేయండి"', use_container_width=True, key="chip_te", disabled=is_api_busy):
                st.session_state.voice_state = "processing"
                turn_res = assistant.correct_current_order("బియ్యం 3 కిలోలు చేయండి")
                st.session_state.last_turn = turn_res
                st.session_state.voice_state = "speaking"
                st.rerun()

        with c_chip2:
            if st.button('✏️ "Change rice to 3 kilos"', use_container_width=True, key="chip_en", disabled=is_api_busy):
                st.session_state.voice_state = "processing"
                turn_res = assistant.correct_current_order("Change rice to 3 kilos")
                st.session_state.last_turn = turn_res
                st.session_state.voice_state = "speaking"
                st.rerun()

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        if st.button("←  Back to Welcome Screen", use_container_width=True, key="btn_back_welcome"):
            st.session_state.screen = "landing"
            st.session_state.voice_state = "idle"
            st.rerun()

    # -------------------------------------------------------------
    # RIGHT DYNAMIC GROCERY CANVAS (58%)
    # -------------------------------------------------------------
    with col_canvas:
        order = assistant.current_order
        item_count = len(order.items) if order else 0

        st.markdown(
            f"""
            <div style="font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 800; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                <span>DYNAMIC GROCERY CANVAS</span>
                <span style="font-size: 13px; font-weight: 700; background: #00A896; color: #FFF8ED; padding: 3px 10px; border-radius: 9999px; border: 1.5px solid #20252B;">
                    {item_count} ITEMS VERIFIED
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not order or not order.items:
            st.markdown(
                """
                <div class="tactile-card" style="text-align: center; padding: 48px 20px;">
                    <div style="font-size: 36px; margin-bottom: 12px;">🧺</div>
                    <div style="font-size: 18px; font-weight: 700; color: #20252B;">Your Grocery Canvas is Empty</div>
                    <p style="font-size: 14px; color: #6C747D; margin-top: 6px;">
                        Speak an order using the Sound Chamber on the left, or click one of the quick suggestions.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Display item tiles
            for idx, item in enumerate(order.items):
                status_badge = (
                    '<span class="stock-badge-available">● IN STOCK</span>'
                    if item.status == "available"
                    else f'<span class="stock-badge-low">⚠ {item.status.upper()}</span>'
                )

                st.markdown(
                    f"""
                    <div class="grocery-tile">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center;">
                                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14px; color: #FF6B35; margin-right: 8px;">
                                    {idx + 1:02d}.
                                </span>
                                <span class="grocery-tile-title">{item.product_name}</span>
                            </div>
                            <div style="font-size: 13px; color: #6C747D; margin-top: 4px;">
                                Rate: Rs. {item.unit_price:g}/{item.inventory_unit} &bull; Requested: <b>{item.requested_quantity:g} {item.requested_unit}</b> &bull; {status_badge}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div class="grocery-tile-price">Rs. {item.item_total:g}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Micro-Steppers for quantity modification
                s_col1, s_col2, s_col3, _spacer = st.columns([1, 1, 1, 3])
                with s_col1:
                    if st.button("➖ 1", key=f"dec_{idx}", use_container_width=True, disabled=is_api_busy):
                        new_q = max(0.5, item.requested_quantity - 1.0)
                        assistant.order_manager.modify_item_quantity(order, item.product_name, new_q)
                        st.rerun()
                with s_col2:
                    if st.button("➕ 1", key=f"inc_{idx}", use_container_width=True, disabled=is_api_busy):
                        new_q = item.requested_quantity + 1.0
                        assistant.order_manager.modify_item_quantity(order, item.product_name, new_q)
                        st.rerun()
                with s_col3:
                    if st.button("🗑️ Del", key=f"del_{idx}", use_container_width=True, disabled=is_api_busy):
                        assistant.order_manager.remove_item(order, item.product_name)
                        st.rerun()

            # Grand Total Ledger Card
            st.markdown(
                f"""
                <div class="ledger-total-card">
                    <div>
                        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #D7F75B;">
                            ORDER SUB-TOTAL
                        </div>
                        <div style="font-size: 13px; color: #FFF8ED; opacity: 0.85;">
                            All staples verified against Kirana catalog
                        </div>
                    </div>
                    <div class="ledger-total-amount">
                        Rs. {order.total_amount:g}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Order Confirmation and Reset actions
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            act_col1, act_col2 = st.columns([1, 1])
            with act_col1:
                if st.button("✓  CONFIRM ORDER (సరే / हाँ)", use_container_width=True, disabled=is_api_busy):
                    res = assistant.confirm_current_order()
                    st.session_state.last_turn = res
                    st.session_state.screen = "confirmation"
                    st.rerun()

            with act_col2:
                if st.button("✕  Clear Order", use_container_width=True, disabled=is_api_busy):
                    assistant.cancel_current_order()
                    st.session_state.last_turn = None
                    st.rerun()


# =============================================================================
# 6. SCREEN C: CONFIRMATION SEAL ("The Vyapar Seal")
# =============================================================================

def render_confirmation_screen():
    order = assistant.current_order
    turn = st.session_state.last_turn

    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 24px;">
            <div class="vyapar-stamp">
                ✓ VYAPAR VERIFIED & RESERVED • 2026
            </div>
            <h1 style="font-size: 38px; font-weight: 800; margin-top: 6px;">
                Order Confirmed Successfully!
            </h1>
            <p style="font-size: 16px; color: #6C747D;">
                Stock has been reserved and deducted from store catalog inventory.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rec_left, col_receipt, rec_right = st.columns([1, 2.5, 1])
    with col_receipt:
        if order:
            st.markdown(
                f"""
                <div class="vyapar-seal-frame">
                    <div style="display: flex; justify-content: space-between; border-bottom: 2px dashed #20252B; padding-bottom: 12px; margin-bottom: 16px;">
                        <div>
                            <div style="font-size: 11px; font-weight: 700; color: #6C747D; text-transform: uppercase;">Order Token</div>
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: #20252B;">{order.order_id}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 11px; font-weight: 700; color: #6C747D; text-transform: uppercase;">Status</div>
                            <div style="font-family: 'Outfit', sans-serif; font-size: 15px; font-weight: 800; color: #00A896;">CONFIRMED & BILLED</div>
                        </div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            # Item rows
            for idx, it in enumerate(order.items):
                if it.is_billable:
                    st.markdown(
                        f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #F3ECE0;">
                            <div>
                                <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #FF6B35;">{idx + 1:02d}.</span>
                                <b style="font-family: 'Outfit', sans-serif; font-size: 15px; margin-left: 6px;">{it.product_name}</b>
                                <div style="font-size: 12px; color: #6C747D; margin-left: 28px;">
                                    {it.requested_quantity:g} {it.requested_unit} &times; Rs. {it.unit_price:g}/{it.inventory_unit}
                                </div>
                            </div>
                            <div style="font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 16px;">
                                Rs. {it.item_total:g}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.markdown(
                f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 14px; border-top: 2px solid #20252B;">
                        <span style="font-family: 'Outfit', sans-serif; font-weight: 800; font-size: 18px;">FINAL AMOUNT BILLED</span>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 26px; color: #00A896;">
                            Rs. {order.total_amount:g}
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Spoken Audio Receipt Playback
        if turn and turn.audio_path and turn.audio_path.is_file():
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="tactile-card-inset">
                    <div style="font-size: 12px; font-weight: 700; color: #00A896; text-transform: uppercase; margin-bottom: 4px;">
                        Spoken Confirmation Receipt (Chitra / Nalini)
                    </div>
                    <div style="font-size: 14px; font-weight: 600; margin-bottom: 8px;">
                        "{turn.response_text}"
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.audio(
                str(turn.audio_path),
                format="audio/wav",
                autoplay=True,
            )

        # Confirmation Action Buttons
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        act_col1, act_col2 = st.columns(2)
        with act_col1:
            if st.button("🛒  START NEW ORDER", use_container_width=True):
                assistant.current_order = None
                st.session_state.last_turn = None
                st.session_state.voice_state = "idle"
                st.session_state.screen = "landing"
                st.rerun()

        with act_col2:
            if st.button("✎  Edit / Re-Open Order", use_container_width=True):
                st.session_state.screen = "interaction"
                st.rerun()


# =============================================================================
# 7. ROUTER: DISPATCH ACTIVE SCREEN
# =============================================================================

if st.session_state.screen == "landing":
    render_landing_screen()
elif st.session_state.screen == "interaction":
    render_interaction_screen()
elif st.session_state.screen == "confirmation":
    render_confirmation_screen()
