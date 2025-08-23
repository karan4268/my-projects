import sys
import ctypes
import threading
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtGui import QFont, QMovie
from PyQt5.QtCore import Qt

# main functions
from main_atom import start_ollama, process_query
from tts_atom import speak_response
from local_engine import get_response_from_atom
from command import handle_command

# widget panels import
from panels.SystemPanel import SystemPanel
from panels.TerminalPanel import TerminalChat
from panels.KeyboardPanel import KeyboardWidget  

# voice logic (non-blocking)
import voice_atom

# font
font = QFont("Orbitron")

#---------------------------------------------------#
#               startup/splash screen               #
#---------------------------------------------------#
class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(400, 300)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label_title = QLabel("A.T.O.M")
        self.label_title.setFont(QFont("Orbitron", 30))
        self.label_title.setStyleSheet("color: cyan;")
        layout.addWidget(self.label_title)

        self.label_status = QLabel("Initializing...")
        self.label_status.setFont(QFont("Orbitron", 12))
        self.label_status.setStyleSheet("color: white;")
        layout.addWidget(self.label_status)

        # Optional: round loading gif
        self.loading_gif = QLabel()
        self.movie = QMovie("loading.gif")  # put a small circular gif in project
        self.loading_gif.setMovie(self.movie)
        self.movie.start()
        layout.addWidget(self.loading_gif)

        self.setLayout(layout)

    def update_status(self, text):
        self.label_status.setText(text)


#---------------------------------------------------#
#      for displaying text in the terminal          #
#---------------------------------------------------#
class StreamRedirector(QtCore.QObject):
    message_signal = QtCore.pyqtSignal(str)  # safe type for cross-thread signal

    def __init__(self, write_callback):
        super().__init__()
        # Connect the signal to the terminal append function
        self.message_signal.connect(write_callback)

    def write(self, text):
        if text and str(text).strip():
            # emit signal to safely update GUI in main thread
            self.message_signal.emit(str(text))

    def flush(self):
        pass


#---------------------------------------------------#
#                      Main UI                       #
#---------------------------------------------------#
class AtomUI(QMainWindow):
    voice_result = QtCore.pyqtSignal(object)  # receives strings or None

    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowMinimizeButtonHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.2); color:rgb(77, 255, 219); border-radius: 5px; border: 1px solid rgba(179, 255, 240, 0.2);")
        try:
            self.apply_blur_effect()
        except Exception:
            pass

        self.offset = None
        self.chat_input = None         # <-- will be set after TerminalChat is built
        self.keyboard_panel = None

        self.init_ui()

        # redirect stdout/stderr to terminal panel safely
        try:
            sys.stdout = StreamRedirector(self.terminal_panel.append_message)
            sys.stderr = StreamRedirector(self.terminal_panel.append_message)
        except Exception as e:
            print(f"Redirection failed: {e}")

        # connect signal
        self.voice_result.connect(self._on_voice_result)

#---------------------------------------------------#
#               win 11 blur effect                  #
#---------------------------------------------------#
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

#---------------------------------------------------#
#                    UI & Layout                    #
#---------------------------------------------------#
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

        # mic toggle
        self.voice_toggle_btn = QtWidgets.QPushButton("🎙️")
        self.voice_toggle_btn.setCheckable(True)
        self.voice_toggle_btn.clicked.connect(self._on_voice_toggle_clicked)
        self.voice_toggle_btn.setToolTip("Toggle Voice Recognition")
        self.voice_toggle_btn.setCursor(QtCore.Qt.PointingHandCursor)

        for btn in (self.minimize_btn, self.close_btn, settings_button, self.max_btn, self.voice_toggle_btn):
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
        self.close_btn.setStyleSheet("background-color: red; color: rgb(77, 255, 219); font-size: 18px; border-radius: 15px; border: none;")
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.close_btn.clicked.connect(self.close)
        self.max_btn.setToolTip("Fullscreen")

        titlebar.addWidget(settings_button)
        titlebar.addWidget(self.voice_toggle_btn)
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



        # wire terminal reference (command module expects it)
        import command
        command.terminal_widget_ref = self.terminal_panel

        # ---- FIND THE REAL INPUT WIDGET FROM TerminalChat ----
        self.chat_input = self._find_input_widget(self.terminal_panel)

        # ---- CREATE KEYBOARD once we have the input ----
        self.keyboard_panel = KeyboardWidget(target_input=self.chat_input)

        upper_layout.addWidget(self.system_panel)
        upper_layout.addWidget(self.terminal_panel)
        lower_layout.addWidget(self.keyboard_panel)
        main_layout.addLayout(upper_layout)
        main_layout.addLayout(lower_layout)

        central_widget.setLayout(main_layout)

#---------------------------------------------------#
#        Event Handlers  for window dragging        #
#---------------------------------------------------#
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

#---------------------------------------------------#
#                voice toggler handlers             #
#---------------------------------------------------#
    def _on_voice_toggle_clicked(self, checked):
        self.voice_toggle_btn.setEnabled(False)
        if checked:
            try:
                voice_atom.start_listening(self._voice_callback)
            except Exception as e:
                self.terminal_panel.append_message(f"⚠️ Failed to start listener: {e}")
                self.voice_toggle_btn.setChecked(False)
        else:
            voice_atom.stop_listening()
        self.voice_toggle_btn.setEnabled(True)

    def _voice_callback(self, text):
        try:
            self.voice_result.emit(text)
        except Exception:
            QtCore.QTimer.singleShot(0, lambda: self._on_voice_result(text))

    def _on_voice_result(self, text):
        voice_atom.stop_listening()
        self.voice_toggle_btn.setChecked(False)

        if not text:
            self.terminal_panel.append_message("⚠️ No speech detected.")
            return

        self.terminal_panel.append_message(f"User: {text}")

        # Exit commands
        if text.strip().lower() in ["exit", "quit", "shutdown", "stop", "goodbye"]:
            self.terminal_panel.append_message("🛑 Shutting down A.T.O.M.")
            threading.Thread(target=lambda: speak_response("Shutting down A.T.O.M. Goodbye!"), daemon=True).start()
            QtCore.QTimer.singleShot(0, self.close)
            return

        # First try hardwired commands
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

        # Otherwise fallback to LLM
        def do_llm():
            try:
                resp = get_response_from_atom(text)
                self.terminal_panel.append_message(f"🗨️ A.T.O.M: {resp}")
                threading.Thread(target=lambda: speak_response(resp), daemon=True).start()
            except Exception as e:
                self.terminal_panel.append_message(f"⚠️ LLM error: {e}")

        threading.Thread(target=do_llm, daemon=True).start()


#---------------------------------------------------#
#       Handle user input from Terminal widget       #
#---------------------------------------------------#
    def process_user_input(self, text: str):
        """
        Called when the user presses Enter in the terminal.
        Decides whether to run a hardwired command or query Ollama.
        """
        if not text.strip():
            return

        # Always echo user input
        self.terminal_panel.append_message(f"User: {text}")

        # Exit handling
        if text.strip().lower() in ["exit", "quit", "shutdown", "stop"]:
            self.terminal_panel.append_message("🛑 Exiting A.T.O.M.")
            self.close()
            return

        # First try hardcoded commands
        try:
            cmd_resp = handle_command(text)
        except Exception as e:
            cmd_resp = None
            self.terminal_panel.append_message(f"⚠️ Command handler error: {e}")

        if cmd_resp:
            self.terminal_panel.append_message(f"A.T.O.M: {cmd_resp}")
            try:
                threading.Thread(target=lambda: speak_response(cmd_resp), daemon=True).start()
            except Exception:
                pass
            return

        # Otherwise → fallback to Ollama / local engine
        def do_ai(q):
            try:
                resp = get_response_from_atom(q)
                QtCore.QTimer.singleShot(0, lambda: self.terminal_panel.append_message(f"🗨️ A.T.O.M:\n\n{resp}"))
                try:
                    speak_response(resp)
                except Exception:
                    pass
            except Exception as e:
                QtCore.QTimer.singleShot(0, lambda: self.terminal_panel.append_message(f"⚠️ LLM error: {e}"))

        threading.Thread(target=do_ai, args=(text,), daemon=True).start()


#---------------------------------------------------#
#         Custom window Fullscreen handler          #
#---------------------------------------------------#
    def toggle_maximize_restore(self):
        if self.isFullScreen():
            self.showNormal()
            self.max_btn.setText("🗖")
        else:
            self.showFullScreen()
            self.max_btn.setText("🗗")
            self.max_btn.setToolTip("Restore")

#---------------------------------------------------#
#        terminal input finder(By chat GPT)         #
#---------------------------------------------------#
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

#---------------------------------------------------#
#            Launcher splash + main ui              #
#---------------------------------------------------#
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Show splash screen
    splash = SplashScreen()
    splash.show()
    QApplication.processEvents()  # forces GUI update

    # Global reference for main window to avoid garbage collection
    main_window = None

    # Function to launch main UI in main thread
    def launch_main_ui():
        global main_window
        main_window = AtomUI()  # <-- Keep a reference to pervent gargage collection

        # redirect stdout/stderr to terminal panel
        sys.stdout = StreamRedirector(main_window.terminal_panel.append_message)
        sys.stderr = StreamRedirector(main_window.terminal_panel.append_message)

        main_window.show()
        splash.close()  # hide splash
        print(" A.T.O.M is online. Terminal ready.")

    # Thread-safe signal for launching UI
    class LauncherSignals(QtCore.QObject):
        done = QtCore.pyqtSignal()
    signals = LauncherSignals()
    signals.done.connect(launch_main_ui)

    # Thread for initializing Ollama (only splash updates here)
    def init_ollama():
        splash.update_status("Starting Ollama...")
        start_ollama(print_fn=splash.update_status)  # runs in this thread
        splash.update_status("Launching UI...")
        signals.done.emit()  # safely trigger UI in main thread

    threading.Thread(target=init_ollama, daemon=True).start()

    sys.exit(app.exec_())

