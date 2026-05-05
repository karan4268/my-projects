# A.T.O.M/panels/TerminalPanel.py
import base64
import os
import re
import html
import threading
from PyPDF2 import PdfReader
from docx   import Document

from PyQt5.QtCore    import Qt, QEvent, pyqtSignal, pyqtSlot, QThread, QObject, QPropertyAnimation, QEasingCurve, QUrl
from PyQt5.QtGui     import QFont, QTextCursor, QTextOption, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextBrowser, QPushButton, QFileDialog,
    QGraphicsDropShadowEffect, QHBoxLayout, QTextEdit, QApplication
)

from command      import handle_command
from tts_atom     import speak_response
from local_engine import get_response_from_atom
from theme        import theme_manager


# ================================================================== #
#  Theme helper — returns current RGB tuple                           #
# ================================================================== #

def _tc() -> tuple[int, int, int]:
    """Return (r, g, b) of the current theme colour."""
    c = QColor(theme_manager.color)
    return c.red(), c.green(), c.blue()

def _theme_hex() -> str:
    return theme_manager.color


# ================================================================== #
#  /help text (theme-aware at render time)                            #
# ================================================================== #

def _help_logo() -> str:
    r, g, b = _tc()
    return (
f"<div style='border:1px solid rgb({r},{g},{b}); border-radius:6px; "
f"padding:10px 16px; margin-bottom:10px; "
f"background:rgba(0,20,20,0.02); text-align:center; color:rgb({r},{g},{b});'>"
f"<pre style='font-family:Consolas,monospace; font-size:9pt; "
f"color:rgb({r},{g},{b}); margin:0; line-height:1.35;'>"
"                                                        \n"
"+-----------------------------------------------------+\n" 
"|          _____    _______   _____   ___  ___        |\n"
"|         /  _  \  |__   __| /  _  \ |   \/   |       |\n"
"|        /  /_\  \    | |    | | | | |  \  /  |       |\n"
"|        |  ___   |   | |    | | | | |  |\/|  |       |\n"
"|        |  |  |  |   | |    | |_| | |  |  |  |       |\n"
"|        |__|  |__|   |_|    \_____/ |__|  |__|       |\n"
"+-----------------------------------------------------+\n"
f"</pre>"
f"<div style='color:rgb({r},{g},{b}); font-family:Orbitron,monospace; font-size:8pt; "
f"letter-spacing:0.12em; margin-top:6px;'>"
f"&gt;&gt;&gt;  ADVANCED TASK ORIENTED MODEL   &lt;&lt;&lt;"
f"</div></div>"

    )


def _help_card(title: str, use: str, examples: list) -> str:
    r, g, b = _tc()
    ex_html = "".join(
        f"<div style='margin:2px 0;'>"
        f"<span style='color:rgba({r},{g},{b},0.45); font-size:8pt;'>&#9656;</span> "
        f"<code style='background:rgba(0,0,0,0.35); border:1px solid rgba({r},{g},{b},0.2); "
        f"border-radius:3px; padding:1px 5px; color:rgba({r},{g},{b},0.85); font-size:8.5pt;'>"
        f"{ex}</code></div>"
        for ex in examples
    )
    return (
        f"<div style='margin:5px 0; padding:7px 10px; "
        f"background:rgba(0,30,30,0.5); "
        f"border:1px solid rgba({r},{g},{b},0.18); "
        f"border-left:2px solid rgba({r},{g},{b},0.6); "
        f"border-radius:0 6px 6px 0;'>"
        f"<div style='color:rgb({r},{g},{b}); font-family:Orbitron,monospace; "
        f"font-size:8.5pt; font-weight:600; margin-bottom:3px;'>[ {title} ]</div>"
        f"<div style='color:rgba(200,220,220,0.75); font-size:8.5pt; margin-bottom:4px;'>{use}</div>"
        f"{ex_html}</div>"
    )


def _help_section(label: str) -> str:
    r, g, b = _tc()
    return (
        f"<div style='margin:10px 0 5px 0; "
        f"border-bottom:1px solid rgba({r},{g},{b},0.25); padding-bottom:3px;'>"
        f"<span style='color:rgb({r},{g},{b}); font-family:Orbitron,monospace; "
        f"font-size:8pt; font-weight:600; letter-spacing:0.1em;'>{label}</span></div>"
    )


def _qcmd(trigger: str, desc: str) -> str:
    r, g, b = _tc()
    return (
        f"<div style='margin:2px 0; font-size:8.5pt;'>"
        f"<code style='background:rgba(0,0,0,0.35); border:1px solid rgba({r},{g},{b},0.2); "
        f"border-radius:3px; padding:1px 5px; color:rgb({r},{g},{b});'>{trigger}</code>"
        f"<span style='color:#c9d1d9;'>&nbsp;&#8594;&nbsp;{desc}</span></div>"
    )


def _build_help_text() -> str:
    r, g, b = _tc()
    return (
        "<div style='font-family:Consolas,monospace; padding:6px 4px;'>"
        + _help_logo()
        + _help_section("SYSTEM TOOLS &amp; CAPABILITIES")
        + _help_card("WEB SEARCH", "Search the internet for real-time or factual information.",
            ["search google for latest stock price of NVIDIA", "who is the current prime minister of Japan?"])
        + _help_card("FILE OPERATIONS", "Read, write, append, or list files on your local disk.",
            ["read file C:/Users/Docs/notes.txt", "list files in D:/Projects", "write file log.txt with content 'Task Completed'"])
        + _help_card("SYSTEM COMMANDS", "Control hardware, volume, and launch applications.",
            ["open notepad", "set volume to 50", "take a screenshot"])
        + _help_card("CALCULATE", "Perform maths or unit conversions.",
            ["calculate (45 * 2) / 10", "convert 100 kilograms to pounds"])
        + _help_card("MEMORY", "Store or recall facts between sessions.",
            ["remember my keys are in the top drawer", "what did I tell you about my keys?"])
        + _help_card("SUMMARIZE", "Extract key points from PDF, DOCX, or TXT files.",
            ["summarize file C:/Downloads/research_paper.pdf"])
        + _help_card("SHELL", "Execute safe, read-only terminal commands.",
            ["run command ipconfig", "ping google.com"])
        + _help_section("QUICK COMMANDS")
        + "<div style='margin:4px 0 8px 4px;'>"
        + _qcmd("time &nbsp;/&nbsp; date", "Shows current system time and date.")
        + _qcmd("battery status",          "Shows current battery percentage.")
        + _qcmd("sys info",                "Real-time CPU and RAM usage.")
        + _qcmd("who are you?",            "Details about A.T.O.M's origin.")
        + _qcmd("/help",                   "Show this panel.")
        + _qcmd("/clear",                  "Clear the terminal output.")
        + _qcmd("/model",                  "Show the active model name.")
        + _qcmd("quit &nbsp;/&nbsp; exit", "Terminate the session.")
        + "</div>"
        + f"<div style='margin-top:8px; padding:6px 10px; "
        + f"border:1px solid rgba({r},{g},{b},0.15); border-radius:6px; "
        + f"background:rgba(0,0,0,0.3); color:rgba(200,220,220,0.6); font-size:8.5pt;'>"
        + "Type your request in natural language. A.T.O.M will automatically determine the best tool to use."
        + "</div></div>"
    )


# ================================================================== #
#  Syntax highlighting — themes follow language, not UI theme         #
# ================================================================== #

_THEMES: dict = {
    "default":    {"bg":"#18181a3c","border":"#30a0c0","text":"#c9d1d9","comment":"#6aff6a","keyword":"#00eaff","func":"#d2a679","string":"#a8d8a8","number":"#f0c080","class_":"#ff88ff"},

    "python":     {"bg":"#18181a3c","border":"#3d9be9","text":"#c9d1d9","comment":"#6aff6a","keyword":"#00eaff","func":"#d2a679","string":"#a8d8a8","number":"#f0c080","class_":"#ff88ff"},

    "javascript": {"bg":"#18181a3c","border":"#f0db4f","text":"#cdd9e5","comment":"#6aff6a","keyword":"#f0db4f","func":"#ffd190","string":"#98d68d","number":"#f0c080","class_":"#ff88ff"},

    "typescript": {"bg":"#18181a3c","border":"#3178c6","text":"#cdd9e5","comment":"#6aff6a","keyword":"#3a9dff","func":"#ffd190","string":"#98d68d","number":"#f0c080","class_":"#ff88ff"},

    "cpp":        {"bg":"#18181a3c","border":"#9b59b6","text":"#e0e0e0","comment":"#7ec8e3","keyword":"#c792ea","func":"#82aaff","string":"#c3e88d","number":"#f78c6c","class_":"#ffcb6b"},

    "c":          {"bg":"#18181a3c","border":"#9b59b6","text":"#e0e0e0","comment":"#7ec8e3","keyword":"#c792ea","func":"#82aaff","string":"#c3e88d","number":"#f78c6c","class_":"#ffcb6b"},

    "java":       {"bg":"#18181a3c","border":"#f89820","text":"#e0e0e0","comment":"#6aff6a","keyword":"#cc7832","func":"#ffc66d","string":"#6a8759","number":"#6897bb","class_":"#ffc66d"},

    "csharp":     {"bg":"#18181a3c","border":"#9b4f96","text":"#e0e0e0","comment":"#6aff6a","keyword":"#569cd6","func":"#dcdcaa","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},

    "rust":       {"bg":"#18181a3c","border":"#ce422b","text":"#e0e0e0","comment":"#6e8c6e","keyword":"#ce422b","func":"#dca77e","string":"#a3be8c","number":"#b48ead","class_":"#81a1c1"},
    
    "go":         {"bg":"#18181a3c","border":"#00acd7","text":"#e0e0e0","comment":"#6aff6a","keyword":"#00acd7","func":"#4fc1e9","string":"#a8d8a8","number":"#f0c080","class_":"#ff88ff"},

    "html":       {"bg":"#18181a3c","border":"#e44d26","text":"#c9d1d9","comment":"#6a9a6a","keyword":"#e44d26","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},

    "css":        {"bg":"#18181a3c","border":"#2965f1","text":"#c9d1d9","comment":"#6a9a6a","keyword":"#2965f1","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},

    "sql":        {"bg":"#18181a3c","border":"#e8a04d","text":"#c9d1d9","comment":"#6aff6a","keyword":"#e8a04d","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},
    "bash":       {"bg":"#18181a3c","border":"#4caf50","text":"#c9d1d9","comment":"#6aff6a","keyword":"#4caf50","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},

    "shell":      {"bg":"#18181a3c","border":"#4caf50","text":"#c9d1d9","comment":"#6aff6a","keyword":"#4caf50","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},

    "json":       {"bg":"#18181a3c","border":"#00b4d8","text":"#c9d1d9","comment":"#6aff6a","keyword":"#00b4d8","func":"#9cdcfe","string":"#ce9178","number":"#b5cea8","class_":"#4ec9b0"},
}

_KW: dict = {
    "python":     ["def","class","return","if","else","elif","for","while","import","from","as","try","except","with","pass","and","or","not","in","is","None","True","False","lambda","yield","raise","break","continue","async","await"],

    "javascript": ["function","const","let","var","return","if","else","for","while","import","export","from","class","new","this","typeof","instanceof","throw","try","catch","finally","async","await","null","undefined","true","false"],

    "typescript": ["function","const","let","var","return","if","else","for","while","import","export","from","class","interface","type","new","this","typeof","instanceof","throw","try","catch","finally","async","await","null","undefined","true","false","enum","namespace","declare"],

    "cpp":        ["int","float","double","char","bool","void","return","if","else","for","while","do","switch","case","break","continue","new","delete","class","struct","public","private","protected","include","using","namespace","template","typedef"],

    "c":          ["int","float","double","char","bool","void","return","if","else","for","while","do","switch","case","break","continue","struct","typedef","include","define","ifdef","endif"],

    "java":       ["int","float","double","char","boolean","void","return","if","else","for","while","do","switch","case","break","continue","new","class","interface","extends","implements","public","private","protected","static","final","import","package","try","catch","finally","throw","throws","null","true","false"],

    "csharp":     ["int","float","double","char","bool","string","void","return","if","else","for","while","do","switch","case","break","continue","new","class","interface","public","private","protected","static","using","namespace","try","catch","finally","throw","null","true","false","var","async","await"],

    "rust":       ["fn","let","mut","const","if","else","for","while","loop","match","return","use","mod","pub","struct","enum","impl","trait","where","self","Self","true","false","None","Some","Ok","Err","Box","Vec","String","str"],

    "go":         ["func","var","const","type","return","if","else","for","range","switch","case","break","continue","go","defer","import","package","struct","interface","nil","true","false","chan","map","make","new","len","cap","append"],

    "html":       [], "css":  [], "json": [],

    "sql":        ["SELECT","FROM","WHERE","JOIN","LEFT","RIGHT","INNER","OUTER","ON","GROUP","BY","ORDER","HAVING","INSERT","INTO","VALUES","UPDATE","SET","DELETE","CREATE","TABLE","DROP","ALTER","INDEX","DISTINCT","COUNT","SUM","AVG","MAX","MIN","AS","AND","OR","NOT","NULL","IS","IN","LIKE","BETWEEN","UNION","ALL"],

    "bash":       ["if","then","else","elif","fi","for","while","do","done","case","esac","function","return","export","local","echo","exit","source","cd","ls","grep","awk","sed","cat","chmod","mkdir","rm","cp","mv"],

    "shell":      ["if","then","else","elif","fi","for","while","do","done","case","esac","function","return","export","local","echo","exit","source"],

    "default":    ["def","class","return","if","else","for","while","import","from","as","try","except","with","pass","function","const","let","var","new","this"],

}


def _highlight_code(lang: str, raw_code: str) -> str:
    lang_key = (lang or "default").lower()
    if lang_key not in _THEMES:
        lang_key = "default"
    c   = _THEMES[lang_key]
    kws = _KW.get(lang_key, _KW["default"])
    code = html.escape(raw_code)
    code = re.sub(r'(&quot;.*?&quot;|&#x27;.*?&#x27;)',
                  lambda m: f"<span style='color:{c['string']}'>{m.group(0)}</span>", code)
    code = re.sub(r'(//[^\n]*|#[^\n]*|/\*.*?\*/)',
                  lambda m: f"<span style='color:{c['comment']}'>{m.group(0)}</span>",
                  code, flags=re.DOTALL)
    code = re.sub(r'\b(\d+\.?\d*)\b',
                  lambda m: f"<span style='color:{c['number']}'>{m.group(0)}</span>", code)
    if kws:
        pattern = r'\b(' + '|'.join(re.escape(k) for k in kws) + r')\b'
        code = re.sub(pattern,
                      lambda m: f"<span style='color:{c['keyword']};font-weight:bold'>{m.group(0)}</span>",
                      code)
    return code


def _code_block_html(lang: str, raw_code: str, block_id: str) -> str:
    lang_key = (lang or "default").lower()
    if lang_key not in _THEMES:
        lang_key = "default"
    c           = _THEMES[lang_key]
    highlighted = _highlight_code(lang_key, raw_code)
    lang_label  = (lang or "code").upper()
    encoded     = base64.b64encode(raw_code.encode()).decode()
    r, g, b     = _tc()
    return (
        f"<div style='margin:6px 0; border-radius:8px; overflow:hidden; "
        f"border:1px solid {c['border']};'>"
        f"<div style='background:rgba(0,0,0,0.2); padding:4px 10px; "
        f"display:flex; justify-content:space-between; align-items:center; "
        f"border-bottom:1px solid {c['border']};'>"
        f"<span style='color:{c['border']}; font-family:Orbitron,monospace; "
        f"font-size:8pt; font-weight:600;'>{lang_label}</span>"
        f"<a href='copy:{encoded}' style='color:rgba({r},{g},{b},0.5); font-size:8pt; "
        f"text-decoration:none; font-family:Consolas,monospace; cursor:pointer;'> 📄 copy</a>"
        f"</div>"
        f"<pre style='background:rgba(0,0,0,0.2); color:{c['text']}; "
        f"font-family:Consolas,monospace; font-size:9pt; "
        f"padding:10px 12px; margin:0; white-space:pre-wrap; word-break:break-word;'>"
        f"{highlighted}</pre></div>"
    )


def _format_response(raw_text: str) -> tuple:
    code_re  = re.compile(r"```([\w#+-]*)?\n(.*?)```", re.DOTALL)
    raw_text = raw_text.strip().replace("\r", "").replace("\\n", "\n")
    plain_blocks = []

    if not re.search(r"```", raw_text) and re.search(
            r"\b(def |class |#include|public static void|function )\b", raw_text):
        raw_text = f"```python\n{raw_text}\n```"

    parts    = []
    last_end = 0
    for i, match in enumerate(code_re.finditer(raw_text)):
        start, end = match.span()
        lang, code = match.group(1), match.group(2)
        if start > last_end:
            parts.append(("text", raw_text[last_end:start]))
        parts.append(("code", lang, code, f"block_{i}"))
        plain_blocks.append(code)
        last_end = end
    if last_end < len(raw_text):
        parts.append(("text", raw_text[last_end:]))

    r, g, b = _tc()
    chunks  = []
    for part in parts:
        if part[0] == "text":
            inline = re.sub(
                r"`([^`\n]+)`",
                rf"<code style='background:rgba({r},{g},{b},0.1);"
                rf"border:1px solid rgba({r},{g},{b},0.3); border-radius:3px;"
                rf"padding:1px 4px; color:rgba({r},{g},{b},0.9); font-family:Consolas;'>\1</code>",
                html.escape(part[1]))
            inline = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#ffffff;'>\1</b>", inline)
            inline = re.sub(
                r"(?m)^#{1,3} (.+)$",
                rf"<span style='color:rgb({r},{g},{b}); font-family:Orbitron; font-weight:bold;'>\1</span>",
                inline)
            chunks.append(inline.replace("\n", "<br>"))
        elif part[0] == "code":
            _, lang, code, bid = part
            chunks.append(_code_block_html(lang, code, bid))

    return "".join(chunks), plain_blocks


# ================================================================== #
#  Summariser                                                         #
# ================================================================== #

class SummarizerWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    @pyqtSlot()
    def run(self):
        try:
            ext  = os.path.splitext(self.file_path)[1].lower()
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
                text = "\n".join(p.text for p in doc.paragraphs)
            else:
                self.error.emit("⚠️ Unsupported file type.")
                return
            if not text.strip():
                self.error.emit("⚠️ No readable text found.")
                return
            self.progress.emit("🔹 Summarising document…")
            summary = get_response_from_atom(f"Summarise this text concisely:\n\n{text}")
            self.finished.emit(summary)
        except Exception as e:
            self.error.emit(f"⚠️ Error: {e}")


class SummarizerMixin:
    def open_file_for_summary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "Documents (*.txt *.pdf *.docx)")
        if not path:
            return
        r, g, b = _tc()
        self.message_signal.emit(
            f"<div style='color:rgba({r},{g},{b},0.7);'>📂 Summarising: {path}</div>")

        thread = QThread(self)
        worker = SummarizerWorker(path)
        worker.moveToThread(thread)
        worker.progress.connect(lambda m: self.message_signal.emit(
            f"<div style='color:rgba({_tc()[0]},{_tc()[1]},{_tc()[2]},0.65);'>{m}</div>"))
        worker.error.connect(lambda m: self.message_signal.emit(
            f"<div style='color:#ff5555;'>{m}</div>"))
        worker.finished.connect(self.on_summary_finished)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @pyqtSlot(str)
    def on_summary_finished(self, summary: str):
        body, _ = _format_response(summary)
        r, g, b = _tc()
        self.message_signal.emit(
            f"<div style='text-align:left; margin:6px;'>"
            f"<span style='color:rgb({r},{g},{b});'><b>A.T.O.M (summary):</b></span><br>"
            f"{body}</div>")
        speak_response("Here is the summary of your document.")


# ================================================================== #
#  Main terminal widget                                               #
# ================================================================== #

class TerminalChat(QWidget, SummarizerMixin):
    message_signal = pyqtSignal(str)

    def __init__(self):
        self._processing     = False
        self._voice_mode_val = False
        super().__init__()
        self.voice_mode = False
        self._build_ui()
        self.message_signal.connect(self.append_message)
        self.output.anchorClicked.connect(self._on_anchor_clicked)
        theme_manager.theme_changed.connect(self.apply_theme)

    # ── build UI ─────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        r, g, b = _tc()

        self.output = QTextBrowser()
        self.output.setReadOnly(True)
        self.output.setOpenLinks(False)
        self.output.setOpenExternalLinks(False)
        self.output.setFont(QFont("Consolas", 10))
        layout.addWidget(self.output)

        input_row = QHBoxLayout()

        self.addDocButton = QPushButton("+")
        self.addDocButton.setToolTip("Add document to summarise")
        self.addDocButton.setFixedSize(36, 36)
        self.addDocButton.setCursor(Qt.PointingHandCursor)
        self.addDocButton.clicked.connect(self.open_file_for_summary)

        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(r, g, b))
        glow.setOffset(0)
        self.addDocButton.setGraphicsEffect(glow)
        self._glow_effect = glow
        ga = QPropertyAnimation(glow, b"blurRadius")
        ga.setStartValue(15); ga.setEndValue(35)
        ga.setDuration(1000); ga.setEasingCurve(QEasingCurve.InOutSine)
        ga.setLoopCount(-1); ga.start()
        self._glow_anim = ga

        self.input = QTextEdit()
        self.input.setMinimumHeight(36)
        self.input.setMaximumHeight(100)
        self.input.document().contentsChanged.connect(self._resize_input)
        self.input.setPlaceholderText("Type here and press Enter… (try /help)")
        self.input.setFont(QFont("Consolas", 9))
        self.input.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.input.setLineWrapMode(QTextEdit.WidgetWidth)
        self.input.installEventFilter(self)

        self.sendButton = QPushButton("↑")
        self.sendButton.setToolTip("Send message (or press Enter)")
        self.sendButton.setFixedSize(36, 36)
        self.sendButton.setCursor(Qt.PointingHandCursor)
        self.sendButton.clicked.connect(self.send_message)

        input_row.addWidget(self.addDocButton)
        input_row.addWidget(self.input)
        input_row.addWidget(self.sendButton)
        layout.addLayout(input_row)

        # Apply initial theme styles
        self.apply_theme(theme_manager.color)

    def apply_theme(self, color: str):
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()

        self.output.setStyleSheet(f"""
            QTextBrowser {{
                background: rgba(0,0,0,0.30);
                border: 1px solid rgba({r},{g},{b},0.25);
                border-radius: 8px;
                color: #c9d1d9;
                selection-background-color: rgba({r},{g},{b},0.3);
            }}
        """)
        self.input.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0,0,0,0.25);
                border: 1px solid rgba({r},{g},{b},0.4);
                border-radius: 6px;
                color: #c9d1d9;
            }}
        """)
        self.sendButton.setStyleSheet(f"""
            QPushButton {{
                color: rgb({r},{g},{b}); font-size:16px; font-weight:bold;
                background: rgba({r},{g},{b},0.08);
                border: 1px solid rgba({r},{g},{b},0.35); border-radius: 8px;
            }}
            QPushButton:hover  {{ background: rgba({r},{g},{b},0.22); }}
            QPushButton:pressed {{ background: rgba({r},{g},{b},0.35); }}
        """)
        self.addDocButton.setStyleSheet(f"""
            QPushButton {{
                color: rgb({r},{g},{b}); font-size:20px; font-weight:bold;
                background: rgba(0,0,0,0.1);
                border: 1px solid rgb({r},{g},{b}); border-radius: 8px;
            }}
            QPushButton:hover {{ background: rgba({r},{g},{b},0.3); }}
        """)
        # Update glow colour
        if hasattr(self, '_glow_effect'):
            self._glow_effect.setColor(QColor(r, g, b))

    def _resize_input(self):
        """Resize input box to fit content, clamped between min and max height."""
        doc_height = int(self.input.document().size().height())
        margins    = self.input.contentsMargins()
        total      = doc_height + margins.top() + margins.bottom() + 8
        clamped    = max(36, min(total, 100))
        self.input.setFixedHeight(clamped)

    # ── event filter ─────────────────────────────────────────────────
    def eventFilter(self, source, event):
        if source == self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                if event.isAutoRepeat():
                    return True
                self.send_message()
                return True
        return super().eventFilter(source, event)

    # ── append HTML ──────────────────────────────────────────────────
    @pyqtSlot(str)
    def append_message(self, html_fragment: str):
        self.output.moveCursor(QTextCursor.End)
        self.output.insertHtml(html_fragment + "<br>\n")
        self.output.moveCursor(QTextCursor.End)

    # ── send message ─────────────────────────────────────────────────
    def send_message(self):
        if not hasattr(self, '_processing'):
            self._processing = False
        if self._processing:
            return

        user_input = self.input.toPlainText().strip()
        if not user_input:
            return

        if user_input.lstrip().startswith("/"):
            self._handle_slash(user_input)
            return

        self._processing = True
        self.input.clear()

        r, g, b = _tc()
        self.message_signal.emit(
            f"<div style='text-align:right; margin:6px;'>"
            f"<span style='background:rgba({r},{g},{b},0.12); color:#c9d1d9; "
            f"padding:6px 12px; border-radius:12px 12px 12px 12px; "
            f"display:inline-block; max-width:70%; font-family:Consolas; font-size:9pt;'>"
            f"<b>You:</b> {html.escape(user_input)}</span></div>"
        )

        def process():
            try:
                result = handle_command(user_input)
                if result:
                    self._display_atom(result)
                    if self.voice_mode:
                        threading.Thread(target=speak_response, args=(result,), daemon=True).start()
                    return

                from model_process import route_and_respond, run_agentic_task
                from agent import is_agentic_request
                _status = lambda m: self.message_signal.emit(
                    f"<div style='color:rgba({r},{g},{b},0.6); font-size:8.5pt;'>{m}</div>"
                )
                if is_agentic_request(user_input):
                    reply = run_agentic_task(user_input, status_fn=_status)
                else:
                    reply = route_and_respond(
                        user_input,
                        max_tokens=800,
                        temperature=0.5,
                        status_fn=_status,
                    )

                self._display_atom(reply)
                if self.voice_mode:
                    threading.Thread(target=speak_response, args=(reply,), daemon=True).start()
            except Exception as e:
                self.message_signal.emit(f"<div style='color:#ff5555;'>⚠️ Error: {e}</div>")
            finally:
                self._processing = False

        threading.Thread(target=process, daemon=True).start()

    # ── slash commands ───────────────────────────────────────────────
    def _handle_slash(self, cmd: str):
        cmd_lower = cmd.lower().strip()
        r, g, b = _tc()
        if cmd_lower == "/help":
            self.message_signal.emit(_build_help_text())
        elif cmd_lower == "/clear":
            self.output.clear()
        elif cmd_lower == "/model":
            from local_engine import get_active_model_name
            self._display_atom(f"Active model: **{get_active_model_name()}**")
        elif cmd_lower == "/models":
            from local_engine import list_available_models
            models = "\n".join(f"  • {m}" for m in list_available_models())
            self._display_atom(f"Available models:\n{models}")
        else:
            self.message_signal.emit(
                f"<div style='color:#ff8888;'>❓ Unknown command: {html.escape(cmd)}. "
                f"Type /help for a list.</div>")

    # ── display A.T.O.M response ─────────────────────────────────────
    def _display_atom(self, text: str):
        body, _ = _format_response(text)
        encoded = base64.b64encode(text.encode()).decode()
        r, g, b = _tc()
        atom_html = (
            f"<div style='text-align:left; margin:6px 2px;'>"
            f"<div style='display:flex; justify-content:space-between; "
            f"align-items:center; margin-bottom:3px;'>"
            f"<span style='color:rgb({r},{g},{b}); font-family:Orbitron,monospace; "
            f"font-size:8pt; font-weight:600; letter-spacing:0.05em;'>A.T.O.M</span>"
            f"<a href='copy:{encoded}' style='color:rgba({r},{g},{b},0.5); font-size:8pt; "
            f"text-decoration:none; font-family:Consolas,monospace;'> 📄 copy</a>"
            f"</div>"
            f"<div style='color:#c9d1d9; font-family:Consolas,monospace; font-size:10pt; "
            f"background:rgba({r},{g},{b},0.08); "
            f"border:1px solid rgba({r},{g},{b},0.12); "
            f"border-left:2px solid rgba({r},{g},{b},0.4); "
            f"border-radius:0 10px 10px 0; "
            f"padding:7px 10px; margin-top:2px;'>"
            f"{body}</div></div>"
        )
        self.message_signal.emit(atom_html)

    # ── copy handler ─────────────────────────────────────────────────
    @pyqtSlot('QUrl')
    def _on_anchor_clicked(self, url):
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("copy:"):
            encoded = url_str[5:]
            try:
                text = base64.b64decode(encoded.encode()).decode()
                QApplication.clipboard().setText(text)
                r, g, b = _tc()
                self.message_signal.emit(
                    f"<div style='color:rgba({r},{g},{b},0.5); font-size:8pt; "
                    f"text-align:right; margin-right:6px;'>✅ Copied to clipboard</div>")
            except Exception:
                pass