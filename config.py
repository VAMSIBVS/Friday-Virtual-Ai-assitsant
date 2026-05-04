"""
Friday AI Assistant — Configuration
Loads environment variables and defines system-wide constants.
"""

import os
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()

# ── API Keys ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── LLM Settings ─────────────────────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

# ── Speech-to-Text ───────────────────────────────────────────────────────────
WHISPER_MODEL        = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE       = "cpu"     # "cpu" or "cuda"
WHISPER_COMPUTE_TYPE = "int8"    # "int8" for CPU, "float16" for GPU

# ── Text-to-Speech ───────────────────────────────────────────────────────────
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-JennyNeural")

# ── Audio Settings ───────────────────────────────────────────────────────────
SAMPLE_RATE       = 16000   # 16kHz — required by Whisper
CHANNELS          = 1       # Mono
SILENCE_THRESHOLD = 0.01    # RMS threshold for silence detection
SILENCE_DURATION  = 1.5     # Seconds of silence before stopping recording
MAX_RECORD_SECONDS = 30     # Maximum recording duration

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
MEMORY_DIR = os.path.join(DATA_DIR, "memory")
LOG_DIR    = os.path.join(DATA_DIR, "logs")

# Ensure data directories exist
for d in [DATA_DIR, MEMORY_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ── UI Settings ───────────────────────────────────────────────────────────────
# Orb dimensions (pixels)
UI_ORB_WIDTH  = 280
UI_ORB_HEIGHT = 320

# Animation tick rate (milliseconds) — lower = smoother, higher = cheaper
UI_TICK_MS = 16   # ~60 fps

# Orb positioning on screen ("bottom-right" or "center")
UI_START_POSITION = "bottom-right"
