"""
Friday Engine — Assistant Orchestrator
========================================
Runs the voice/text conversation loop in a background QThread.
Emits Qt signals for UI state changes.

IMPORTANT: The core logic pipeline is identical to main.py:
  listen() → brain.think() → speak()
Nothing here changes voice detection, timing, or response flow.
"""

import time
import uuid
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from core.brain import FridayBrain
from core.memory import MemoryStore
from core.personality import VOICE_GREETING


def _is_exit_command(text: str) -> bool:
    return text.lower().strip() in {"quit", "exit", "bye", "goodbye", "shutdown", "stop"}


class AssistantEngine(QThread):
    """
    Background thread that drives the Friday conversation loop.
    Emits signals to the UI for visual state changes.
    """

    # Qt signals (emitted from the worker thread, connected to UI slots)
    state_changed  = pyqtSignal(str)   # "idle" | "listening" | "thinking" | "speaking"
    transcript     = pyqtSignal(str, str)  # (role, text) — for optional console printing
    error_occurred = pyqtSignal(str)

    def __init__(self, voice_mode: bool = True, tts_enabled: bool = True, parent=None):
        super().__init__(parent)
        self.voice_mode  = voice_mode
        self.tts_enabled = tts_enabled
        self._running    = False

        # Lazy-loaded voice modules
        self._listen = None
        self._speak  = None

    def _load_voice_modules(self):
        from voice.listener import listen as _listen
        from voice.speaker import speak as _speak
        self._listen = _listen
        self._speak  = _speak

    def speak(self, text: str):
        """Speak text and emit appropriate state signals."""
        self.state_changed.emit("speaking")
        if self.tts_enabled and self._speak:
            self._speak(text)
        time.sleep(0.1)
        self.state_changed.emit("idle")

    def run(self):
        """Main conversation loop — runs on the background thread."""
        self._running = True

        # ── Init core modules ──────────────────────────────────────────────
        try:
            brain = FridayBrain()
        except ValueError as e:
            self.error_occurred.emit(str(e))
            return

        memory   = MemoryStore()
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

        # ── Load voice modules if needed ───────────────────────────────────
        if self.voice_mode:
            try:
                self._load_voice_modules()
            except Exception as e:
                self.error_occurred.emit(f"Voice module load failed: {e}")
                return

        # ── Startup greeting (once) ────────────────────────────────────────
        self.transcript.emit("friday", VOICE_GREETING)
        self.speak(VOICE_GREETING)

        # ── Main loop ─────────────────────────────────────────────────────
        while self._running:

            # ── Get input ─────────────────────────────────────────────────
            if self.voice_mode:
                self.state_changed.emit("listening")
                user_input = self._listen()
                if not user_input:
                    self.state_changed.emit("idle")
                    continue
                self.transcript.emit("boss", user_input)
            else:
                # Text mode: not used in UI mode normally,
                # but kept for completeness
                self.state_changed.emit("idle")
                time.sleep(0.2)
                continue

            # ── Exit command ──────────────────────────────────────────────
            if _is_exit_command(user_input):
                farewell = "Shutting down. Stay sharp, Boss."
                self.transcript.emit("friday", farewell)
                self.speak(farewell)
                self._running = False
                break

            # ── Think ─────────────────────────────────────────────────────
            self.state_changed.emit("thinking")
            history = memory.get_recent(n=10, session_id=session_id)
            response = brain.think(user_input, history)

            # ── Save to memory ─────────────────────────────────────────────
            memory.save("user",      user_input, session_id)
            memory.save("assistant", response,   session_id)

            self.transcript.emit("friday", response)

            # ── Speak ─────────────────────────────────────────────────────
            self.speak(response)

        self.state_changed.emit("idle")

    def stop(self):
        """Signal the loop to stop gracefully."""
        self._running = False
