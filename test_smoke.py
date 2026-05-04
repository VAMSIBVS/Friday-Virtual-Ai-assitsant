"""
Friday V1 — Smoke Test
Validates each component individually without requiring a microphone.
Run: python test_smoke.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
SKIP = "\033[93m⚠ SKIP\033[0m"

results = []

def test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        print(f"  {FAIL}  {name}: {e}")
        results.append((name, False, str(e)))


# ── 1. Config ──────────────────────────────────────────────────────────────────
print("\n[1/5] Config & Environment")
def check_config():
    import config
    assert config.GROQ_API_KEY, "GROQ_API_KEY is not set in .env"
    assert config.WHISPER_MODEL
    assert config.TTS_VOICE
test("GROQ_API_KEY loaded from .env", check_config)

def check_dirs():
    import config
    assert os.path.isdir(config.DATA_DIR)
    assert os.path.isdir(config.MEMORY_DIR)
test("Data directories created", check_dirs)


# ── 2. Personality ────────────────────────────────────────────────────────────
print("\n[2/5] Personality")
def check_personality():
    from core.personality import SYSTEM_PROMPT, VOICE_GREETING, TEXT_GREETING
    assert "Boss" in SYSTEM_PROMPT
    assert "Friday" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) > 200
test("System prompt loaded (contains Boss + Friday)", check_personality)


# ── 3. Memory ─────────────────────────────────────────────────────────────────
print("\n[3/5] Memory (SQLite)")
def check_memory_write_read():
    from core.memory import MemoryStore
    mem = MemoryStore()
    sid = "smoke_test_001"
    mem.save("user", "Hello Friday", sid)
    mem.save("assistant", "Ready, Boss.", sid)
    history = mem.get_recent(n=5, session_id=sid)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "Ready, Boss."
    mem.clear_session(sid)
    assert mem.get_recent(n=5, session_id=sid) == []
test("Write → Read → Clear conversation memory", check_memory_write_read)


# ── 4. Brain (LLM) ────────────────────────────────────────────────────────────
print("\n[4/5] Brain (Groq LLM)")
def check_brain():
    import config
    if not config.GROQ_API_KEY or config.GROQ_API_KEY == "your_groq_api_key_here":
        raise Exception("GROQ_API_KEY not set — open .env and paste your key")
    from core.brain import FridayBrain
    brain = FridayBrain()
    response = brain.think("Say exactly: Ready Boss.", history=[])
    assert isinstance(response, str)
    assert len(response) > 0
    print(f"       LLM response: \"{response[:80]}...\"" if len(response) > 80 else f"       LLM response: \"{response}\"")
test("LLM round-trip (Groq API)", check_brain)


# ── 5. TTS ────────────────────────────────────────────────────────────────────
print("\n[5/5] Text-to-Speech (edge-tts)")
def check_tts_synthesis():
    """Only tests synthesis to file — no audio playback required."""
    import asyncio
    import tempfile
    import edge_tts
    async def synth():
        import config
        communicate = edge_tts.Communicate("Friday online. Ready, Boss.", config.TTS_VOICE)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            path = f.name
        await communicate.save(path)
        size = os.path.getsize(path)
        os.unlink(path)
        assert size > 1000, f"MP3 too small ({size} bytes) — TTS may have failed"
    asyncio.run(synth())
test("edge-tts synthesis (synthesizes without error)", check_tts_synthesis)


# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok, _ in results if ok)
total  = len(results)

print(f"\n{'─'*45}")
print(f"  Results: {passed}/{total} passed")

if passed == total:
    print("\n  \033[92mAll systems go, Boss. Run Friday with:\033[0m")
    print("  \033[96m  python main.py           \033[0m  ← Text mode")
    print("  \033[96m  python main.py --voice   \033[0m  ← Voice mode")
else:
    failed = [(n, e) for n, ok, e in results if not ok]
    print("\n  \033[91mFix these issues before running:\033[0m")
    for name, err in failed:
        print(f"  • {name}: {err}")

print()
