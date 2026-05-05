# A.T.O.M/UI_ATOM.py
"""
Main UI entry point.
Splash now offers:
  1. Download Phi (conversation model)
  2. Download Mistral (agent reasoning model — recommended for full agentic use)
  3. Use existing folder

Fixes applied (v2):
  1. _mistral_download_thread: was importing download_mistral from local_engine
     (wrong module) — fixed to import from agent_model where it's actually defined.
  2. _load_mistral_thread: was logging status but never calling load_agent_model() —
     fixed so selecting an existing Mistral folder actually loads the model.
  3. start_voice_mode > do_ai: both branches of if/else called run_agent() —
     else branch now correctly falls back to get_response_from_atom() for Phi.
  4. StreamRedirector: stdout/stderr sends raw text into append_message which
     expects HTML — wrapped in a plain <span> so it doesn't break layout.
  5. _choose_existing_folder: had `from UI_ATOM import ACTIVE_MODEL` inside
     the method (circular self-import) — removed, uses module-level dict directly.
  6. _mistral_download_thread: never emitted ready_to_launch after a fresh
     Mistral download, so the main window never opened — emit added.
  7. TerminalPanel.send_message bypass: typed input called get_response_from_atom
     directly, skipping the agent loop — now routes through run_agent like voice does.
"""
import faulthandler
import logging
faulthandler.enable()
logging.basicConfig(
    filename="atom_crash.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)
import os
import sys
import ctypes
import threading
import command
from theme import theme_manager
from pathlib import Path
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMenu, QProgressBar, QFileDialog, QComboBox,
    QSplitter
)
from PyQt5.QtCore import pyqtSignal, QTimer, QMetaObject, Qt, QSettings
from PyQt5.QtGui import QFont, QMovie, QColor

import voice_atom
from tts_atom import speak_response
from local_engine import download_model_hf, find_local_gguf, load_model, set_manual_model_path
from command import handle_command

from panels.SystemPanel   import SystemPanel
from panels.TerminalPanel import TerminalChat
from panels.KeyboardPanel import KeyboardWidget, CollapsibleKeyboard
from panels.SettingsPanel import SettingsPanel
from panels.FilesPanel    import FilesPanel

# FIX 1: import from agent_model (correct module), not local_engine
from agent_model import load_agent_model, agent_model_available, download_mistral

font = QFont("Orbitron")

ACTIVE_MODEL = {"type": None}  # "phi" | "mistral"


# ================================================================= #
#  Splash Screen                                                      #
# ================================================================= #
class SplashScreen(QWidget):
    update_status_signal   = pyqtSignal(str)
    update_progress_signal = pyqtSignal(int)
    ready_to_launch        = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(520, 460)
        self.apply_blur_effect()

        config_path        = os.path.join(Path.home(), "atom_config.ini")
        self.settings      = QSettings(config_path, QSettings.IniFormat)
        self.download_path = self.settings.value("model_path", str(Path.home() / "A.T.O.M/models"))
        self.model_choice  = self.settings.value("model_choice", "Phi-3-mini-instruct")
        # Reset any invalid saved model choice back to Phi-3
        if self.model_choice not in ["Phi-3-mini-instruct"]:
            self.model_choice = "Phi-3-mini-instruct"
            self.settings.setValue("model_choice", "Phi-3-mini-instruct")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        title = QLabel("A.T.O.M")
        title.setFont(QFont("Orbitron", 30))
        title.setStyleSheet("color: rgb(77, 255, 219);")
        layout.addWidget(title)

        sub = QLabel("Advanced Task Oriented Model")
        sub.setFont(QFont("Orbitron", 9))
        sub.setStyleSheet("color: rgba(77,255,219,0.6);")
        layout.addWidget(sub)

        self.label_status = QLabel("Initializing…")
        self.label_status.setFont(QFont("Orbitron", 11))
        self.label_status.setStyleSheet("color: gray;")
        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)

        lbl = QLabel("Conversation Model (Phi):")
        lbl.setFont(QFont("Orbitron", 9))
        lbl.setStyleSheet("color: rgb(200,200,200);")
        layout.addWidget(lbl)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["Phi-3-mini-instruct"])
        self.model_combo.setCurrentText(self.model_choice)
        self.model_combo.currentTextChanged.connect(self._save_model_choice)
        self.model_combo.setStyleSheet("""
            QComboBox { background-color:rgba(77,255,219,0.2); color:rgb(77,255,219);
                        font-weight:bold; padding:5px; border:1px solid rgb(77,255,219); border-radius:5px; }
            QComboBox QAbstractItemView { background-color:rgba(0,0,0,0.8);
                        selection-background-color:rgb(77,255,219); color:white; }
        """)
        layout.addWidget(self.model_combo)

        self.loading_gif = QLabel()
        self.loading_gif.setAlignment(Qt.AlignCenter)
        self.movie = QMovie("F:\Experiments\A.T.O.M_v3\sparkels.gif")
        self.loading_gif.setMovie(self.movie)
        self.movie.start()
        layout.addWidget(self.loading_gif, alignment=Qt.AlignCenter)

        btn_style = (
            "QPushButton { background-color:rgba(77,255,219,0.8); font-weight:bold; "
            "border-radius:6px; padding:6px; }"
            "QPushButton:hover { background-color:rgba(77,255,219,1.0); }"
        )
        alt_style = (
            "QPushButton { background-color:rgba(77,255,180,0.8); font-weight:bold; "
            "border-radius:6px; padding:6px; }"
            "QPushButton:hover { background-color:rgba(77,255,180,1.0); }"
        )
        agent_style = (
            "QPushButton { background-color:rgba(89,245,195,0.8); color:Black; "
            "font-weight:bold; border-radius:6px; padding:6px; }"
            "QPushButton:hover { background-color:rgba(89,245,195,1.0); }"
        )

        btn_mistral = QPushButton("🤖 Mistral-7B-Instruct — better for agentic tasks")
        btn_mistral.setStyleSheet(agent_style)
        btn_mistral.setToolTip(
            "Mistral-7B-Instruct gives A.T.O.M full agentic tool-calling capability.\n"
            "Required for the ReAct reasoning loop. Phi handles conversation only."
        )
        btn_mistral.clicked.connect(self._start_mistral_download)
        layout.addWidget(btn_mistral)

        btn_phi = QPushButton("📥 Download Phi — better for chat and light coding tasks")
        btn_phi.setStyleSheet(btn_style)
        btn_phi.clicked.connect(self._start_phi_download)
        layout.addWidget(btn_phi)

        btn_existing = QPushButton("📂 Use Existing Model Folder")
        btn_existing.setStyleSheet(alt_style)
        btn_existing.clicked.connect(self._choose_existing_folder)
        layout.addWidget(btn_existing)

        btn_launch = QPushButton("▶ Launch without downloading")
        btn_launch.setStyleSheet(
            "QPushButton { background-color:rgba(40,40,40,0.8); color:rgb(77,255,219); "
            "font-weight:bold; border:1px solid rgb(77,255,219); border-radius:6px; padding:4px; }"
        )
        btn_launch.clicked.connect(self.ready_to_launch.emit)
        layout.addWidget(btn_launch)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFont(QFont("Orbitron", 8))
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar { background-color:rgba(77,255,219,0.2); border:none; border-radius:10px; }
            QProgressBar::chunk { background-color:rgb(77,255,219); border-radius:10px; }
        """)
        layout.addWidget(self.progress)

        self.update_status_signal.connect(self.label_status.setText)
        self.update_progress_signal.connect(self.progress.setValue)
        self._update_status(f"Ready. Models folder: {self.download_path}")

    # ── Helpers ──────────────────────────────────────────────────── #
    def _save_model_choice(self, val):
        self.model_choice = val
        self.settings.setValue("model_choice", val)

    def _update_status(self, msg):
        self.update_status_signal.emit(msg)

    def _update_progress(self, val):
        self.update_progress_signal.emit(val)

    # ── Phi download ──────────────────────────────────────────────── #
    def _start_phi_download(self):
        ACTIVE_MODEL["type"] = "phi"
        if not self.download_path:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder for Phi Download")
            if not folder:
                self._update_status("⚠️ No folder selected.")
                return
            self.download_path = folder
            self.settings.setValue("model_path", folder)
        threading.Thread(target=self._phi_download_thread, daemon=True).start()

    def _phi_download_thread(self):
        success = download_model_hf(
            self.model_choice, save_dir=self.download_path,
            status_fn=self._update_status, progress_fn=self._update_progress,
        )
        if success:
            self._update_status("✅ Phi download complete. Loading…")
            self._load_phi_thread()
            self.ready_to_launch.emit()

    # ── Mistral download ──────────────────────────────────────────── #
    def _start_mistral_download(self):
        ACTIVE_MODEL["type"] = "mistral"
        if not self.download_path:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder for Mistral Download")
            if not folder:
                return
            self.download_path = folder
            self.settings.setValue("model_path", folder)
        threading.Thread(target=self._mistral_download_thread, daemon=True).start()

    def _mistral_download_thread(self):
        try:
            success = download_mistral(
                save_dir=self.download_path,
                status_fn=self._update_status,
                progress_fn=self._update_progress,
            )

            if success:
                # ✅ DO NOT load model here
                self._update_status("[INFO] ✅ Mistral download complete.")
                self._update_status("[INFO]  Model will load automatically on first use.")

                # Launch UI
                self.ready_to_launch.emit()

        except Exception as e:
            self._update_status(f"[ERROR] ❌ Mistral download error: {e}")

    # ── Use existing folder ───────────────────────────────────────── #
    def _choose_existing_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Existing Model Folder")
        if not folder:
            return

        # FIX 5: removed `from UI_ATOM import ACTIVE_MODEL` — that was a circular
        # self-import. ACTIVE_MODEL is already in this module's global scope.
        self.download_path = folder
        self.settings.setValue("model_path", folder)
        self._update_status(f"📂 Using folder: {folder}")

        mistral_found = False
        phi_found     = False

        for root, _, files in os.walk(folder):
            for f in files:
                if f.endswith(".gguf"):
                    name = f.lower()
                    if "mistral" in name:
                        mistral_found = True
                    elif "phi" in name:
                        phi_found = True

        if mistral_found:
            ACTIVE_MODEL["type"] = "mistral"
            self._update_status("🤖 Detected Mistral model")
            threading.Thread(target=self._load_mistral_thread, daemon=True).start()

        elif phi_found:
            ACTIVE_MODEL["type"] = "phi"
            self._update_status("🧠 Detected Phi model")
            if set_manual_model_path(self.model_choice, folder,
                                     status_fn=self._update_status):
                self._update_status(f"✅ Model path registered for {self.model_choice}")
            threading.Thread(target=self._load_phi_thread, daemon=True).start()

        else:
            self._update_status("❌ No valid GGUF model found in folder")
            return

        self.ready_to_launch.emit()

    def _load_mistral_thread(self):
        try:

            self._update_status("[INFO]  Mistral model detected.")
            self._update_status("[INFO]  Ready (will load automatically on first request)")

        except Exception as e:
            self._update_status(f"[ERROR] ❌ Mistral setup error: {e}")

    def _load_phi_thread(self):
        if ACTIVE_MODEL["type"] == "mistral":
            self._update_status("[INFO]  Skipping Phi (Mistral active)")
            return

        if not find_local_gguf(self.model_choice, self.download_path):
            self._update_status("[WARN] ⚠️ Phi model not found. Please download.")
            return

        try:
            load_model(self.model_choice, save_dir=self.download_path,
                       status_fn=self._update_status)
            self._update_status("[INFO]  Phi model loaded.")
        except Exception as e:
            self._update_status(f"[ERROR] ❌ Error loading Phi: {e}")

    # ── Win11 blur ────────────────────────────────────────────────── #
    def apply_blur_effect(self):
        hwnd = int(self.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENTPOLICY)),
                        ("SizeOfData", ctypes.c_size_t)]

        accent = ACCENTPOLICY()
        accent.AccentState   = 3
        accent.GradientColor = 0x99000000
        data = WINCOMPATTRDATA()
        data.Attribute  = 19
        data.Data       = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))


# ================================================================= #
#  stdout/stderr redirector                                           #
# ================================================================= #
class StreamRedirector(QtCore.QObject):
    message_signal = QtCore.pyqtSignal(str)

    def __init__(self, write_callback):
        super().__init__()
        self.message_signal.connect(write_callback)

    def write(self, text):
        if text and str(text).strip():
            # FIX 4: append_message expects an HTML fragment. Raw stdout/stderr text
            # passed unwrapped would either render as malformed HTML or break layout.
            # Wrap in a muted <span> so it appears as styled plain text in the terminal.
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self.message_signal.emit(
                f"<span style='color:rgba(180,180,180,0.6); font-size:8.5pt;'>{safe}</span>"
            )

    def flush(self):
        pass


# ================================================================= #
#  Main UI                                                            #
# ================================================================= #
class AtomUI(QMainWindow):
    voice_result = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.no_speech_counter = 0
        self.setGeometry(100, 100, 1300, 800)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowSystemMenuHint |
            QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            "background-color:rgba(0,0,0,0.2); color:rgb(77,255,219); "
            "border-radius:5px; border:1px solid rgba(179,255,240,0.2);"
        )
        try:
            self.apply_blur_effect()
        except Exception:
            pass

        self.offset         = None
        self.chat_input     = None
        self.keyboard_panel = None
        self.voice_mode     = None

        self.init_ui()

        self.silence_timer = QTimer(self)
        self.silence_timer.setInterval(30_000)
        self.silence_timer.setSingleShot(True)
        self.silence_timer.timeout.connect(self._auto_stop_due_to_silence)

        try:
            sys.stdout = StreamRedirector(self.terminal_panel.append_message)
            sys.stderr = StreamRedirector(self.terminal_panel.append_message)
        except Exception as e:
            print(f"Redirection failed: {e}")

        self.voice_result.connect(self._on_voice_result)

        theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(theme_manager.color)
        self.settings_panel = SettingsPanel(self)

        threading.Thread(target=self._try_load_agent_model, daemon=True).start()

    def _try_load_agent_model(self):
        try:
            def status(msg):
                QtCore.QMetaObject.invokeMethod(
                    self.terminal_panel, "append_message",
                    Qt.QueuedConnection,
                    QtCore.Q_ARG(str, msg)
                )

            if agent_model_available():
                status("[INFO] 🤖 Mistral available")
            else:
                status("[INFO] ⚠️ No agent model found (Phi fallback)")

        except Exception as e:
            QtCore.QMetaObject.invokeMethod(
                self.terminal_panel, "append_message",
                Qt.QueuedConnection,
                QtCore.Q_ARG(str, f"❌ Agent init error: {e}")
            )

    def closeEvent(self, event):
        try:
            voice_atom.stop_listening()
        except Exception:
            pass
        event.accept()

    def apply_theme(self, color: str):
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()

        self.setStyleSheet(
            f"background-color:rgba(0,0,0,0.2); color:rgb({r},{g},{b}); "
            f"border-radius:5px; border:1px solid rgba({r},{g},{b},0.2);"
        )

        btn_style = f"""
            QPushButton {{
                background-color:rgba({r},{g},{b},0.1);
                color:rgb({r},{g},{b});
                font-size:18px; border:none; border-radius:15px;
            }}
            QPushButton:checked {{ background-color:rgba({r},{g},{b},0.8); }}
        """
        for btn in (self.minimize_btn, self.max_btn):
            btn.setStyleSheet(btn_style)

        self.close_btn.setStyleSheet(
            f"background-color:red; color:rgb({r},{g},{b}); border-radius:15px; border:none;"
        )

        self.mic_button.setStyleSheet(f"""
            QPushButton {{
                background-color:rgba({r},{g},{b},0.1);
                color:rgb({r},{g},{b});
                font-size:14px; border:none; border-radius:6px; padding:0px 8px;
            }}
            QPushButton:checked {{ background-color:rgba({r},{g},{b},0.8); }}
        """)

        for panel in [self.system_panel, self.terminal_panel, self.keyboard_panel,
                      getattr(self, "files_panel", None)]:
            if panel and hasattr(panel, "apply_theme"):
                panel.apply_theme(color)

    def apply_blur_effect(self):
        hwnd = int(self.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENTPOLICY)),
                        ("SizeOfData", ctypes.c_size_t)]

        accent = ACCENTPOLICY()
        accent.AccentState   = 3
        accent.GradientColor = 0x99000000
        data = WINCOMPATTRDATA()
        data.Attribute  = 19
        data.Data       = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

    def init_ui(self):
        titlebar    = QHBoxLayout()
        title_label = QtWidgets.QLabel("A.T.O.M")
        title_label.setStyleSheet("background-color:transparent; border:none; font-size:15px;")
        title_label.setFont(font)
        titlebar.addWidget(title_label)
        titlebar.addStretch()

        self.files_toggle_btn = QPushButton("📁")
        self.files_toggle_btn.setToolTip("Toggle Files Panel")
        self.files_toggle_btn.setFixedSize(30, 30)
        self.files_toggle_btn.clicked.connect(self.toggle_files_panel)
        titlebar.addWidget(self.files_toggle_btn)

        self.minimize_btn = QtWidgets.QPushButton("—")
        self.minimize_btn.setToolTip("Minimize")
        self.max_btn   = QtWidgets.QPushButton("🗖")
        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setToolTip("Close/Quit")
        self.max_btn.clicked.connect(self.toggle_maximize_restore)

        settings_button = QtWidgets.QPushButton("⚙️")
        settings_button.setToolTip("Open Settings Panel")
        settings_button.setCursor(QtCore.Qt.PointingHandCursor)
        settings_button.clicked.connect(self.toggle_settings_panel)
        self.settings_button = settings_button

        self.mic_button = QPushButton("🎙️ Mic")
        self.mic_button.setToolTip("Choose Voice Mode")
        self.mic_button.setFixedSize(150, 30)

        menu = QMenu(self)
        menu.addAction("🎧 Continuous listening").triggered.connect(
            lambda: self.start_voice_mode("continuous"))
        menu.addAction("🎤 One-shot/Click-to-talk").triggered.connect(
            lambda: self.start_voice_mode("click-to-talk"))
        self.mic_button.setMenu(menu)
        self.mic_button.clicked.connect(self.stop_voice_mode)

        btn_style = """
            QPushButton { background-color:rgba(0,255,255,0.1);
                          font-size:18px; border:none; border-radius:15px; }
        """
        for btn in (self.minimize_btn, self.close_btn, settings_button, self.max_btn):
            btn.setFixedSize(30, 30)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.setFont(font)

        self.mic_button.setStyleSheet("""
            QPushButton { background-color:rgba(0,255,255,0.1);
                          font-size:14px; border:none; border-radius:6px; padding:0px 8px; }
        """)
        self.mic_button.setFont(font)
        self.close_btn.setStyleSheet(
            "background-color:red; color:rgb({r},{g},{b});; font-size:18px; "
            "border-radius:15px; border:none;"
        )
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)

        titlebar.addWidget(self.mic_button)
        titlebar.addWidget(settings_button)
        titlebar.addWidget(self.minimize_btn)
        titlebar.addWidget(self.max_btn)
        titlebar.addWidget(self.close_btn)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout  = QVBoxLayout()
        upper_layout = QHBoxLayout()

        self.system_panel   = SystemPanel()
        self.terminal_panel = TerminalChat()

        self.files_panel    = FilesPanel()
        self.files_panel.status_signal.connect(self.terminal_panel.append_message)
        self.files_panel.summarize_requested.connect(self.terminal_panel.open_file_for_summary)
        self.files_panel.setVisible(False)  # start hidden, toggle with button

        command.terminal_widget_ref = self.terminal_panel
        self.chat_input     = self._find_input_widget(self.terminal_panel)
        self.keyboard_panel = CollapsibleKeyboard(self.chat_input)
        self.keyboard_panel.visibility_changed.connect(self._on_keyboard_toggled)

        left_column = QVBoxLayout()
        left_column.addWidget(self.system_panel)
        left_column.addWidget(self.files_panel)  

        upper_layout.addLayout(left_column, 1)
        upper_layout.addWidget(self.terminal_panel, 2)

        # Vertical splitter — terminal+panels on top, keyboard on bottom
        self._main_splitter = QSplitter(Qt.Vertical)

        upper_widget = QWidget()
        upper_widget.setLayout(upper_layout)
        upper_widget.setStyleSheet("background:transparent;")

        self._main_splitter.addWidget(upper_widget)
        self._main_splitter.addWidget(self.keyboard_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)
        self._main_splitter.setHandleWidth(2)
        self._main_splitter.setStyleSheet("""
            QSplitter::handle { background-color: rgba(77,255,219,0.15); }
        """)

        # Collapse keyboard section until toggled
        self._main_splitter.setSizes([10000, 0])

        central_widget.setLayout(main_layout)
        main_layout.addLayout(titlebar)
        main_layout.addWidget(self._main_splitter)

    def _on_keyboard_toggled(self, visible: bool):
            total = self._main_splitter.height()
            if visible:
                self._main_splitter.setSizes([total - 260, 260])
                self.files_panel.setVisible(False)
            else:
                self._main_splitter.setSizes([total, 0])
                self.files_panel.setVisible(True)

    def toggle_files_panel(self):
        if hasattr(self, "files_panel"):
            self.files_panel.setVisible(not self.files_panel.isVisible())

    def toggle_settings_panel(self):
        if self.settings_panel.isVisible():
            self.settings_panel.hide_animated()
        else:
            self.settings_panel.show_animated(self.settings_button)

    def showEvent(self, event):
        super().showEvent(event)
        if self.chat_input:
            self.chat_input.setFocus()

    def mousePressEvent(self, event):
        if hasattr(self, "settings_panel") and self.settings_panel.isVisible():
            if not self.settings_panel.geometry().contains(event.globalPos()):
                self.settings_panel.hide_animated()
        if self.chat_input:
            self.chat_input.setFocus()
        if event.button() == QtCore.Qt.LeftButton:
            self.offset = event.globalPos() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.offset = None
        super().mouseReleaseEvent(event)

    # ── Voice mode ────────────────────────────────────────────────── #
    def start_voice_mode(self, mode="click-to-talk"):
        if self.voice_mode:
            self.stop_voice_mode()
            return

        self.voice_mode = mode
        QMetaObject.invokeMethod(self, "set_mic_state", Qt.QueuedConnection,
                                 QtCore.Q_ARG(object, mode))
        QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                 Qt.QueuedConnection,
                                 QtCore.Q_ARG(str, f"🎙️ Voice mode started ({mode})."))

        def callback(text):
            if not text:
                self.no_speech_counter += 1
                if self.no_speech_counter >= 3:
                    QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                             Qt.QueuedConnection,
                                             QtCore.Q_ARG(str, "⚠️ No speech detected."))
                    self.no_speech_counter = 0
                return
            self.no_speech_counter = 0

            if mode == "continuous":
                QMetaObject.invokeMethod(self.silence_timer, "start", Qt.QueuedConnection)

            QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                     Qt.QueuedConnection,
                                     QtCore.Q_ARG(str, f"User: {text}"))

            resp = None
            try:
                resp = handle_command(text)
            except Exception as e:
                QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                         Qt.QueuedConnection,
                                         QtCore.Q_ARG(str, f"⚠️ Command error: {e}"))

            if resp:
                QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                         Qt.QueuedConnection,
                                         QtCore.Q_ARG(str, f"A.T.O.M: {resp}"))
                threading.Thread(target=lambda: speak_response(resp), daemon=True).start()
            else:
                def do_ai():
                    try:
                        from model_process import route_and_respond

                        reply = route_and_respond(text)

                        QMetaObject.invokeMethod(
                            self.terminal_panel,
                            "append_message",
                            Qt.QueuedConnection,
                            QtCore.Q_ARG(str, f"🗨️ A.T.O.M: {reply}")
                        )

                        speak_response(reply)

                    except Exception as e:
                        QMetaObject.invokeMethod(
                            self.terminal_panel,
                            "append_message",
                            Qt.QueuedConnection,
                            QtCore.Q_ARG(str, f"⚠️ AI error: {e}")
                        )

                threading.Thread(target=do_ai, daemon=True).start()

            if mode == "click-to-talk":
                QMetaObject.invokeMethod(self, "stop_voice_mode", Qt.QueuedConnection)

        voice_atom.start_listening(callback)
        if mode == "continuous":
            self.silence_timer.start()

    @QtCore.pyqtSlot()
    def stop_voice_mode(self):
        if not self.voice_mode:
            return
        try:
            voice_atom.stop_listening()
        except Exception:
            pass
        self.voice_mode = None
        self.silence_timer.stop()
        QMetaObject.invokeMethod(self, "set_mic_state", Qt.QueuedConnection,
                                 QtCore.Q_ARG(object, None))
        QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                 Qt.QueuedConnection,
                                 QtCore.Q_ARG(str, "Voice mode stopped."))

    @QtCore.pyqtSlot()
    def _auto_stop_due_to_silence(self):
        QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                 Qt.QueuedConnection,
                                 QtCore.Q_ARG(str, "⏱️ Stopped (30s silence)."))
        self.stop_voice_mode()

    @QtCore.pyqtSlot(object)
    def set_mic_state(self, mode):
        labels = {None: "🎙️ Mic", "continuous": "🎧 Listening…", "click-to-talk": "🎤 Click to Talk…"}
        self.mic_button.setText(labels.get(mode, "🎤 Mic"))

    def _on_voice_result(self, text):
        if not text:
            self.terminal_panel.append_message("⚠️ No speech detected.")
            return
        self.terminal_panel.append_message(f"User: {text}")

    def toggle_maximize_restore(self):
        if self.isFullScreen():
            self.showNormal()
            self.max_btn.setText("🗖")
        else:
            self.showFullScreen()
            self.max_btn.setText("🗗")
            self.max_btn.setToolTip("Restore")

    def _find_input_widget(self, terminal_panel):
        if terminal_panel is None:
            return None
        for name in ("input", "editor", "text_edit", "plain_edit", "line_edit", "chat_input"):
            w = getattr(terminal_panel, name, None)
            if w is not None:
                return w
        for child in terminal_panel.findChildren(
            (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QLineEdit)
        ):
            return child
        return None


# ================================================================= #
#  Launch                                                             #
# ================================================================= #
if __name__ == "__main__":
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()
    QApplication.processEvents()

    main_window = None

    def launch_main_ui():
        global main_window
        main_window = AtomUI()
        sys.stdout = StreamRedirector(main_window.terminal_panel.append_message)
        sys.stderr = StreamRedirector(main_window.terminal_panel.append_message)
        main_window.show()
        splash.close()
        print("A.T.O.M is online. Ready for commands!")

    splash.ready_to_launch.connect(launch_main_ui)
    sys.exit(app.exec_())