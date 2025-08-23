
import threading
import time

try:
    import speech_recognition as sr
except Exception:
    sr = None  # allow import even in environments without speech_recognition

_recognizer = sr.Recognizer() if sr else None
_listening = False
_listen_thread = None
_callback = None  # callback(text: str | None)


def listen_to_user(timeout=5, phrase_time_limit=10):
    """
    One-shot blocking recognition. Returns recognized text or None on failure.
    Keeps old signature for compatibility with main_atom.
    """
    if sr is None:
        return None

    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = _recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            try:
                text = _recognizer.recognize_google(audio)
                return text
            except sr.UnknownValueError:
                return None
            except Exception:
                return None
    except Exception:
        return None


def _listen_loop(timeout=5, phrase_time_limit=10):
    global _listening, _callback
    if sr is None:
        # Nothing to do; call callback once with None so UI can update
        if _callback:
            try:
                _callback(None)
            except Exception:
                pass
        return

    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)
            while _listening:
                try:
                    audio = _recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                    if not _listening:
                        break
                    try:
                        text = _recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        text = None
                    except Exception:
                        text = None

                    # call callback (may be in worker thread)
                    if _callback:
                        try:
                            _callback(text)
                        except Exception:
                            pass

                except sr.WaitTimeoutError:
                    # timeout listening — notify callback with None so UI may show "No speech detected"
                    if _callback:
                        try:
                            _callback(None)
                        except Exception:
                            pass
                    continue
                except Exception:
                    # unexpected errors — notify callback and keep looping
                    if _callback:
                        try:
                            _callback(None)
                        except Exception:
                            pass
                    time.sleep(0.5)
    except Exception:
        # microphone open failed
        if _callback:
            try:
                _callback(None)
            except Exception:
                pass


def start_listening(callback, timeout=5, phrase_time_limit=10):
    """
    Start continuous listening in a background thread.
    `callback` will be called with recognized text (str) or None.
    """
    global _listening, _listen_thread, _callback
    if _listening:
        return  # already listening
    _callback = callback
    _listening = True
    _listen_thread = threading.Thread(target=_listen_loop, args=(timeout, phrase_time_limit), daemon=True)
    _listen_thread.start()


def stop_listening():
    """
    Stop the background listening loop.
    """
    global _listening, _listen_thread, _callback
    _listening = False
    _callback = None
    _listen_thread = None
