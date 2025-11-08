import os
import re
import html
import threading
from PyPDF2 import PdfReader
from docx import Document

from PyQt5.QtCore import Qt, QEvent, pyqtSignal, pyqtSlot, QThread, QObject, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QTextCursor, QTextOption, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QFileDialog,
    QGraphicsDropShadowEffect, QHBoxLayout
)

from command import handle_command
from tts_atom import speak_response
from local_engine import get_response_from_atom


# ================================================================= #
# ------------------- SUMMARIZER WORKER --------------------------- #
# ================================================================= #
class SummarizerWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    @pyqtSlot()
    def run(self):
        try:
            ext = os.path.splitext(self.file_path)[1].lower()
            text = ""

            if ext == ".txt":
                with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            elif ext == ".pdf":
                reader = PdfReader(self.file_path)
                for page in reader.pages:
                    text += page.extract_text() or ""
            elif ext == ".docx":
                doc = Document(self.file_path)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            else:
                self.error.emit("⚠️ Unsupported file type.")
                return

            if not text.strip():
                self.error.emit("⚠️ No readable text found in the document.")
                return

            self.progress.emit("🔹 Summarizing document...")
            prompt = f"Summarize this text concisely:\n\n{text}"
            summary = get_response_from_atom(prompt)

            self.finished.emit(summary)

        except Exception as e:
            self.error.emit(f"⚠️ Error summarizing file: {e}")


# ================================================================= #
# ------------------- SUMMARIZER MIXIN ---------------------------- #
# ================================================================= #
class SummarizerMixin:
    def open_file_for_summary(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document to Summarize",
            "",
            "Documents (*.txt *.pdf *.docx)"
        )
        if not file_path:
            return

        self.message_signal.emit(f"📂 Summarizing: {file_path}")

        # Setup thread and worker safely
        thread = QThread(self)  # parent = self
        worker = SummarizerWorker(file_path)
        worker.moveToThread(thread)

        worker.progress.connect(self.message_signal.emit)
        worker.error.connect(self.message_signal.emit)
        worker.finished.connect(self.on_summary_finished)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @pyqtSlot(str)
    def on_summary_finished(self, summary):
        self.message_signal.emit(f"\n🧠 Summary:\n{summary}\n")
        speak_response("Here’s the summary of your document.")


# ================================================================= #
# ------------------- TERMINAL CHAT UI ---------------------------- #
# ================================================================= #
class TerminalChat(QWidget, SummarizerMixin):
    message_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.voice_mode = False

        layout = QVBoxLayout(self)

        # --- Output area ---
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("A.T.O.M is online. Terminal ready.")
        self.output.setFont(QFont("Consolas", 10))
        self.output.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.output.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.output)

        # --- Input + Document button row ---
        input_row = QHBoxLayout()

        self.addDocButton = QPushButton("+", self)
        self.addDocButton.setToolTip("Add document or notes to summarize")
        self.addDocButton.setFixedSize(36, 36)
        self.addDocButton.setStyleSheet("""
            QPushButton {
                color: rgb(77,255,219);
                font-size: 20px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 0.1);
                border: 1px solid rgb(77,255,215);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(77, 255, 219, 0.3);
            }
        """)
        self.addDocButton.clicked.connect(self.open_file_for_summary)

        # Neon glow effect
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(77, 255, 219))
        glow.setOffset(0)
        self.addDocButton.setGraphicsEffect(glow)

        glow_anim = QPropertyAnimation(glow, b"blurRadius")
        glow_anim.setStartValue(15)
        glow_anim.setEndValue(35)
        glow_anim.setDuration(1000)
        glow_anim.setEasingCurve(QEasingCurve.InOutSine)
        glow_anim.setLoopCount(-1)
        glow_anim.start()

        self.input = QTextEdit()
        self.input.setFixedHeight(50)
        self.input.setPlaceholderText("Type your message here and press Enter...")
        self.input.setFont(QFont("Consolas", 9))
        self.input.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.input.setLineWrapMode(QTextEdit.WidgetWidth)

        input_row.addWidget(self.addDocButton)
        input_row.addWidget(self.input)
        layout.addLayout(input_row)

        self.input.installEventFilter(self)

        # Thread-safe GUI updates
        self.message_signal.connect(self.append_message)

    # ---------------- Event Filter ---------------- #
    def eventFilter(self, source, event):
        if source == self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
        return super().eventFilter(source, event)

    # ---------------- Thread-safe appending ---------------- #
    @pyqtSlot(str)
    def append_message(self, html_fragment: str):
        self.output.moveCursor(QTextCursor.End)
        self.output.insertHtml(html_fragment + "<br>\n")
        self.output.moveCursor(QTextCursor.End)

    # ---------------- Send message ---------------- #
    def send_message(self):
        user_input = self.input.toPlainText().strip()
        if not user_input:
            return
        self.input.clear()

        user_html = (
            f"<div style='text-align:right; margin:6px;'>"
            f"<span style='color:rgb(50, 255, 219); padding:6px 10px; "
            f"border-radius:12px; display:inline-block; max-width:70%;'><b>User:</b> "
            f"{html.escape(user_input)}</span></div>"
        )
        self.message_signal.emit(user_html)

        def process():
            # Check for commands first
            result = handle_command(user_input)
            if result:
                self.display_atom_message(result)
                if self.voice_mode:
                    speak_response(result)
                return

            try:
                reply = get_response_from_atom(user_input)
                self.display_atom_message(reply)
                if self.voice_mode:
                    speak_response(reply)
            except Exception as e:
                self.message_signal.emit(f"<div style='color:red;'>⚠️ Error: {e}</div>")

        threading.Thread(target=process, daemon=True).start()

    # ---------------- Display Atom message ---------------- #
    def display_atom_message(self, text):
        formatted = self._format_response(text)
        atom_html = (
            f"<div style='text-align:left; margin:6px;'>"
            f"<span style='color:#00ffc3; padding:6px 10px; border-radius:12px; "
            f"display:inline-block; max-width:65%; vertical-align:top;'>"
            f"<b>A.T.O.M:</b><br>{formatted}</span></div>"
        )
        self.message_signal.emit(atom_html)

    # ---------------- Format response with code highlighting ---------------- #
    def _format_response(self, raw_text: str) -> str:
        # --- Normalize input text ---
        code_pattern = re.compile(r"```([\w#+-]*)?\n(.*?)```", re.DOTALL)
        raw_text = raw_text.strip().replace("\r", "").replace("\\n", "\n")

        # Auto-wrap code if no markdown fences but looks like code
        if not re.search(r"```", raw_text) and re.search(r"\b(def |class |#include|public static void)\b", raw_text):
            raw_text = f"```python\n{raw_text}\n```"

        # --- Syntax color themes ---
        colors = {
            "default": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#00eaff",
                        "func": "#ffb347", "class": "#ff66ff"},
            "python": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#00eaff",
                    "func": "#ffb347", "class": "#ff66ff"},
            "cpp": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#00eaff",
                    "func": "#834d00", "class": "#EF0000"},
            "javascript": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#00eaff",
                        "func": "#ffd190", "class": "#190089"},
            "java": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#00eaff",
                    "func": "#ffb347", "class": "#ff0000"},
            "csharp": {"text": "#e0e0e0", "comment": "#6aff6a", "keyword": "#edce9c",
                    "func": "#ffb347", "class": "#00ffff"},
        }

        # --- Highlight Code ---
        def highlight_code(lang, code):
            lang = (lang or "default").lower()
            c = colors.get(lang, colors["default"])
            code = html.escape(code)

            # Highlight comments and keywords
            code = re.sub(r"#[^\n]*", lambda m: f"<span style='color:{c['comment']}'>{m.group(0)}</span>", code)
            code = re.sub(r"\b(def|class|return|if|else|for|while|import|from|as|try|except|with|pass|new|public|void|int|float|String)\b",
                        lambda m: f"<span style='color:{c['keyword']};font-weight:bold'>{m.group(0)}</span>", code)
            return code

        # --- Split into text + code parts ---
        parts, last_end = [], 0
        for match in code_pattern.finditer(raw_text):
            start, end = match.span()
            lang, code = match.group(1), match.group(2)
            if start > last_end:
                parts.append(("text", raw_text[last_end:start]))
            parts.append(("code", lang, code))
            last_end = end
        if last_end < len(raw_text):
            parts.append(("text", raw_text[last_end:]))

        # --- Assemble HTML ---
        formatted = []
        for part in parts:
            if part[0] == "text":
                formatted.append(html.escape(part[1]).replace("\n", "<br>"))
            elif part[0] == "code":
                formatted_code = highlight_code(part[1], part[2])
                formatted.append(
                    f"<pre style='background:#111;border:1px solid #0ff;"
                    f"border-radius:8px;padding:8px;color:#fff;overflow-x:auto;'>"
                    f"{formatted_code}</pre>"
                )

        return "\n".join(formatted)

