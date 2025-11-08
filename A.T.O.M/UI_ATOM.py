# A.T.O.M/UI_ATOM.py
import os
import sys
import ctypes
import threading
import command
from pathlib import Path
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QProgressBar,QFileDialog, QComboBox
from PyQt5.QtCore import pyqtSignal, QTimer, QMetaObject, Qt, QSettings
from PyQt5.QtGui import QFont, QMovie

# main functions
import voice_atom
from tts_atom import speak_response
from local_engine import download_model_hf, find_local_gguf, load_model, set_manual_model_path 
from command import handle_command

# widget panels import
from panels.SystemPanel import SystemPanel
from panels.TerminalPanel import TerminalChat
from panels.KeyboardPanel import KeyboardWidget
from panels.KeyboardPanel import CollapsibleKeyboard  # collapsible toggle for keyboard

# font
font = QFont("Orbitron")

class SplashScreen(QWidget):
    update_status_signal = pyqtSignal(str)
    update_progress_signal = pyqtSignal(int)
    ready_to_launch = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(500, 380)
        self.apply_blur_effect()

        # ----------------- Config -----------------
        config_path = os.path.join(Path.home(), "atom_config.ini")
        self.settings = QSettings(config_path, QSettings.IniFormat)
        self.download_path = self.settings.value("model_path", str(Path.home() / "A.T.O.M/models"))
        self.model_choice = self.settings.value("model_choice", "Phi-3-mini-instruct")

        # ----------------- Layout -----------------
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        # Title
        self.label_title = QLabel("A.T.O.M")
        self.label_title.setFont(QFont("Orbitron", 30))
        self.label_title.setStyleSheet("color: rgb(77, 255, 219);")
        self.layout.addWidget(self.label_title)

        # Status
        self.label_status = QLabel("Initializing...")
        self.label_status.setFont(QFont("Orbitron", 12))
        self.label_status.setStyleSheet("color: gray;")
        self.layout.addWidget(self.label_status)

        # ----------------- Model Selection -----------------
        self.label_model = QLabel("Select Model:")
        self.label_model.setFont(QFont("Orbitron", 10))
        self.label_model.setStyleSheet("color: rgb(200, 200, 200);")
        self.layout.addWidget(self.label_model)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["Phi-3-mini-instruct", "Phi-4-mini-instruct"])
        self.model_combo.setCurrentText(self.model_choice)
        self.model_combo.currentTextChanged.connect(self.save_model_choice)
        self.model_combo.setStyleSheet("""
            QComboBox { background-color: rgba(77,255,219,0.2); color: rgb(77,255,219); font-weight: bold; padding: 5px; border: 1px solid rgb(77,255,219); border-radius: 5px; }
            QComboBox QAbstractItemView { background-color: rgba(0,0,0,0.8); selection-background-color: rgb(77,255,219); color: white; }
        """)
        self.layout.addWidget(self.model_combo)

        # Loading GIF
        self.loading_gif = QLabel()
        self.loading_gif.setAlignment(Qt.AlignCenter)
        self.movie = QMovie("A.T.O.M/loading.gif")
        self.loading_gif.setMovie(self.movie)
        self.movie.start()
        self.layout.addWidget(self.loading_gif, alignment=Qt.AlignCenter)

        # ----------------- Buttons -----------------
        self.btn_download = QPushButton("📥 Download Model")
        self.btn_download.setStyleSheet("background-color: rgba(77,255,219,0.8); font-weight:bold;")
        self.btn_download.clicked.connect(self.start_download)
        self.layout.addWidget(self.btn_download)

        self.btn_existing = QPushButton("📂 Use Existing Model Folder")
        self.btn_existing.setStyleSheet("background-color: rgba(77,255,200,0.8); font-weight:bold;")
        self.btn_existing.clicked.connect(self.choose_existing_folder)
        self.layout.addWidget(self.btn_existing)


        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFont(QFont("Orbitron", 8))
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar { background-color: rgba(77,255,219,0.2); border: none; border-radius: 10px; }
            QProgressBar::chunk { background-color: rgb(77,255,219); border-radius: 10px; }
            QProgressBar::text { color: black; font-weight: bold; }
        """)
        self.layout.addWidget(self.progress)

        # Connect signals
        self.update_status_signal.connect(self.label_status.setText)
        self.update_progress_signal.connect(self.progress.setValue)

        self.update_status(f"Using folder: {self.download_path}")

    # ----------------- Helpers -----------------
    def save_model_choice(self, val):
        self.model_choice = val
        self.settings.setValue("model_choice", val)

    def update_status(self, msg):
        self.update_status_signal.emit(msg)

    def update_progress(self, val):
        self.update_progress_signal.emit(val)

    # ----------------- Download / Load -----------------
    def start_download(self):
        if not self.download_path:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder for Model Download")
            if not folder:
                self.update_status("⚠️ No folder selected.")
                return
            self.download_path = folder
            self.settings.setValue("model_path", folder)

        threading.Thread(target=self.download_thread, daemon=True).start()

    def download_thread(self):
        success = download_model_hf(
            self.model_choice,
            save_dir=self.download_path,
            status_fn=self.update_status,
            progress_fn=self.update_progress
        )
        if success:
            self.update_status("✅ Download complete.")
            self.init_model_thread()
            self.ready_to_launch.emit()

    # ----------------- Choose Existing Folder -----------------
    def choose_existing_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Existing Model Folder")
        if folder:
            self.download_path = folder
            self.settings.setValue("model_path", folder)
            self.update_status(f"📂 Using folder: {folder}")

            # Set the manual model path dynamically
            if set_manual_model_path(self.model_choice, folder, status_fn=self.update_status):
                self.update_status(f"✅ Model path registered for {self.model_choice}")

            self.init_model_thread()
            self.ready_to_launch.emit()


    def init_model_thread(self):
        threading.Thread(target=self._init_model_thread, daemon=True).start()

    # ----------------- Init Model Thread -----------------
    def _init_model_thread(self):
        if not find_local_gguf(self.model_choice, self.download_path):
            self.update_status("⚠️ Local model not found. Please download or select a folder.")
            return
        try:
            # load_model will now automatically pick the GGUF in the folder
            load_model(self.model_choice, save_dir=self.download_path, status_fn=self.update_status)
            self.update_status("✅ Model loaded successfully.")
        except Exception as e:
            self.update_status(f"❌ Error loading model: {e}")


# ---------------------------------------------------#
#       win 11 blur effect for splash window           #
# ---------------------------------------------------#
    def apply_blur_effect(self):
        hwnd = int(self.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int),
                        ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENTPOLICY)),
                        ("SizeOfData", ctypes.c_size_t)]

        accent = ACCENTPOLICY()
        accent.AccentState = 3
        accent.GradientColor = 0x99000000

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

# ---------------------------------------------------#
#      for displaying text in the terminal           #
# ---------------------------------------------------#
class StreamRedirector(QtCore.QObject):
    message_signal = QtCore.pyqtSignal(str)

    def __init__(self, write_callback):
        super().__init__()
        self.message_signal.connect(write_callback)

    def write(self, text):
        if text and str(text).strip():
            self.message_signal.emit(str(text))

    def flush(self):
        pass

# ---------------------------------------------------#
#                      Main UI                       #
# ---------------------------------------------------#
class AtomUI(QMainWindow):
    voice_result = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.no_speech_counter = 0

        self.setGeometry(100, 100, 1200, 800)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowMinimizeButtonHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.2); color:rgb(77, 255, 219); border-radius: 5px; border: 1px solid rgba(179, 255, 240, 0.2);")
        try:
            self.apply_blur_effect()
        except Exception:
            pass

        self.offset = None
        self.chat_input = None
        self.keyboard_panel = None
        self.voice_mode = None

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

    def closeEvent(self, event):
        try:
            print("Closing A.T.O.M window... shutting down services.")
            try:
                voice_atom.stop_listening()
            except Exception as e:
                print(f"⚠️ Voice listener stop error: {e}")
        except Exception as e:
            print(f"⚠️ Error during shutdown: {e}")
        event.accept()

    # ---------------------------------------------------#
    #       win 11 blur effect for main window           #
    # ---------------------------------------------------#
    def apply_blur_effect(self):
        hwnd = int(self.winId())

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int),
                        ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENTPOLICY)),
                        ("SizeOfData", ctypes.c_size_t)]

        accent = ACCENTPOLICY()
        accent.AccentState = 3
        accent.GradientColor = 0x99000000

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

    # ---------------------------------------------------#
    #                    UI & Layout                     #
    # ---------------------------------------------------#
    def init_ui(self):
        titlebar = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("A.T.O.M")
        title_label.setStyleSheet("background-color: transparent; border: none; font-size: 15px;")
        title_label.setFont(font)
        titlebar.addWidget(title_label)
        titlebar.addStretch()

        self.minimize_btn = QtWidgets.QPushButton("—")
        self.minimize_btn.setToolTip("Minimize")
        self.max_btn = QtWidgets.QPushButton("🗖")
        self.close_btn = QtWidgets.QPushButton("✕")
        self.close_btn.setToolTip("Close/Quit")
        self.max_btn.clicked.connect(self.toggle_maximize_restore)

        # Settings panel button (kept as commented out, can enable)
        settings_button = QtWidgets.QPushButton("⚙️")
        settings_button.setToolTip("Open Settings Panel")
        settings_button.setCursor(QtCore.Qt.PointingHandCursor)
        # settings_button.clicked.connect(self.open_settings_panel)  # your settings logic

        # mic toggle (dropdown for voice mode selection)
        self.mic_button = QPushButton("🎙️ Mic")
        self.mic_button.setToolTip("Choose Voice Mode")
        self.mic_button.setFixedSize(150, 30)  # keep wider button for label

        menu = QMenu(self)
        continuous_mic_input = menu.addAction("🎧 Continuous listening")
        continuous_mic_input.triggered.connect(lambda: self.start_voice_mode("continuous"))
        oneshot_mic_input = menu.addAction("🎤 One-shot/Click-to-talk")
        oneshot_mic_input.triggered.connect(lambda: self.start_voice_mode("oneshot"))
        self.mic_button.setMenu(menu)

        # Clicking the button itself stops current listening session (if any)
        self.mic_button.clicked.connect(self.stop_voice_mode)

        # Style buttons
        for btn in (self.minimize_btn, self.close_btn, settings_button, self.max_btn):
            btn.setFixedSize(30, 30)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet('''
                QPushButton{
                    background-color: rgba(0, 255, 255, 0.1);
                    color: rgb(77, 255, 219);
                    font-size: 18px; border: none;
                    border-radius: 15px;
                }
                QPushButton:checked {
                    background-color: rgba(77, 255, 219, 0.8);
                }
            ''')
            btn.setFont(font)

        # Gives mic (wider) style button
        self.mic_button.setStyleSheet('''
            QPushButton{
                background-color: rgba(0, 255, 255, 0.1);
                color: rgb(77, 255, 219);
                font-size: 14px; border: none;
                border-radius: 6px;
                padding: 0px 8px;
            }
            QPushButton:checked {
                background-color: rgba(77, 255, 219, 0.8);
            }
        ''')
        self.mic_button.setFont(font)

        self.close_btn.setStyleSheet("background-color: red; color: rgb(77, 255, 219); font-size: 18px; border-radius: 15px; border: none;")
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)
        self.max_btn.setToolTip("Fullscreen")

        # add to titlebar (order preserved)
        titlebar.addWidget(self.mic_button)
        titlebar.addWidget(settings_button)
        titlebar.addWidget(self.minimize_btn)
        titlebar.addWidget(self.max_btn)
        titlebar.addWidget(self.close_btn)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        upper_layout = QHBoxLayout()
        lower_layout = QHBoxLayout()
        main_layout.addLayout(titlebar)

        # panels
        self.system_panel = SystemPanel()
        self.terminal_panel = TerminalChat()

        command.terminal_widget_ref = self.terminal_panel  # ref for voice mode function in command.py

        # Instead of passing terminal_panel directly, grab the input widget
        self.chat_input = self._find_input_widget(self.terminal_panel)

        # Now CollapsibleKeyboard correctly wraps a KeyboardWidget
        self.keyboard_panel = CollapsibleKeyboard(self.chat_input)

        # Add panels to layouts
        upper_layout.addWidget(self.system_panel)
        upper_layout.addWidget(self.terminal_panel)
        lower_layout.addWidget(self.keyboard_panel)

        main_layout.addLayout(upper_layout)
        main_layout.addLayout(lower_layout)

        central_widget.setLayout(main_layout)

    # ---------------------------------------------------#
    #        Event Handlers  for window dragging         #
    # ---------------------------------------------------#
    def showEvent(self, event):
        super().showEvent(event)
        if self.chat_input:
            self.chat_input.setFocus()

    def focusInEvent(self, event):
        if self.chat_input:
            self.chat_input.setFocus()
        super().focusInEvent(event)

    def mousePressEvent(self, event):
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

    # ---------------------------------------------------#
    #    Voice mode helpers (start/stop + auto-stop)     #
    # ---------------------------------------------------#
    def start_voice_mode(self, mode="oneshot"):

        if self.voice_mode:
            self.stop_voice_mode()
            return

        self.voice_mode = mode
        QMetaObject.invokeMethod(self, "set_mic_state", Qt.QueuedConnection,
                                QtCore.Q_ARG(object, mode))
        QMetaObject.invokeMethod(self.terminal_panel, "append_message", Qt.QueuedConnection,
                                QtCore.Q_ARG(str, f"🎙️ Voice mode started ({mode})."))

        def callback(text):
            if not text:  # no speech detected
                self.no_speech_counter += 1
                if self.no_speech_counter >= 3:
                    QMetaObject.invokeMethod(
                        self.terminal_panel,
                        "append_message",
                        Qt.QueuedConnection,
                        QtCore.Q_ARG(str, "⚠️ No speech detected.")
                    )
                    self.no_speech_counter = 0
                return
            else:
                self.no_speech_counter = 0

            if not text:
                QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                        Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, "⚠️ No speech detected."))
                if mode == "oneshot":
                    QMetaObject.invokeMethod(self, "stop_voice_mode", Qt.QueuedConnection)
                return

            if mode == "continuous":
                QMetaObject.invokeMethod(self.silence_timer, "start", Qt.QueuedConnection)

            QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                    Qt.QueuedConnection,
                                    QtCore.Q_ARG(str, f"User: {text}"))

            # Hardwired commands first
            resp = None
            try:
                from command import handle_command
                resp = handle_command(text)
            except Exception as e:
                QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                        Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, f"⚠️ Command error: {e}"))

            if resp:
                QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                        Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, f"A.T.O.M: {resp}"))
                from tts_atom import speak_response
                threading.Thread(target=lambda: speak_response(resp), daemon=True).start()
            else:
                def do_ai():
                    try:
                        from local_engine import get_response_from_atom
                        reply = get_response_from_atom(text)
                        QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                                Qt.QueuedConnection,
                                                QtCore.Q_ARG(str, f"🗨️ A.T.O.M: {reply}"))
                        from tts_atom import speak_response
                        speak_response(reply)
                    except Exception as e:
                        QMetaObject.invokeMethod(self.terminal_panel, "append_message",
                                                Qt.QueuedConnection,
                                                QtCore.Q_ARG(str, f"⚠️ LLM error: {e}"))
                threading.Thread(target=do_ai, daemon=True).start()

            if mode == "oneshot":
                QMetaObject.invokeMethod(self, "stop_voice_mode", Qt.QueuedConnection)

        voice_atom.start_listening(callback)

        if mode == "continuous":
            self.silence_timer.start()

    @QtCore.pyqtSlot()
    def stop_voice_mode(self):
        import voice_atom
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
        QMetaObject.invokeMethod(self.terminal_panel, "append_message", Qt.QueuedConnection,
                                QtCore.Q_ARG(str, "Voice mode stopped. Click 🎙️ to start again."))

    @QtCore.pyqtSlot()
    def _auto_stop_due_to_silence(self):
        QMetaObject.invokeMethod(self.terminal_panel, "append_message", Qt.QueuedConnection,
                                QtCore.Q_ARG(str, "⏱️ Stopped listening (30s silence)."))
        self.stop_voice_mode()

    @QtCore.pyqtSlot(object)
    def set_mic_state(self, mode):
        if mode is None:
            self.mic_button.setText("🎙️ Mic")
        elif mode == "continuous":
            self.mic_button.setText("🎧 Listening…")
        elif mode == "oneshot":
            self.mic_button.setText("🎤 One-shot…")
        else:
            self.mic_button.setText("🎤 Mic")

    # ---------------------------------------------------#
    #   (Optional legacy path) Voice result callbacks    #
    # ---------------------------------------------------#
    def _on_voice_result(self, text):
        if not text:
            self.terminal_panel.append_message("⚠️ No speech detected.")
            return

        self.terminal_panel.append_message(f"User: {text}")

        def handle_cmd():
            try:
                cmd_resp = handle_command(text)
                if cmd_resp:
                    self.terminal_panel.append_message(f"A.T.O.M: {cmd_resp}")
                    threading.Thread(target=lambda: speak_response(cmd_resp), daemon=True).start()
                    return True
                return False
            except Exception as e:
                self.terminal_panel.append_message(f"⚠️ Command error: {e}")
                return False

        if handle_cmd():
            return

    # ---------------------------------------------------#
    #       Handle user input from Terminal widget       #
    # ---------------------------------------------------#
    def process_user_input(self, text: str):
        if not text.strip():
            return

        self.terminal_panel.append_message(f"User: {text}")

        if text.strip().lower() in ["exit", "quit", "shutdown", "stop"]:
            self.terminal_panel.append_message("🛑 Exiting A.T.O.M.")
            self.close()
            return

        try:
            cmd_resp = handle_command(text)
        except Exception as e:
            cmd_resp = None
            self.terminal_panel.append_message(f"⚠️ Command handler error: {e}")

        if cmd_resp:
            self.terminal_panel.append_message(f"A.T.O.M: {cmd_resp}")
            threading.Thread(target=lambda: speak_response(cmd_resp), daemon=True).start()
            return

    # ---------------------------------------------------#
    #         Custom window Fullscreen handler           #
    # ---------------------------------------------------#
    def toggle_maximize_restore(self):
        if self.isFullScreen():
            self.showNormal()
            self.max_btn.setText("🗖")
        else:
            self.showFullScreen()
            self.max_btn.setText("🗗")
            self.max_btn.setToolTip("Restore")

    # ---------------------------------------------------#
    #        terminal input finder (By chat GPT)         #
    # ---------------------------------------------------#
    def _find_input_widget(self, terminal_panel):
        if terminal_panel is None:
            return None
        for name in ("input", "editor", "text_edit", "plain_edit", "line_edit", "chat_input"):
            w = getattr(terminal_panel, name, None)
            if w is not None:
                return w
        for child in terminal_panel.findChildren((QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QLineEdit)):
            return child
        return None


# ---------------------------------------------------#
#            Launcher splash + main ui               #
# ---------------------------------------------------#
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # --- Splash screen ---
    splash = SplashScreen()
    splash.show()
    QApplication.processEvents()  # make sure UI updates immediately

    main_window = None

    # Function to launch main UI
    def launch_main_ui():
        global main_window
        main_window = AtomUI()
        # Redirect stdout/stderr to terminal
        sys.stdout = StreamRedirector(main_window.terminal_panel.append_message)
        sys.stderr = StreamRedirector(main_window.terminal_panel.append_message)
        main_window.show()
        splash.close()
        print("✅ A.T.O.M is online. Terminal ready.")

    # Connect the splash's ready_to_launch signal to launch_main_ui
    splash.ready_to_launch.connect(launch_main_ui)

    sys.exit(app.exec_())
