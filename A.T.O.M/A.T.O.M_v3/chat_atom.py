# A.T.O.M/chat_atom.py
from PyQt5.QtCore import QThread, pyqtSignal
from local_engine import get_response_from_atom

class LLMWorker(QThread):
    finished = pyqtSignal(str)  # emits full response once

    def __init__(self, prompt: str, model: str = "phi3", parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.model = model

    def run(self):
        try:
            response = get_response_from_atom(self.prompt)
            self.finished.emit(response)
        except Exception as e:
            self.finished.emit(f"[Error: {e}]")
