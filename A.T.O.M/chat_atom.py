from PyQt5.QtCore import QThread, pyqtSignal
import ollama

class LLMWorker(QThread):
    new_chunk = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, prompt: str, model: str = "phi3", parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.model = model
        self._running = True

    def run(self):
        try:
            stream = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": self.prompt}],
                stream=True
            )

            for chunk in stream:
                if not self._running:
                    break

                # ✅ Each chunk is already incremental text
                if "message" in chunk and "content" in chunk["message"]:
                    self.new_chunk.emit(chunk["message"]["content"])

        except Exception as e:
            self.new_chunk.emit(f"[Error: {e}]")
        finally:
            self.finished.emit()

    def stop(self):
        self._running = False
