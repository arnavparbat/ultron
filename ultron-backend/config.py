"""
Ultron Assistant Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DB_PATH = DATA_DIR / "ultron_usage.db"

# App Aliases
ALIASES_PATH = DATA_DIR / "aliases.json"
CUSTOM_ALIASES_PATH = DATA_DIR / "custom_aliases.json"

# Audio & Cache Directory
AUDIO_CACHE_DIR = DATA_DIR / "audio_cache"
AUDIO_CACHE_DIR.mkdir(exist_ok=True)

# WebSocket Settings
WS_HOST = "127.0.0.1"
WS_PORT = 8765

# Wake Word Detection
# Porcupine AccessKey - provide your key from https://console.picovoice.ai/
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
# Keyword names or custom .ppn file path
WAKE_WORDS = ["hey ultron", "ultron", "jarvis", "computer"]

# Fallback STT Settings
# "google" (free online via SpeechRecognition) or "whisper" / "vosk"
STT_ENGINE = os.getenv("ULTRON_STT_ENGINE", "google")
STT_LANGUAGE = os.getenv("ULTRON_STT_LANGUAGE", "en-IN")
STT_ENERGY_THRESHOLD = int(os.getenv("ULTRON_STT_ENERGY_THRESHOLD", "400"))
STT_MAX_ENERGY_THRESHOLD = int(os.getenv("ULTRON_STT_MAX_ENERGY_THRESHOLD", "800"))
STT_PAUSE_THRESHOLD = 0.8  # Silence duration to conclude speech

# Text-To-Speech (Edge-TTS)
# Movie Ultron Voice (James Spader - Avengers: Age of Ultron)
TTS_VOICE = os.getenv("ULTRON_TTS_VOICE", "en-US-BrianMultilingualNeural")
TTS_RATE = "-6%"
TTS_PITCH = "-16Hz"
ULTRON_METALLIC_EFFECT = True

# Acknowledgment Phrases
ACK_PHRASES = [
    "Yes boss",
    "On it, boss",
    "Right away, boss",
    "Yes boss, executing now"
]

# Usage Tracker
TRACKER_INTERVAL_SEC = 1.0
NETWORK_TRACKING_ENABLED = True
