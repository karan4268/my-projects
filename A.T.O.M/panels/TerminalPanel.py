import re
import json
import requests
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QEvent,  pyqtSignal, QObject, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtGui import QTextCursor
from command import handle_command
from tts_atom import speak_response   # <-- for voice responses


# ------------------------------------------------------------------------- #
# Worker Thread (Streams from Ollama instead of waiting for full response)  #
# ------------------------------------------------------------------------- #
class LLMWorker(QThread):
    chunk_signal = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, query: str, model: str = "phi3"):
        super().__init__()
        self.query = query
        self.model = model

    def run(self):
        url = "http://localhost:11434/api/generate"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "prompt": self.query,
            "stream": True
        }

        try:
            with requests.post(url, json=payload, headers=headers, stream=True) as r:
                for line in r.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                self.chunk_signal.emit(data["response"])
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            self.chunk_signal.emit(f"[Error] Could not reach Ollama: {e}")

        self.done_signal.emit()


class TerminalChat(QWidget):
    message_signal = pyqtSignal(str)

    def __init__(self, model="phi3"):
        super().__init__()
        self.model = model
        self.response_buffer = ""
        self.voice_mode = False

        layout = QVBoxLayout(self)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("ATOM Online: Terminal Ready.")
        layout.addWidget(self.output)

        self.input = QTextEdit()
        self.input.setFixedHeight(50)
        self.input.setPlaceholderText("Type your message here and press Enter...")
        layout.addWidget(self.input)

        self.input.installEventFilter(self)

        # connect signal to GUI-safe appending
        self.message_signal.connect(self._append_message)

    def append_message(self, text: str):
        # can be called from any thread safely
        self.message_signal.emit(text)

    def _append_message(self, text: str):
        self.output.moveCursor(self.output.textCursor().End)
        self.output.insertHtml(text + "<br>\n")
        self.output.moveCursor(self.output.textCursor().End)



    # ---------------- VOICE MODE ---------------- #
    def start_voice_mode(self):
        self.voice_mode = True
        self.append_message("<b>[System]</b> Voice mode <span style='color:lime;'>ENABLED</span>.")

    def stop_voice_mode(self):
        self.voice_mode = False
        self.append_message("<b>[System]</b> Voice mode <span style='color:red;'>DISABLED</span>.")

    # -------------------------------- #
    #     Event filter for Enter key   #
    # -------------------------------- #
    def eventFilter(self, source, event):
        if source == self.input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
        return super().eventFilter(source, event)

    def send_message(self):
        user_input = self.input.toPlainText().strip()
        if not user_input:
            return

        self.append_message(f"<span style='color:rgb(77, 255, 219);font-weight:bold;'>User:</span> {user_input}\n")
        self.input.clear()

        # --- First check hardwired commands ---
        result = handle_command(user_input)
        if result:
            self.append_message(f"<b>A.T.O.M:</b> {result}")
            if self.voice_mode:
                speak_response(result)
            return

        # --- If no command matched, fallback to LLM ---
        self.worker = LLMWorker(user_input, self.model)
        self.worker.chunk_signal.connect(self.handle_chunk)
        self.worker.done_signal.connect(self.handle_done)
        self.worker.start()

    # ------------------------------ #
    # Append messages & format response
    # ------------------------------ #
    def append_message(self, text: str):
        """Always append with a line break"""
        self.output.moveCursor(QTextCursor.End)
        self.output.insertHtml(text + "<br>"+ "\n")
        self.output.ensureCursorVisible()

    def handle_chunk(self, chunk: str):
        # Collect response but don't print it yet
        self.response_buffer += chunk

    def handle_done(self):
        if not self.response_buffer.strip():
            return

        # Now show assistant reply
        self.append_message("🗨️ <b>A.T.O.M says:</b>")
        self.display_response(self.response_buffer.strip())

        # Voice output if enabled
        if self.voice_mode:
            speak_response(self.response_buffer.strip())

        # Reset buffer after displaying
        self.response_buffer = ""

    def display_response(self, response: str, speaker: str = "A.T.O.M"):
        """Display response with formatting and code highlighting"""
        if speaker == "A.T.O.M":
            self.append_text_block("\n")

            response = response.replace("", "").lstrip()

            # Parse code blocks
            code_pattern = re.compile(r"```(\w+)?(.*?)```", re.DOTALL)
            parts = code_pattern.split(response)

            for i, part in enumerate(parts):
                if i % 3 == 1:  # language
                    lang = part.strip() or "text"
                elif i % 3 == 2:  # code block
                    self.append_code_block(part.strip(), lang)
                else:  # normal text
                    if part.strip():
                        self.append_text_block(part.strip())

    # ------------------------------ #
    # Append normal text block
    # ------------------------------ #
    def append_text_block(self, text: str):
        self.output.append(
            f"<p style='color: rgb(77, 255, 219); "
            f"background-color: rgba(0, 0, 0, 0.0);'>{text}</p>"
        )

    # ------------------------------ #
    # Append colored code block
    # ------------------------------ #
    def append_code_block(self, code: str, lang: str):
        colors = {
            "python": "#ffff99",     # light yellow
            "cpp": "#66aaff",        # blue
            "c++": "#66aaff",
            "java": "#ff6666",       # red
            "javascript": "#ff6666",
            "js": "#ff6666",
            "html": "#66ff66",       # green
            "css": "#ff66cc",        # pink
        }
        color = colors.get(lang.lower(), "#d3d3d3")  # default grey

        self.output.append(
            f"<pre style='background-color:#111; color:{color}; "
            f"padding:6px; border-radius:6px; font-family: Consolas, monospace;'>"
            f"{code}</pre>"
        )
