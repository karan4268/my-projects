import re
import html
import threading
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QTextCursor, QTextOption
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from command import handle_command
from tts_atom import speak_response
from chat_atom import LLMWorker  # your streaming worker (emits new_chunk, finished)


class TerminalChat(QWidget):
    message_signal = pyqtSignal(str)

    def __init__(self, model="phi3"):
        super().__init__()
        self.model = model
        self.voice_mode = False
        self.worker = None

        # streaming state
        self._stream_buffer = ""        # raw text buffer
        self._active_response = False   # whether a response bubble is active
        self._response_cursor = None    # QTextCursor bookmark for replacement

        layout = QVBoxLayout(self)

        # --- Output area ---
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("A.T.O.M is online. Terminal ready.")
        self.output.setFont(QFont("Consolas", 10))
        self.output.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.output.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.output)

        # --- Input area ---
        self.input = QTextEdit()
        self.input.setFixedHeight(50)
        self.input.setPlaceholderText("Type your message here and press Enter...")
        self.input.setFont(QFont("Consolas", 9))
        self.input.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.input.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.input)

        self.input.installEventFilter(self)
        self.message_signal.connect(self._append_message)

    # ---------------- helpers ---------------- #
    def _escape_and_preserve(self, text: str) -> str:
        """Escape HTML but keep newlines visible."""
        return html.escape(text).replace("\n", "<br>")

    @pyqtSlot(str)
    def append_message(self, html_fragment: str):
        self.message_signal.emit(html_fragment)

    @pyqtSlot(str)
    def _append_message(self, html_fragment: str):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)
        self.output.insertHtml(html_fragment + "<br/>\n")
        self.output.moveCursor(QTextCursor.End)
        self.output.ensureCursorVisible()

    # -------------------------------- #
    def eventFilter(self, source, event):
        if source == self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self.send_message()
                return True
        return super().eventFilter(source, event)

    # ------------------------------------------------------------------ #
    def send_message(self):
        user_input = self.input.toPlainText().strip()
        if not user_input:
            return
        self.input.clear()

        # --- user bubble ---
        safe_user = self._escape_and_preserve(user_input)
        user_html = (
            "<div style='text-align:right; margin:6px;'>"
            f"<span style='color:rgb(50, 255, 219); "
            "padding:6px 10px; border-radius:12px; display:inline-block; max-width:70%;'>"
            f"<b>User:</b> {safe_user}</span></div>"
        )
        self.append_message(user_html)

        # --- check command ---
        result = handle_command(user_input)
        if result:
            safe_result = self._escape_and_preserve(result)
            res_html = (
                "<div style='text-align:left; margin:6px;'>"
                f"<span style='background-color:rgba(77, 219, 255, 0.05); color:#66ffcc; "
                "padding:6px 10px; border-radius:12px; display:inline-block; max-width:70%;'>"
                f"<b>A.T.O.M:</b> {safe_result}</span></div>"
            )
            self.append_message(res_html)

            if self.voice_mode:
                threading.Thread(target=lambda: speak_response(result), daemon=True).start()
            return

        # --- fallback to LLM (streaming worker) ---
        self._stream_buffer = ""   # reset buffer
        self._active_response = False
        self._response_cursor = None

        self.worker = LLMWorker(user_input, self.model)   # ✅ works now
        self.worker.new_chunk.connect(self._on_chunk)
        self.worker.finished.connect(self._on_response_done)
        self.worker.start()


    # ---------------- STREAMING: create bubble and update ---------------- # <----FIX ME!!!!!!!!!!
    def start_stream(self):
        """Insert a bubble with a placeholder and bookmark cursor for streaming."""
        self._stream_buffer = ""
        self._active_response = True

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)

        # Insert bubble and keep a bookmark cursor
        self.output.insertHtml(
            "<div style='text-align:left; margin:6px;'>"
            "<span style='color:#00ffc3; padding:6px 10px; border-radius:12px; "
            "display:inline-block; max-width:70%; vertical-align:top;'>"
            "<b>A.T.O.M:</b><br>"
        )

        # Save cursor position where streamed content should be inserted
        self._response_cursor = self.output.textCursor()

        # Close bubble
        self.output.insertHtml("</span></div>")
        self.output.moveCursor(QTextCursor.End)
        self.output.ensureCursorVisible()


    @pyqtSlot(str)
    def _on_chunk(self, chunk: str):
        if not self._active_response:
            self.start_stream()

        # append raw chunk to buffer
        self._stream_buffer += chunk

        # format
        formatted_html = self._format_response(self._stream_buffer)

        # replace from bookmarked cursor position
        tc = self.output.textCursor()
        tc.setPosition(self._response_cursor.position())
        tc.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        tc.removeSelectedText()
        tc.setPosition(self._response_cursor.position())
        tc.insertHtml(formatted_html)

        # move bookmark forward
        self._response_cursor = tc

        self.output.moveCursor(QTextCursor.End)
        self.output.ensureCursorVisible()

        # --- streaming TTS ---
        sentences = re.split(r'([.!?])', self._stream_buffer)
        while len(sentences) > 2:
            sentence = sentences[0].strip() + sentences[1]
            if sentence.strip() and self.voice_mode:
                threading.Thread(target=lambda s=sentence: speak_response(s), daemon=True).start()
            sentences = sentences[2:]


    @pyqtSlot()
    def _on_response_done(self):
        """Called when stream finishes. Flush any leftover buffer to TTS and mark as done."""
        if self._active_response:
            # append completion marker
            cursor = self.output.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml("<br><span style='color:yellow;'>[Response complete]</span>")
            self.output.moveCursor(QTextCursor.End)
            self.output.ensureCursorVisible()
            self._active_response = False

        # speak leftover if any
        plain_text = re.sub(r"<.*?>", "", self._stream_buffer)
        if self.voice_mode and plain_text.strip():
            threading.Thread(target=lambda: speak_response(plain_text.strip()), daemon=True).start()

        self.worker = None

    # ------------------------------------------------------------------ #
    #              Formatting for any code in output                     #
    # ------------------------------------------------------------------ #
    def _format_response(self, raw_text: str, streaming: bool = False) -> str:
        """
        Format text into HTML with code block support.
        If streaming=True, leave unclosed code blocks as plain text until they close.
        """
        tmp = raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        code_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)

        def repl(match):
            lang = (match.group(1) or "").strip()
            code = match.group(2)
            esc_code = html.escape(code)
            colors = {
                "python": "#ffff99",
                "cpp": "#66aaff",
                "c++": "#66aaff",
                "java": "#ff6666",
                "javascript": "#ffae66",
                "js": "#ffae66",
                "html": "#66ff66",
                "css": "#ff66cc",
            }
            color = colors.get(lang.lower(), "#d3d3d3")
            return (
                f"<pre style='background-color:#111; color:{color}; padding:8px; "
                f"border-radius:12px; font-family: Consolas, monospace; max-width:75%; "
                f"white-space:pre-wrap; word-wrap:break-word;'>{esc_code}</pre>"
            )

        # --- full matches (closed blocks) ---
        replaced = re.sub(code_pattern, repl, tmp)

        if streaming:
            # If last ``` is not closed, don’t try to format it yet.
            if tmp.count("```") % 2 == 1:
                # just show last segment as raw text (append-safe)
                last_tick = tmp.rfind("```")
                safe_prefix = re.sub(code_pattern, repl, tmp[:last_tick])
                unfinished = tmp[last_tick:].replace("\n", "<br>")
                return safe_prefix + unfinished

        return replaced.replace("\n", "<br>")
