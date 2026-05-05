# A.T.O.M/panels/FilesPanel.py
"""
FilesPanel – shows tracked files/folders, lets the user add items and run
agentic operations (summarise, ask, analyse …).  Output is saved into the
same folder as the source file.
"""

import os
import threading
from pathlib import Path

from PyQt5.QtCore  import Qt, QThread, QObject, pyqtSignal, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui   import QFont, QColor, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QTextEdit,
    QGraphicsDropShadowEffect, QFrame, QSizePolicy, QMenu, QAction
)
from theme import theme_manager



# ── colours & fonts consistent with A.T.O.M theme ──────────────────────────
TEAL   = "rgb(77,255,219)"
TEAL_A = "rgba(77,255,219,0.15)"
FONT   = QFont("Orbitron", 9)
MONO   = QFont("Consolas", 9)

_STYLE_PANEL = f"""
    QWidget {{
        background: transparent;
        color: {TEAL};
    }}
    QLabel {{
        border: none;
        background: transparent;
    }}
    QListWidget {{
        background: rgba(0,0,0,0.25);
        border: 1px solid rgba(77,255,219,0.3);
        border-radius: 6px;
        color: {TEAL};
    }}
    QListWidget::item:selected {{
        background: rgba(77,255,219,0.18);
    }}
    QListWidget::item:hover {{
        background: rgba(77,255,219,0.10);
    }}
    QTextEdit {{
        background: rgba(0,0,0,0.35);
        border: 1px solid rgba(77,255,219,0.3);
        border-radius: 6px;
        color: #e0ffe0;
        font-family: Consolas;
        font-size: 9pt;
    }}
    QPushButton {{
        background: rgba(0,0,0,0.2);
        border: 1px solid rgba(77,255,219,0.6);
        border-radius: 5px;
        color: {TEAL};
        padding: 4px 8px;
        font-family: Orbitron;
        font-size: 9pt;
    }}
    QPushButton:hover  {{ background: rgba(77,255,219,0.2); }}
    QPushButton:pressed{{ background: rgba(77,255,219,0.4); }}
"""


# ── Worker ──────────────────────────────────────────────────────────────────
class FileAgentWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, str)   # (result_text, output_path)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str, operation: str, extra_prompt: str = ""):
        super().__init__()
        self.file_path    = file_path
        self.operation    = operation   # "summarize" | "analyse" | "ask"
        self.extra_prompt = extra_prompt

    @pyqtSlot()
    def run(self):
        from local_engine import get_response_from_atom
        from PyPDF2 import PdfReader
        from docx  import Document as DocxDocument

        path = Path(self.file_path)
        ext  = path.suffix.lower()
        text = ""

        try:
            self.progress.emit(f"📂 Reading {path.name} …")
            if ext == ".txt":
                text = path.read_text(encoding="utf-8", errors="ignore")
            elif ext == ".pdf":
                reader = PdfReader(str(path))
                for page in reader.pages:
                    text += page.extract_text() or ""
            elif ext == ".docx":
                doc = DocxDocument(str(path))
                text = "\n".join(p.text for p in doc.paragraphs)
            elif ext in (".py", ".js", ".ts", ".html", ".css", ".json", ".md",
                         ".cpp", ".c", ".java", ".cs", ".xml", ".yaml", ".yml"):
                text = path.read_text(encoding="utf-8", errors="ignore")
            else:
                self.error.emit(f"⚠️ Unsupported file type: {ext}")
                return

            if not text.strip():
                self.error.emit("⚠️ File appears to be empty.")
                return

            # Build prompt
            if self.operation == "summarize":
                self.progress.emit("🧠 Summarising …")
                prompt = f"Summarise the following document concisely:\n\n{text}"
            elif self.operation == "analyse":
                self.progress.emit("🔍 Analysing …")
                prompt = (f"Analyse the following content and give a detailed breakdown "
                          f"including key topics, structure and insights:\n\n{text}")
            elif self.operation == "ask":
                self.progress.emit("💬 Processing question …")
                prompt = f"{self.extra_prompt}\n\n---\nDocument content:\n{text}"
            else:
                prompt = f"{self.extra_prompt}\n\n{text}"

            result = get_response_from_atom(prompt)

            # Save output to same folder as source file
            stem        = path.stem
            out_name    = f"{stem}_{self.operation}_output.txt"
            out_path    = path.parent / out_name
            out_path.write_text(result, encoding="utf-8")

            self.finished.emit(result, str(out_path))

        except Exception as e:
            self.error.emit(f"⚠️ Error: {e}")


# ── Panel ────────────────────────────────────────────────────────────────────
class FilesPanel(QWidget):
    """Left-side panel:  file list + quick-action buttons + output log."""

    status_signal       = pyqtSignal(str)   # forward to terminal if desired
    # Emitted when the user clicks Summarise. Connect this in the main UI to
    # terminal.open_file_for_summary so the terminal's SummarizerWorker runs.
    summarize_requested = pyqtSignal(str)   # carries the absolute file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_STYLE_PANEL)
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._tracked: list[str] = []    # list of absolute file paths
        self._output_folder: str = ""    # folder for outputs (auto-set per file)
        self._threads = []  #  store active threads for cleanup
        self._build_ui()
        theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(theme_manager.color)  # initial sync


    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Header ──
        header = QLabel("📁  FILES & FOLDERS")
        header.setFont(QFont("Orbitron", 10, QFont.Bold))
        c = self.palette().color(self.foregroundRole())
        r, g, b = c.red(), c.green(), c.blue()
        layout.addWidget(header)
        

        # ── Add buttons ──
        btn_row = QHBoxLayout()
        self.btn_add_file   = self._btn("+ File",   self._add_file)
        self.btn_add_folder = self._btn("+ Folder", self._add_folder)
        self.btn_clear      = self._btn("🗑 Clear",  self._clear_all)
        for b in (self.btn_add_file, self.btn_add_folder, self.btn_clear):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # ── File list ──
        self.file_list = QListWidget()
        self.file_list.setFont(MONO)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._context_menu)
        self.file_list.setToolTip("Right-click for actions")
        self.file_list.setMaximumHeight(180)
        layout.addWidget(self.file_list)

        # ── Action buttons ──
        act_row = QHBoxLayout()
        self.btn_summarize = self._btn("🧠 Summarise", self._run_summarize)
        self.btn_analyse   = self._btn("🔍 Analyse",   self._run_analyse)
        self.btn_ask       = self._btn("💬 Ask",       self._run_ask)
        for b in (self.btn_summarize, self.btn_analyse, self.btn_ask):
            act_row.addWidget(b)
        layout.addLayout(act_row)

        # ── Output folder info ──
        self.lbl_outfolder = QLabel("Output: (same as source file)")
        self.lbl_outfolder.setFont(QFont("Consolas", 8))
        self.lbl_outfolder.setStyleSheet("color: inherit; border: none;")
        self.lbl_outfolder.setWordWrap(True)
        layout.addWidget(self.lbl_outfolder)

        # ── Output log ──
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setFont(MONO)
        self.output_log.setPlaceholderText("Agent output appears here…")
        layout.addWidget(self.output_log)

        # ── Ask input ──
        self.ask_input = QTextEdit()
        self.ask_input.setFixedHeight(50)
        self.ask_input.setFont(MONO)
        self.ask_input.setPlaceholderText("Type a question about the selected file…")
        layout.addWidget(self.ask_input)

        # divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: inherit;")
        layout.addWidget(div)

    def apply_theme(self, color: str):
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()

        self.setStyleSheet(f"""
            QWidget {{
                background: transparent;
                color: rgb({r},{g},{b});
            }}

            QLabel {{
                border: none;
                background: transparent;
            }}

            QListWidget {{
                background: rgba(0,0,0,0.25);
                border: 1px solid rgba({r},{g},{b},0.3);
                border-radius: 6px;
                color: rgb({r},{g},{b});
            }}

            QListWidget::item:selected {{
                background: rgba({r},{g},{b},0.18);
            }}

            QListWidget::item:hover {{
                background: rgba({r},{g},{b},0.10);
            }}

            QTextEdit {{
                background: rgba(0,0,0,0.35);
                border: 1px solid rgba({r},{g},{b},0.3);
                border-radius: 6px;
                color: #e0ffe0;
                font-family: Consolas;
                font-size: 9pt;
            }}

            QPushButton {{
                background: rgba(0,0,0,0.2);
                border: 1px solid rgba({r},{g},{b},0.6);
                border-radius: 5px;
                color: rgb({r},{g},{b});
                padding: 4px 8px;
            }}

            QPushButton:hover {{
                background: rgba({r},{g},{b},0.2);
            }}

            QPushButton:pressed {{
                background: rgba({r},{g},{b},0.4);
            }}
        """)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _btn(self, label: str, slot) -> QPushButton:
        b = QPushButton(label)
        b.setFont(FONT)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _log(self, html: str):
        self.output_log.moveCursor(QTextCursor.End)
        self.output_log.insertHtml(html + "<br>")
        self.output_log.moveCursor(QTextCursor.End)

    def _selected_path(self) -> str | None:
        items = self.file_list.selectedItems()
        if not items:
            # fall back to last added
            if self._tracked:
                return self._tracked[-1]
            return None
        return items[0].data(Qt.UserRole)

    # ── File management ─────────────────────────────────────────────────────
    def _add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Files", "",
            "Documents (*.txt *.pdf *.docx *.py *.js *.ts *.html *.css "
            "*.json *.md *.cpp *.c *.java *.cs *.xml *.yaml *.yml)")
        for p in paths:
            self._register(p)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Folder")
        if folder:
            # list first-level files
            for f in Path(folder).iterdir():
                if f.is_file():
                    self._register(str(f))

    def _register(self, path: str):
        if path in self._tracked:
            return
        self._tracked.append(path)
        item = QListWidgetItem(f"  {Path(path).name}")
        item.setData(Qt.UserRole, path)
        item.setToolTip(path)
        self.file_list.addItem(item)
        self.lbl_outfolder.setText(f"Output → {Path(path).parent}")
        self._log(f"<span style='color:rgba(77,255,219,0.7);'>📎 Added: {Path(path).name}</span>")

    def _clear_all(self):
        self._tracked.clear()
        self.file_list.clear()
        self.output_log.clear()
        self.lbl_outfolder.setText("Output: (same as source file)")

    def _context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.UserRole)
        c = self.palette().color(self.foregroundRole())
        r, g, b = c.red(), c.green(), c.blue()
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(10,20,20,0.95);
                color: rgb({r},{g},{b});
                border:1px solid rgba({r},{g},{b},0.4);
                border-radius:4px;
            }}
            QMenu::item:selected {{
                background: rgba({r},{g},{b},0.18);
            }}
        """)
        a_remove  = menu.addAction("🗑 Remove")
        a_open    = menu.addAction("📂 Open folder")
        a_sum     = menu.addAction("🧠 Summarise")
        a_analyse = menu.addAction("🔍 Analyse")
        action    = menu.exec_(self.file_list.viewport().mapToGlobal(pos))
        if action == a_remove:
            self._tracked.remove(path)
            self.file_list.takeItem(self.file_list.row(item))
        elif action == a_open:
            import subprocess
            subprocess.Popen(f'explorer /select,"{path}"', shell=True)
        elif action == a_sum:
            self.summarize_requested.emit(path)
        elif action == a_analyse:
            self._launch_worker(path, "analyse")

    # ── Actions ─────────────────────────────────────────────────────────────
    def _run_summarize(self):
        path = self._selected_path()
        if not path:
            self._log("<span style='color:orange;'>⚠️ No file selected.</span>")
            return
        # Delegate to the terminal's SummarizerWorker via the signal.
        # The main UI must connect: files_panel.summarize_requested → terminal.open_file_for_summary
        self.summarize_requested.emit(path)

    def _run_analyse(self):
        path = self._selected_path()
        if not path:
            self._log("<span style='color:orange;'>⚠️ No file selected.</span>")
            return
        self._launch_worker(path, "analyse")

    def _run_ask(self):
        path  = self._selected_path()
        question = self.ask_input.toPlainText().strip()
        if not path:
            self._log("<span style='color:orange;'>⚠️ No file selected.</span>")
            return
        if not question:
            self._log("<span style='color:orange;'>⚠️ Please type a question first.</span>")
            return
        self.ask_input.clear()
        self._launch_worker(path, "ask", extra_prompt=question)

    def _cleanup_thread(self, thread):
        if thread in self._threads:
            self._threads.remove(thread)

    def _launch_worker(self, file_path: str, operation: str, extra_prompt: str = ""):
        self._log(f"<span style='color:#4dffd7;'>⚡ Running <b>{operation}</b> on "
                  f"<i>{Path(file_path).name}</i>…</span>")

        thread = QThread(self)
        worker = FileAgentWorker(file_path, operation, extra_prompt)

        self._threads.append(thread)  # reference 
        worker.moveToThread(thread)

        worker.progress.connect(lambda m: self._log(f"<span style='color:rgba(77,255,219,0.65);'>{m}</span>"))
        worker.error.connect   (lambda m: self._log(f"<span style='color:#ff5555;'>{m}</span>"))
        worker.finished.connect(self._on_finished)
        worker.finished.connect(lambda *_: thread.quit())
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        thread.started.connect(worker.run)
        thread.start()

    @pyqtSlot(str, str)
    def _on_finished(self, result: str, output_path: str):
        self.lbl_outfolder.setText(f"✅ Saved → {output_path}")
        preview = result[:600].replace("\n", "<br>")
        self._log(
            f"<hr style='border-color:rgba(77,255,219,0.2);'>"
            f"<span style='color:#00ffc3;'><b>Result:</b></span><br>"
            f"<span style='color:#d0ffd0; font-family:Consolas; font-size:9pt;'>{preview}…</span><br>"
            f"<span style='color:rgba(77,255,219,0.5);'>💾 Full output saved to: {output_path}</span>"
        )
        self.status_signal.emit(f"✅ Agent output saved: {output_path}")