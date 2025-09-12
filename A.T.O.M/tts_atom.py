# tts_atom.py
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

# --- Suppress unwanted Coqui TTS prints globally ---
def block_print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    if any(kw in text for kw in ["Processing time", "Real-time factor", "Text splitted"]):
        return  # block only these messages
    old_print(*args, **kwargs)

old_print = builtins.print
builtins.print = block_print

# -------------------------------
# Load Coqui TTS model (multi-speaker VCTK)
# -------------------------------
tts = TTS("tts_models/en/vctk/vits")

# Choose speaker
TARGET_SPEAKER = "p246"  # calm female

# Queue for TTS requests
tts_queue = queue.Queue()

# to- do tune these settings for best results
def voice_model_settings(input_file, output_file):
    """Apply filters to make TTS sound closer to Interstellar's TARS."""
    sound = AudioSegment.from_file(input_file)

    # Pitch shift slightly down
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * 0.95)
    }).set_frame_rate(44100)

    # Speed up slightly
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * 1.10)  # speech speed
    }).set_frame_rate(44100)

    # Normalize
    sound = effects.normalize(sound)

    # Band-pass filter
    sound = effects.high_pass_filter(sound, 200)
    sound = effects.low_pass_filter(sound, 4000)

    # Subtle echo
    echo = sound - 15
    sound = sound.overlay(echo, position=60)

    # Export processed voice
    sound.export(output_file, format="wav")
    return output_file


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
                        text=text,
                        file_path=tmp_path,
                        speaker=TARGET_SPEAKER
                    )

            # Apply filter
            processed_path = tmp_path.replace(".wav", "_processed.wav")
            voice_model_settings(tmp_path, processed_path)

            # Play processed sound
            play(AudioSegment.from_file(processed_path))

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
