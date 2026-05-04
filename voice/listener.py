"""
Friday Voice — Speech-to-Text using faster-whisper.
Records from microphone until silence is detected, then transcribes.

BUG 1 FIX: Auto-detects the correct input channel count before opening
the stream. Falls back through channel counts [1, 2, device_max] so
PaErrorCode -9998 (Invalid number of channels) never crashes the loop.
"""

import numpy as np
import sounddevice as sd
import tempfile
import os
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
import config

# Load Whisper model once at import time
print("Loading Whisper model... (first run may download the model)")
_model = WhisperModel(
    config.WHISPER_MODEL,
    device=config.WHISPER_DEVICE,
    compute_type=config.WHISPER_COMPUTE_TYPE,
)
print("Whisper ready.")


# ══════════════════════════════════════════════════════════════════════════════
#  BUG 1 FIX — Safe channel detection
# ══════════════════════════════════════════════════════════════════════════════
def _get_safe_channels() -> int:
    """
    Query the default input device and return the safe channel count.
    Prefers mono (1) — falls back to the device's max input channels.
    Never returns 0 or negative.
    """
    try:
        info   = sd.query_devices(kind="input")
        max_ch = int(info.get("max_input_channels", 1))
        # Prefer mono if the device supports it (max_ch >= 1 always means mono is fine)
        return max(1, min(max_ch, 1))   # clamp: we always want mono
    except Exception:
        return 1


def _open_stream_safe(sr: int, chunk_size: int):
    """
    Try to open an InputStream with progressively relaxed channel settings.
    Returns (stream, channels_used) or raises RuntimeError if all attempts fail.
    """
    # Probe actual device capabilities
    try:
        dev_info = sd.query_devices(kind="input")
        dev_max  = int(dev_info.get("max_input_channels", 2))
    except Exception:
        dev_max = 2

    # Try in order: 1 ch (preferred), then device max
    attempts = list(dict.fromkeys([1, dev_max, 2]))   # deduplicated, ordered

    last_err = None
    for ch in attempts:
        if ch < 1:
            continue
        try:
            stream = sd.InputStream(samplerate=sr, channels=ch,
                                    dtype="int16", blocksize=chunk_size)
            stream.start()
            return stream, ch
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        f"Could not open mic with any channel count {attempts}. "
        f"Last error: {last_err}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _rms(audio_chunk: np.ndarray) -> float:
    """Root Mean Square energy of a mono int16 chunk."""
    return float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))


def _to_mono(chunk: np.ndarray, channels: int) -> np.ndarray:
    """Collapse multi-channel audio to mono."""
    if channels == 1 or chunk.ndim == 1:
        return chunk.flatten()
    # Average across channels
    return chunk.mean(axis=1).astype(np.int16)


# ══════════════════════════════════════════════════════════════════════════════
#  RECORDING
# ══════════════════════════════════════════════════════════════════════════════
def record_until_silence() -> np.ndarray:
    """
    Record audio from the default microphone.
    Stops after SILENCE_DURATION seconds of silence or MAX_RECORD_SECONDS.

    Returns:
        numpy int16 mono array at SAMPLE_RATE, or empty array on error.
    """
    sr           = config.SAMPLE_RATE
    chunk_size   = int(sr * 0.1)   # 100 ms chunks
    max_chunks   = int(config.MAX_RECORD_SECONDS / 0.1)
    silence_chks = int(config.SILENCE_DURATION / 0.1)

    print("[Friday] Listening...")

    # BUG 1 FIX: open stream safely
    try:
        stream, channels = _open_stream_safe(sr, chunk_size)
    except RuntimeError as e:
        print(f"[Listener] Cannot open mic: {e}")
        return np.array([], dtype=np.int16)

    frames        = []
    silent_count  = 0
    started       = False

    try:
        for _ in range(max_chunks):
            try:
                chunk, _ = stream.read(chunk_size)
            except Exception as read_err:
                print(f"[Listener] Read error: {read_err}")
                break

            mono = _to_mono(chunk, channels)
            frames.append(mono)

            rms = _rms(mono)
            if rms > config.SILENCE_THRESHOLD * 32768:
                started      = True
                silent_count = 0
            elif started:
                silent_count += 1
                if silent_count >= silence_chks:
                    break   # silence after speech — stop
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

    if not frames:
        return np.array([], dtype=np.int16)

    return np.concatenate(frames, axis=0)


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSCRIPTION
# ══════════════════════════════════════════════════════════════════════════════
def transcribe(audio: np.ndarray) -> str:
    """
    Transcribe a mono int16 numpy array → text via faster-whisper.
    Returns empty string on silence, noise, or error.
    """
    if len(audio) == 0:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        wav.write(tmp_path, config.SAMPLE_RATE, audio)
        segments, _ = _model.transcribe(
            tmp_path,
            beam_size=5,
            language="en",
            vad_filter=True,
        )
        text = " ".join(seg.text for seg in segments).strip()
        return text
    except Exception as e:
        print(f"[Transcribe] Error: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def listen() -> str:
    """
    High-level function: record → transcribe → return text.
    Returns empty string on silence / noise / error (never raises).
    """
    try:
        audio = record_until_silence()
        if len(audio) < config.SAMPLE_RATE * 0.5:
            return ""   # too short — likely noise
        text = transcribe(audio)
        if text:
            print(f"[Boss] {text}")
        return text
    except Exception as e:
        print(f"[Listener] Unhandled error in listen(): {e}")
        return ""
