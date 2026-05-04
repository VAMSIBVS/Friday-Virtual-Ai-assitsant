# Friday — AI Voice Assistant

**Your personal AI co-pilot. Calm, confident, always in your corner.**

---

## Quick Start

### 1. Get your Groq API key (free)
→ Sign up at [console.groq.com](https://console.groq.com) → API Keys → Create

### 2. Set up environment
```bash
cd Friday
copy .env.example .env
# Open .env and paste your GROQ_API_KEY
```

### 3. Create a virtual environment & install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run Friday

**UI mode — floating orb + voice (recommended):**
```bash
python app.py
```

**UI mode — voice input, text output (no TTS):**
```bash
python app.py --no-tts
```

**Terminal mode — keyboard input, no UI:**
```bash
python app.py --text-only
```

**Legacy terminal entry (backwards compatible):**
```bash
python main.py
python main.py --voice
```

---

## Voice Mode: ffmpeg Required (for TTS playback)

```bash
winget install ffmpeg
```
Or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

---

## Project Structure

```
Friday/
├── app.py               # Main entry point (UI + voice)
├── main.py              # Legacy terminal-only entry
├── config.py            # All configuration
├── .env                 # Your secrets (never commit)
├── requirements.txt     # Dependencies
├── core/
│   ├── brain.py         # LLM (Groq) integration
│   ├── memory.py        # Conversation history (SQLite)
│   └── personality.py   # Friday's identity & system prompt
├── voice/
│   ├── listener.py      # Mic → STT (faster-whisper)
│   └── speaker.py       # TTS → Audio (edge-tts)
├── engine/
│   └── assistant.py     # Conversation orchestrator (QThread)
├── ui/
│   └── orb.py           # Floating orb window + animations
└── data/
    ├── memory/          # friday_memory.db (auto-created)
    └── logs/            # Session logs
```

---

## UI States

| State | Visual |
|---|---|
| **Idle** | Slow breathing cyan glow |
| **Listening** | Active pulse + expanding rings |
| **Thinking** | Rotating shimmer (purple) |
| **Speaking** | Neon ripple radiating outward |

The orb is **draggable** and always stays on top. Starts in the bottom-right corner.

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *required* | Get free at console.groq.com |
| `WHISPER_MODEL` | `base` | `tiny` (fastest) → `large-v3` (best) |
| `TTS_VOICE` | `en-US-GuyNeural` | Any edge-tts voice |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Any Groq-supported model |

---

## Feature Set

| Feature | Status |
|---|---|
| LLM Brain (Groq / Llama 3.3 70B) | ✅ |
| Floating orb UI (dark + neon) | ✅ |
| Animated states (idle/listen/think/speak) | ✅ |
| Voice input (faster-whisper) | ✅ |
| TTS output (edge-tts neural) | ✅ |
| Conversation memory (SQLite) | ✅ |
| Draggable always-on-top window | ✅ |
| Terminal fallback mode | ✅ |

---

## Roadmap

| Version | Features |
|---|---|
| **V1** (current) | Chatbot + voice I/O + memory + UI orb |
| **V2** | Wake word ("Hey Friday") + idea→plan engine |
| **V3** | Voice authentication + device lock |
