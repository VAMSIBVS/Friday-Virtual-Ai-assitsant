"""
Friday AI Assistant — V1 Main Entry Point
==========================================
Supports two modes:
  python main.py          → Text mode (keyboard input)
  python main.py --voice  → Voice mode (microphone input + speech output)

Usage:
  1. Copy .env.example to .env and fill in GROQ_API_KEY
  2. pip install -r requirements.txt
  3. python main.py
"""

import sys
import argparse
import uuid
from datetime import datetime

from core.brain import FridayBrain
from core.memory import MemoryStore
from core.personality import TEXT_GREETING, VOICE_GREETING


# ── Argument Parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Friday AI Assistant")
parser.add_argument(
    "--voice", action="store_true",
    help="Enable voice mode (microphone + TTS)"
)
parser.add_argument(
    "--no-tts", action="store_true",
    help="In voice mode, disable TTS output (text-only responses)"
)
args = parser.parse_args()

VOICE_MODE = args.voice
TTS_ENABLED = VOICE_MODE and not args.no_tts


# ── Lazy-load voice modules (only if needed) ──────────────────────────────────
def load_voice_modules():
    """Import voice modules only when voice mode is active."""
    global listen, speak
    print("Loading voice modules...")
    from voice.listener import listen as _listen
    from voice.speaker import speak as _speak
    listen = _listen
    speak = _speak
    print("Voice modules ready.\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def print_friday(text: str):
    """Print Friday's response with styling."""
    print(f"\n\033[96m[Friday]\033[0m {text}\n")


def print_boss(text: str):
    """Print Boss's input with styling."""
    print(f"\033[93m[Boss]\033[0m {text}")


def get_boss_input_text() -> str:
    """Get text input from keyboard."""
    try:
        user_input = input("\033[93mBoss → \033[0m").strip()
        return user_input
    except (EOFError, KeyboardInterrupt):
        return "quit"


def is_exit_command(text: str) -> bool:
    """Check if Boss wants to shut down."""
    return text.lower().strip() in {"quit", "exit", "bye", "goodbye", "shutdown", "stop"}


def is_mode_switch(text: str) -> bool:
    """Check if Boss wants to switch to voice mode."""
    return text.lower().strip() in {"voice", "voice mode", "switch to voice"}


# ── Core Session Loop ─────────────────────────────────────────────────────────
def run_session(brain: FridayBrain, memory: MemoryStore, session_id: str):
    """
    Main conversation loop.
    Handles text or voice input depending on VOICE_MODE.
    """
    global VOICE_MODE, TTS_ENABLED

    while True:
        # ── Get Input ──────────────────────────────────────────────────────────
        if VOICE_MODE:
            user_input = listen()
            if not user_input:
                continue  # Silence or noise — keep listening
            print_boss(user_input)
        else:
            user_input = get_boss_input_text()
            if not user_input:
                continue

        # ── Check for exit ────────────────────────────────────────────────────
        if is_exit_command(user_input):
            farewell = "Shutting down, Boss. Stay sharp."
            print_friday(farewell)
            if TTS_ENABLED:
                speak(farewell)
            break

        # ── Check for mode switch ─────────────────────────────────────────────
        if not VOICE_MODE and is_mode_switch(user_input):
            VOICE_MODE = True
            TTS_ENABLED = True
            load_voice_modules()
            msg = "Switched to voice mode, Boss. I'm listening."
            print_friday(msg)
            speak(msg)
            continue

        # ── Retrieve memory context ───────────────────────────────────────────
        history = memory.get_recent(n=10, session_id=session_id)

        # ── Think ─────────────────────────────────────────────────────────────
        if VOICE_MODE:
            # Non-streaming for voice (need full text before speaking)
            response = brain.think(user_input, history)
        else:
            # Streaming for text (feels more responsive)
            print(f"\n\033[96m[Friday]\033[0m ", end="", flush=True)
            response_chunks = []
            for chunk in brain.think_stream(user_input, history):
                print(chunk, end="", flush=True)
                response_chunks.append(chunk)
            print("\n")
            response = "".join(response_chunks)

        # ── Output ────────────────────────────────────────────────────────────
        if VOICE_MODE:
            print_friday(response)
            if TTS_ENABLED:
                speak(response)

        # ── Save to memory ────────────────────────────────────────────────────
        memory.save("user", user_input, session_id)
        memory.save("assistant", response, session_id)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Generate unique session ID for this run
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    # Initialise brain and memory
    try:
        brain = FridayBrain()
    except ValueError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

    memory = MemoryStore()

    # Load voice modules if needed
    if VOICE_MODE:
        load_voice_modules()

    # Greeting
    if VOICE_MODE:
        print_friday(VOICE_GREETING)
        if TTS_ENABLED:
            speak(VOICE_GREETING)
    else:
        print(TEXT_GREETING)

    # Run the conversation loop
    try:
        run_session(brain, memory, session_id)
    except KeyboardInterrupt:
        print("\n\n[Friday] Interrupted. Shutting down, Boss.")


if __name__ == "__main__":
    main()
