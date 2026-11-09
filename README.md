# Gnani Sahaayak (GNANI — VOXORA)
### AI Voice Assistant for Local Indian Kirana Stores

**Gnani Sahaayak** is a multilingual, voice-first AI shopping assistant engineered specifically for local Kirana store owners and customers across India. Built for natural spoken grocery interactions in Indian languages (Telugu, Hindi, English, Hinglish, and Tenglish), it accurately transcribes customer speech, extracts items and quantities, matches them against store inventory, calculates itemized bills, enables conversational corrections, and speaks back clear order confirmations.

---

## 🌟 Key Features

- **Voice-Powered Experience (GNANI — VOXORA)**:
  - **Screen A (Welcome / Voice Threshold)**: Marketplace entry point with language selection and prompt cards.
  - **Screen B (The Living Bazaar)**: Split-screen sound chamber featuring live microphone recording, WAV upload, real-time Prisma STT transcription, and an interactive Grocery Canvas with tactile `+` / `-` quantity steppers and live billing.
  - **Screen C (Confirmation Seal)**: Mercantile receipt slate detailing itemized totals, inventory reservation, and synthesized Timbre v2.5 spoken confirmation receipt playable via `st.audio`.
- **Multilingual Support (5 Input Styles & Language Modes)**:
  - **Telugu Script (`తెలుగు`)**: e.g., *"అన్నా రెండు కిలోల బియ్యం మరియు ఒక లీటర్ నూనె కావాలి"*
  - **Tenglish (Romanized Telugu)**: e.g., *"Anna, two kilos biyyam aur one litre oil kavali"*
  - **Hindi Script (`हिन्दी`)**: e.g., *"भैया, एक किलो चावल और आधा किलो चीनी देना"*
  - **Hinglish (Romanized Hindi)**: e.g., *"Bhai, ek kilo rice aur half kilo sugar dena"*
  - **English**: e.g., *"I need two kilos of rice and one litre of cooking oil"*
  - **Automatic Language Detection**: Detects language mode automatically from text or speech, persists preference, and responds in the customer's preferred dialect.
- **Official Gnani Vachana AI Speech Engines**:
  - **Gnani Prisma v2.5 STT**: Speech-to-text recognition with request lock concurrency protection and hash-based audio deduplication to eliminate redundant API calls during Streamlit reruns.
  - **Gnani Timbre v2.5 TTS**: Speech synthesis with verified voices (`Nalini` for Hindi/English, `Chitra` for Telugu) and safe fallback handling ensuring audio errors never compromise the customer's cart or order state.
- **Kirana Commerce Engine**:
  - Deterministic regex & multilingual numeral parsing (`ek`, `do`, `rendu`, `half`, `aadha`, `aradha`).
  - Standardized unit normalization (kg, g, litre, ml, packet, piece).
  - Vernacular alias resolution (`chawal` / `biyyam` → Basmati Rice, `cheeni` / `panchadara` → Refined Sugar).
  - Natural conversational corrections (*"Change rice to 3 kilos"*, *"Remove oil"*).
  - Atomic inventory deduction upon order confirmation.

---

## 🏗️ Architecture Pipeline

```
[Customer Spoken WAV / Microphone Audio]
                 │
                 ▼
┌─────────────────────────────────┐
│     gnani.audio_input           │  Validates WAV RIFF format, 16-bit PCM,
│     (AudioInputHandler)         │  sample rates, and duration (<= 60s).
└────────────────┬────────────────┘
                 │ Validated Audio Bytes
                 ▼
┌─────────────────────────────────┐
│     gnani.prisma / gnani.speech │  Transcribes speech with concurrency lock &
│     (SpeechRecognizer)          │  hash-based deduplication (POST api.vachana.ai/stt/v3).
└────────────────┬────────────────┘
                 │ Transcript (e.g. "Anna, two kilos biyyam aur one litre oil kavali")
                 ▼
┌─────────────────────────────────┐
│     gnani.languages             │  Detects Telugu, Tenglish, Hindi, Hinglish, English;
│     (LanguagePreferenceManager) │  normalizes script and selects appropriate TTS voice.
└────────────────┬────────────────┘
                 │ Normalized Text & Active Language
                 ▼
┌─────────────────────────────────┐
│     gnani.extractor             │  Extracts products, quantities, and units;
│     (BaseProductExtractor)      │  resolves colloquial numerals & vernacular variants.
└────────────────┬────────────────┘
                 │ Structured Item List (Product, Quantity, Unit)
                 ▼
┌─────────────────────────────────┐
│     gnani.inventory             │  Matches local catalog with alias lookup
│     (InventoryManager)          │  (e.g. "biyyam" -> Basmati Rice), unit conversion, stock check.
└────────────────┬────────────────┘
                 │ Line-Item Pricing & Stock Status
                 ▼
┌─────────────────────────────────┐
│     gnani.order                 │  Computes subtotal, tax, grand total; handles
│     (OrderManager)              │  conversational modifications and atomic stock deduction.
└────────────────┬────────────────┘
                 │ Spoken Summary Text
                 ▼
┌─────────────────────────────────┐
│     gnani.timbre / gnani.voice  │  Synthesizes WAV speech via Gnani Timbre v2.5
│     (VoiceResponseService)      │  (Nalini for Hindi/English, Chitra for Telugu).
└────────────────┬────────────────┘
                 │ Spoken Audio Response (.wav) + Visual State
                 ▼
┌─────────────────────────────────┐
│     GNANI — VOXORA UI (app.py)  │  Interactive Streamlit application with audio
│     (Streamlit Interface)       │  playback, tactile steppers, and confirmation seal.
└─────────────────────────────────┘
```

---

## 📁 Directory Structure

```
gnani sahayak/
├── .env.example              # Environment configuration template (secrets excluded)
├── .gitignore                # Excludes .env, caches, virtualenvs, audio files
├── requirements.txt          # Python runtime dependencies
├── pytest.ini                # Pytest configuration
├── README.md                 # Project documentation
├── app.py                    # Streamlit VOXORA web application
│
├── data/
│   └── sample_inventory.json # Local Kirana store inventory catalog
│
├── gnani/                    # Core Voice Assistant Backend Package
│   ├── __init__.py           # Package exports
│   ├── config.py             # Configuration loader with secret masking
│   ├── languages.py          # Multilingual modes, auto-detection & voice mappings
│   ├── prisma.py             # Gnani Prisma v2.5 STT client wrapper
│   ├── timbre.py             # Gnani Timbre v2.5 TTS client wrapper
│   ├── audio_input.py        # WAV audio validation and inspection
│   ├── speech.py             # STT recognition service and error handler
│   ├── extractor.py          # Multilingual product & quantity extraction engine
│   ├── inventory.py          # Local store inventory catalog & pricing
│   ├── order.py              # Order calculation, confirmation & correction manager
│   ├── voice_response.py     # Voice summary generation & TTS audio output
│   └── assistant.py          # End-to-end voice assistant orchestrator
│
├── output_audio/             # Local storage for synthesized response WAV files (gitignored)
│
├── scripts/
│   ├── smoke_test.py         # Mock and live smoke test for Prisma & Timbre
│   └── run_assistant_demo.py # Interactive CLI demo walkthrough
│
└── tests/
    ├── test_config.py             # Config loading & secret masking unit tests
    ├── test_clients_mock.py       # Prisma & Timbre client mock tests
    ├── test_audio_input.py        # Audio validation & constraint tests
    ├── test_extractor.py          # Product & quantity extraction tests
    ├── test_inventory.py          # Inventory lookup & unit conversion tests
    ├── test_languages.py          # Language detection & voice selection tests
    ├── test_multilingual.py       # 5-language input styles & persistence tests
    ├── test_order.py              # Order calculation & correction tests
    ├── test_assistant_pipeline.py # Voice pipeline integration tests
    ├── test_smoke_test.py         # Smoke test validation tests
    └── test_ui.py                 # Streamlit VOXORA UI workflow integration tests
```

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Windows / macOS / Linux

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials (Optional for Live Mode)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your Gnani Cloud API credentials:
```env
GNANI_API_KEY=your_actual_gnani_api_key_here
GNANI_API_BASE_URL=https://api.vachana.ai
GNANI_AUTH_HEADER=X-API-Key-ID
GNANI_PRISMA_LANGUAGE=hi-IN
GNANI_TIMBRE_MODEL=timbre-v2.5
GNANI_TIMBRE_VOICE=Nalini
```

> **Security Note:** Real API keys are never printed, logged, or committed to Git. String representations (`__repr__`) automatically mask secrets (e.g., `vach...b9be`), and `.env` is excluded in `.gitignore`.

---

## 💻 Running the Application

### 1. Launch the Streamlit Web Application
Start the GNANI — VOXORA web interface:
```bash
python -m streamlit run app.py
```
Or specify the port:
```bash
python -m streamlit run app.py --server.port 8501
```
Open your browser at `http://localhost:8501`.

### 2. Run the Interactive Offline CLI Demo
Run a complete simulated customer shopping session without network calls:
```bash
python scripts/run_assistant_demo.py --mock
```

**Walkthrough Sequence:**
1. **Turn 1 (Spoken Order)**: Customer submits audio clip (*"Two kilos of rice and one litre of oil"*). Items are extracted, priced (Rs. 260.00), and a voice summary is synthesized.
2. **Turn 2 (Correction)**: Customer modifies order (*"Change rice to 3 kilos"*). Quantity updates, total recalculates (Rs. 320.00), and updated audio is generated.
3. **Turn 3 (Confirmation)**: Customer confirms (*"confirm"*). Stock is deducted from inventory, order status transitions to `CONFIRMED`, and a spoken receipt is produced.

### 3. Run the Offline Smoke Test
Verify client integrity and mock responses:
```bash
python scripts/smoke_test.py --mock
```

### 4. Run Live API Tests (Optional)
Test live connectivity with the Gnani Cloud Gateway:
```bash
python scripts/smoke_test.py --live
```

---

## 🧪 Automated Test Suite

The repository includes a comprehensive test suite of **127 automated tests** covering unit components, multilingual extraction, audio validation, rate-limiting recovery, and UI workflows.

To run the complete test suite:
```bash
python -m pytest tests/ -v
```

### Test Coverage Highlights:
- **`tests/test_ui.py` (26 tests)**: Screen state transitions (A → B → C), tactile quantity steppers, item deletion, live audio recording, audio deduplication, Prisma/Timbre concurrency locks, and 429 rate-limit recovery without cart loss.
- **`tests/test_multilingual.py` (8 tests)**: Five input styles (Telugu script, Tenglish, Hindi script, Hinglish, English), script normalization, automatic language detection, and language preference persistence.
- **`tests/test_assistant_pipeline.py` (9 tests)**: Complete voice pipeline flow, conversational confirmations and rejections, and graceful fallback when TTS fails.
- **`tests/test_clients_mock.py` (30 tests)**: Prisma STT and Timbre TTS mock responses, timeouts, concurrency locks, and error propagation.
- **`tests/test_extractor.py` (12 tests)**: Multilingual numeral canonicalization, unit parsing (kg, g, l, ml, packets), and missing entity detection.
- **`tests/test_inventory.py` (6 tests)**: Catalog alias resolution, automatic unit conversion, stock deduction, and atomic rollbacks.
- **`tests/test_order.py` (6 tests)**: Subtotal, GST, grand total calculation, item corrections, and lifecycle state management.
- **`tests/test_audio_input.py` (8 tests)**: WAV RIFF headers, sampling rates, duration boundaries, and invalid format handling.
- **`tests/test_languages.py` (10 tests)**: Dialect detection, voice configuration mapping (`Nalini`, `Chitra`), and preference persistence.
- **`tests/test_config.py` (4 tests)**: Environment variable loading, fallback defaults, and secret masking.
- **`tests/test_smoke_test.py` (8 tests)**: Smoke test validation and mock client verification.

---

## 📦 Sample Store Catalog

The sample Kirana catalog (`data/sample_inventory.json`) includes staple Indian grocery items with vernacular aliases:

| ID | Product Name | Category | Price | Unit | Stock | Vernacular Aliases |
|---|---|---|---|---|---|---|
| `PROD-001` | Basmati Rice | Grains & Cereals | Rs. 60.0 | kg | 50.0 | `rice`, `chawal`, `biyyam`, `basmati` |
| `PROD-002` | Sunflower Cooking Oil | Edible Oils | Rs. 140.0 | litre | 30.0 | `oil`, `tel`, `noone`, `cooking oil` |
| `PROD-003` | Refined Sugar | Sweeteners | Rs. 42.0 | kg | 40.0 | `sugar`, `cheeni`, `panchadara`, `shakkar` |
| `PROD-004` | Whole Wheat Atta | Flours | Rs. 40.0 | kg | 35.0 | `atta`, `wheat flour`, `godhuma pindi`, `gehu` |
| `PROD-005` | Toor Dal | Pulses & Lentils | Rs. 150.0 | kg | 20.0 | `dal`, `toor dal`, `kandi pappu`, `arhar dal` |
| `PROD-006` | Fresh Cow Milk | Dairy | Rs. 60.0 | litre | 25.0 | `milk`, `doodh`, `paalu`, `dudh` |
| `PROD-007` | Parle-G Biscuits | Snacks & Bakery | Rs. 10.0 | packet | 50.0 | `biscuit`, `biscuits`, `parle-g` |
| `PROD-008` | Premium Tea Leaves | Beverages | Rs. 280.0 | kg | 15.0 | `tea`, `chai`, `tea powder`, `chai patti` |
| `PROD-009` | Iodized Salt | Spices & Condiments | Rs. 22.0 | kg | 45.0 | `salt`, `namak`, `uppu` |
| `PROD-010` | Turmeric Powder | Spices & Condiments | Rs. 180.0 | kg | 10.0 | `turmeric`, `haldi`, `pasupu` |
