import requests
from PyQt5.QtCore import QThread, pyqtSignal

class OllamaWorker(QThread):
    new_chunk = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, message, model="phi3"):
        super().__init__()
        self.message = message
        self.model = model

    def run(self):
        url = "http://localhost:11434/api/generate"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "prompt": self.message,
            "stream": True
        }

        try:
            # streaming response
            with requests.post(url, json=payload, headers=headers, stream=True) as r:
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = requests.utils.json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            self.new_chunk.emit(chunk)
                        if data.get("done", False):
                            break
                    except Exception:
                        continue
        except Exception as e:
            self.new_chunk.emit(f"[Error] {e}")

        self.finished.emit()
