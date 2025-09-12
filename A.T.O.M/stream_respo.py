import queue
import threading
import re

from tts_atom import speak_response
from local_engine import stream_response_from_atom

class StreamingChat:
    def __init__(self, enable_tts=True, ui_callback=None):
        """
        :param enable_tts: Enable/disable voice output
        :param ui_callback: Function to update UI (e.g., TerminalChat.append_text)
        """
        self.enable_tts = enable_tts
        self.ui_callback = ui_callback
        self.tts_queue = queue.Queue()

        # Start background TTS worker
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

    def _tts_worker(self):
        """ Continuously plays sentences from queue """
        while True:
            sentence = self.tts_queue.get()
            if sentence is None:  # shutdown signal
                break
            speak_response(sentence)

    def _send_to_tts(self, sentence):
        if self.enable_tts and sentence.strip():
            self.tts_queue.put(sentence.strip())

    def stream_chat(self, user_input):
        """Stream LLM output and speak sentence-by-sentence."""
        buffer = ""

        for chunk in stream_response_from_atom(user_input):
            buffer += chunk

            # Update UI immediately
            if self.ui_callback:
                self.ui_callback(chunk)

            # Sentence detection
            sentences = re.split(r'([.!?])', buffer)
            while len(sentences) > 2:
                full_sentence = sentences[0] + sentences[1]
                self._send_to_tts(full_sentence)
                sentences = sentences[2:]
            buffer = "".join(sentences)

        # Speak any remaining text
        if buffer.strip():
            self._send_to_tts(buffer.strip())

    def shutdown(self):
        """Stop TTS worker cleanly"""
        self.tts_queue.put(None)
        self.tts_thread.join()
