"""
gnani
~~~~~
Gnani AI integration and Voice Assistant Core package for Gnani Sahaayak.
"""

from .audio_input import (
    AudioInputHandler,
    AudioMetadata,
    AudioValidationError,
    create_dummy_wav,
)
from .assistant import AssistantTurnResponse, VoiceAssistant
from .config import ConfigError, GnaniConfig, load_config, mask_secret
from .extractor import (
    BaseProductExtractor,
    DeterministicProductExtractor,
    ExtractedItem,
    ExtractionResult,
)
from .inventory import InventoryItem, InventoryManager, StockCheckResult
from .languages import (
    DetectionResult,
    LanguageDetector,
    LanguageMode,
    LanguagePreferenceManager,
    PRISMA_LANGUAGE_CODES,
    TIMBRE_VOICE_CONFIG,
)
from .order import Order, OrderItem, OrderManager, OrderStatus
from .prisma import PrismaAPIError, PrismaClient
from .speech import SpeechRecognizer, SpeechResult
from .timbre import TimbreAPIError, TimbreClient
from .voice_response import VoiceResponseResult, VoiceResponseService

__all__ = [
    # Config & Secrets
    "ConfigError",
    "GnaniConfig",
    "load_config",
    "mask_secret",
    # STT & TTS Clients (Prisma & Timbre)
    "PrismaAPIError",
    "PrismaClient",
    "TimbreAPIError",
    "TimbreClient",
    # Audio Ingestion & Validation
    "AudioInputHandler",
    "AudioMetadata",
    "AudioValidationError",
    "create_dummy_wav",
    # Speech Recognition
    "SpeechRecognizer",
    "SpeechResult",
    # Extraction
    "BaseProductExtractor",
    "DeterministicProductExtractor",
    "ExtractedItem",
    "ExtractionResult",
    # Inventory
    "InventoryItem",
    "InventoryManager",
    "StockCheckResult",
    # Order Processing & Management
    "Order",
    "OrderItem",
    "OrderManager",
    "OrderStatus",
    # Voice Response
    "VoiceResponseService",
    "VoiceResponseResult",
    # Orchestrator
    "VoiceAssistant",
    "AssistantTurnResponse",
    # Multilingual & Language Selection
    "LanguageMode",
    "LanguageDetector",
    "LanguagePreferenceManager",
    "DetectionResult",
    "PRISMA_LANGUAGE_CODES",
    "TIMBRE_VOICE_CONFIG",
]
