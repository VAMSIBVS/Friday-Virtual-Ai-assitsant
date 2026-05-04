"""
Friday Voice — Text-to-Speech using edge-tts.
Converts Friday's text responses to high-quality neural audio.

Playback priority:
  1. ffmpeg → sounddevice  (best quality, needs ffmpeg on PATH)
  2. winsound              (Windows built-in, no extra install)
  3. os.startfile          (last resort — opens system media player)
"""

import asyncio
import edge_tts
import sounddevice as sd
import numpy as np
import tempfile
import os
import subprocess
import sys
import shutil
import config


async def _synthesize_to_file(text: str, voice: str, out_path: str):
    """Run edge-tts and save audio directly to out_path (MP3)."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


async def _synthesize_to_wav(text: str, voice: str, wav_path: str):
    """
    Run edge-tts and save as WAV using the av library (bundled with faster-whisper).
    This avoids the ffmpeg CLI dependency entirely.
    """
    import av
    import io

    # First get MP3 bytes
    communicate = edge_tts.Communicate(text, voice)
    mp3_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_bytes += chunk["data"]

    if not mp3_bytes:
        raise RuntimeError("edge-tts returned no audio data")

    # Decode MP3 → WAV using PyAV (always available via faster-whisper)
    mp3_buf = io.BytesIO(mp3_bytes)
    output_buf = io.BytesIO()

    with av.open(mp3_buf, format="mp3") as in_container:
        in_stream = in_container.streams.audio[0]
        with av.open(output_buf, mode="w", format="wav") as out_container:
            out_stream = out_container.add_stream("pcm_s16le", rate=22050)
            for frame in in_container.decode(in_stream):
                frame.pts = None
                for pkt in out_stream.encode(frame):
                    out_container.mux(pkt)
            # Flush
            for pkt in out_stream.encode(None):
                out_container.mux(pkt)

    with open(wav_path, "wb") as f:
        f.write(output_buf.getvalue())


def _play_with_ffmpeg_sounddevice(mp3_path: str):
    """Decode MP3 with ffmpeg CLI and play via sounddevice."""
    cmd = [
        "ffmpeg", "-loglevel", "quiet",
        "-i", mp3_path,
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(config.SAMPLE_RATE), "-ac", "1",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError("ffmpeg decode failed")
    audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio, samplerate=config.SAMPLE_RATE)
    sd.wait()


def _play_with_pyav_sounddevice(mp3_path: str):
    """Decode MP3 with PyAV and play via sounddevice (no ffmpeg CLI needed)."""
    import av, io
    frames_data = []
    with av.open(mp3_path) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=22050)
        for frame in container.decode(stream):
            resampled = resampler.resample(frame)
            for r in resampled:
                frames_data.append(r.to_ndarray().flatten())

    if not frames_data:
        raise RuntimeError("PyAV decoded no frames")

    audio = np.concatenate(frames_data).astype(np.float32) / 32768.0
    sd.play(audio, samplerate=22050)
    sd.wait()


def _play_with_winsound(wav_path: str):
    """Play a WAV file using Windows built-in winsound (zero dependencies)."""
    import winsound
    winsound.PlaySound(wav_path, winsound.SND_FILENAME)


def _play_with_system(mp3_path: str):
    """Last resort: open with system default media player."""
    if sys.platform == "win32":
        os.startfile(mp3_path)
    elif sys.platform == "darwin":
        subprocess.call(["afplay", mp3_path])
    else:
        subprocess.call(["mpg123", mp3_path])
    import time
    time.sleep(3)


def speak(text: str, voice: str = None):
    """
    Convert text to speech and play it.
    Tries 3 playback methods in order:
      1. PyAV decode → sounddevice  (no ffmpeg CLI needed)
      2. winsound WAV               (Windows built-in)
      3. os.startfile               (system media player)

    Args:
        text:  Text for Friday to speak
        voice: edge-tts voice name (defaults to config.TTS_VOICE)
    """
    if not text or not text.strip():
        return

    voice = voice or config.TTS_VOICE
    clean_text = _strip_markdown(text)
    print(f"[Friday] {text}")

    # Write MP3 to a temp file
    mp3_tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    mp3_tmp.close()
    mp3_path = mp3_tmp.name

    try:
        # Synthesize to MP3 file
        asyncio.run(_synthesize_to_file(clean_text, voice, mp3_path))

        # ── Playback attempt 1: PyAV → sounddevice (no ffmpeg needed) ──────
        try:
            _play_with_pyav_sounddevice(mp3_path)
            return
        except Exception:
            pass

        # ── Playback attempt 2: ffmpeg CLI → sounddevice ───────────────────
        if shutil.which("ffmpeg"):
            try:
                _play_with_ffmpeg_sounddevice(mp3_path)
                return
            except Exception:
                pass

        # ── Playback attempt 3: winsound (convert to WAV first) ────────────
        if sys.platform == "win32":
            wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav_tmp.close()
            wav_path = wav_tmp.name
            try:
                asyncio.run(_synthesize_to_wav(clean_text, voice, wav_path))
                _play_with_winsound(wav_path)
                return
            except Exception:
                pass
            finally:
                if os.path.exists(wav_path):
                    os.unlink(wav_path)

        # ── Playback attempt 4: system media player ─────────────────────────
        _play_with_system(mp3_path)

    except Exception as e:
        print(f"[TTS Error] Could not synthesize audio: {e}")
        print("[Friday] (Response printed above — audio unavailable)")
    finally:
        if os.path.exists(mp3_path):
            os.unlink(mp3_path)


def _strip_markdown(text: str) -> str:
    """Remove markdown syntax for cleaner TTS playback."""
    import re
    text = re.sub(r"```[\s\S]*?```", "...code block omitted...", text)
    text = re.sub(r"`[^`]+`", lambda m: m.group(0).strip("`"), text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
