# A.T.O.M/tts_atom.py
import threading
import queue
import tempfile
import os
from TTS.api import TTS
from pydub import AudioSegment, effects
from pydub.playback import play
import builtins
import io
import contextlib
import random

# --- Suppress unwanted Coqui TTS prints globally ---
def block_print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    if any(kw in text for kw in ["Processing time", "Real-time factor", "Text splitted"]):
        return  # block only these messages
    old_print(*args, **kwargs)

old_print = builtins.print
builtins.print = block_print

# ----------------------------------------- #
# Load Coqui TTS model (multi-speaker VCTK) #
# ----------------------------------------- #
tts = TTS("tts_models/en/vctk/vits")

# Choose speaker (can be changed at runtime via UI)
TTS_SPEAKER = "p230"

SPEAKER_MAP = {
    "p230": "Calm Male (Default)",
    "p225": "dull Female",
    "p229": "Neutral Male",
    "p240": "Neutral Female",
    "p243": "British Female",
}

AVAILABLE_SPEAKERS = list(SPEAKER_MAP.keys())
# --- Runtime adjustable parameters (controlled from UI) ---
TTS_SPEED = 1.03
TTS_PITCH = 0.98
TTS_VOLUME = 1.0
TTS_PAUSE = 120  # ms silence before speech

# Queue for TTS requests
tts_queue = queue.Queue()

# to- do tune these settings for best results
def voice_model_settings(input_file, output_file):
    sound = AudioSegment.from_file(input_file)

    # --- Pitch ---
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * TTS_PITCH)
    }).set_frame_rate(44100)

    # --- Speed ---
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * TTS_SPEED)
    }).set_frame_rate(44100)

    # --- Volume ---
    sound = sound + (TTS_VOLUME * 5 - 5)  # maps 0–2 → -5dB to +5dB

    sound = effects.normalize(sound)

    sound = sound.compress_dynamic_range(
        threshold=-20.0,
        ratio=2.5,
        attack=5,
        release=50
    )

    sound = effects.high_pass_filter(sound, 80)
    sound = effects.low_pass_filter(sound, 8000)

    sound.export(output_file, format="wav")
    return output_file

# ----------------------------------------- #
# ----------- humanize_output ------------- #
# ----------------------------------------- #

def humanize_text(text):
    """Add subtle pauses and variation to improve natural speech."""
    
    # Natural pauses
    text = text.replace(",", ", ... ")
    text = text.replace("?", "? ... ")
    
    # Optional tiny variation (kept very subtle)
    if len(text) > 1000 and random.random() > 0.2:
        text = text.replace(" you ", " you know ")
    
    return text
# ----------------------------------------- #
# ---------------- Worker ----------------- #
# ----------------------------------------- #

def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:  # Shutdown signal
            break

        try:
            # Generate raw TTS to a temp file with target speaker
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp_path = tmp.name
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):  # hide noisy Coqui logs
                    tts.tts_to_file(
                    text=humanize_text(text),
                    file_path=tmp_path,
                    speaker=TTS_SPEAKER
                )
            # Apply filter
            processed_path = tmp_path.replace(".wav", "_processed.wav")
            voice_model_settings(tmp_path, processed_path)

            # Play processed sound
            final_audio = AudioSegment.silent(duration=120) + AudioSegment.from_file(processed_path)
            play(final_audio)

        except Exception as e:
            old_print(f"[TTS ERROR] {e}")

        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(processed_path):
                os.remove(processed_path)
            tts_queue.task_done()


# Start worker thread
threading.Thread(target=tts_worker, daemon=True).start()


def speak_response(text):
    """Add text to the TTS queue to be spoken sequentially."""
    tts_queue.put(text)
