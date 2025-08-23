# tts_atom.py
import pyttsx3
import threading
import queue

# Initialize TTS engine
engine = pyttsx3.init()

# Voice properties
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)  # 0 = Male, 1 = Female
engine.setProperty('rate', 200)
engine.setProperty('volume', 1.0)

# Queue for TTS requests
tts_queue = queue.Queue()

def tts_worker():
    while True:
        text, suppress_print = tts_queue.get()
        if text is None:  # Shutdown signal
            break
        if not suppress_print:
            engine.say(text)
            engine.runAndWait()
        tts_queue.task_done()

# Start new thread for TTS
threading.Thread(target=tts_worker, daemon=True).start()

def speak_response(text, suppress_print=False):
    """
    Adds text to the TTS queue to be spoken sequentially
    without overlapping or raising 'run loop already started' errors.
    """
    tts_queue.put((text, suppress_print))
