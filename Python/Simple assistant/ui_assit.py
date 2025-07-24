import sys
import ctypes
import speech_recognition as sr
import pyttsx3
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from simple_assistant import VoiceAssistantApp

# Initialization
engine = pyttsx3.init()

#Voice properties
voices = engine.getProperty('voices')  
engine.setProperty('voice', voices[1].id)  # Change to voice to male or female (0 for male/1 for female)
engine.setProperty('rate', 190)  #  speaking rate
engine.setProperty('volume', 0.7)  #  0.0 (mute)  1.0 (max)

# GUI customizations

class VoiceAssistantApp(QtWidgets.QMainWindow, VoiceAssistantApp):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Assistant")
        self.setGeometry(100, 100, 500, 400)
        #window flags for frameless and translucent background
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowMinimizeButtonHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.2); color: antiquewhite;border-radius: 5px;border: 1px solid rgba(255, 255, 255, 0.2);")
        self.apply_blur_effect()
        self.offset = None  # <-- Required for dragging
        self.init_ui()

        # Enable dragging from anywhere
        self.installEventFilter(self)
# ----- Apply blur effect to the window (Form chat GPT) -----#
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
        accent.AccentState = 3  # ACCENT_ENABLE_BLURBEHIND
        accent.GradientColor = 0x99000000

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

#--- Main UI initialization ---#
    def init_ui(self):
        self.central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self.central.setLayout(layout)

        # Title bar (custom title bar and buttons)
        titlebar = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("Voice Assistant")
        title_label.setStyleSheet("background-color: transparent;border: none; font-size: 15px; color: antiquewhite;")
        titlebar.addWidget(title_label)
        titlebar.addStretch()
        #--minimize and close buttons
        minimize_btn = QtWidgets.QPushButton("—")
        close_btn = QtWidgets.QPushButton("✕")
        # Settings button
        settings_button = QtWidgets.QPushButton("⚙️")
        settings_button.clicked.connect(self.toggle_settings_panel)
        settings_button.setToolTip("Open Settings Panel")
        settings_button.setCursor(QtCore.Qt.PointingHandCursor)

        #styles for buttons
        for btn in (minimize_btn, close_btn , settings_button):
            btn.setFixedSize(30, 30)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color:antiquewhite; font-size: 18px; border: none; border-radius: 15px;")
        close_btn.setStyleSheet("background-color: red; color:antiquewhite; font-size: 18px; border-radius: 15px; border: none;")

        minimize_btn.clicked.connect(self.showMinimized)
        minimize_btn.setToolTip("Minimize")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.close)
        titlebar.addWidget(settings_button)
        titlebar.addWidget(minimize_btn)
        titlebar.addWidget(close_btn)
        layout.addLayout(titlebar)

        # ------------------------------------- Slide-out Settings Panel --------------------------------------- #
        self.settings_panel = QtWidgets.QFrame()
        self.settings_panel.setFixedWidth(0)
        self.settings_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: antiquewhite;
                font-size: 14px;
                padding: 12px;
            }
        """)
        self.settings_layout = QtWidgets.QVBoxLayout(self.settings_panel)

# ----- VOICE SELECTION  -----#
        voice_row = QtWidgets.QHBoxLayout()
        self.voice_label = QtWidgets.QLabel("Voice: Female")
        self.voice_label.setStyleSheet("color: antiquewhite; font-size: 14px;")
        self.voice_combo = QtWidgets.QComboBox()
        self.voice_combo.addItems(["Male", "Female"])
        self.voice_combo.setCursor(QtCore.Qt.PointingHandCursor)
        self.voice_combo.setStyleSheet("""
                QComboBox {
                        background-color: rgba(255, 255, 255, 0.1);
                        color: antiquewhite;
                        padding: 6px;
                        border: 1px solid rgba(255, 255, 255, 0.2);
                        border-radius: 8px;
                        }
                QComboBox::drop-down {
                        border: none;
                        background: transparent;
                        
                        }
                QComboBox::down-arrow {
                        image: url(Python/Simple assistant/arrow_drop_down.png);
                        width: 12px;
                        height: 12px;
                        }
                QComboBox QAbstractItemView {
                        background-color: rgba(40, 40, 40, 0.95);
                        color: antiquewhite;
                        border-radius: 8px;
                        selection-background-color: rgba(255, 255, 255, 0.2);
                        }
""")
        self.voice_combo.currentIndexChanged.connect(self.update_voice_label)
        voice_row.addWidget(self.voice_label)
        voice_row.addWidget(self.voice_combo)
        self.settings_layout.addLayout(voice_row)

# ----- SPEECH RATE SLIDER  -----#
        self.rate_label = QtWidgets.QLabel(f"Speech Rate: {engine.getProperty('rate')}")
        self.rate_label.setStyleSheet("color: antiquewhite;")
        self.settings_layout.addWidget(self.rate_label)

        self.rate_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.rate_slider.setMinimum(100)
        self.rate_slider.setMaximum(300)
        self.rate_slider.setValue(engine.getProperty("rate"))
        self.rate_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                        height: 8px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 4px;
                        }
                QSlider::handle:horizontal {
                        background: rgba(255, 255, 255, 0.9);
                        border: 1px solid rgba(255, 255, 255, 0.4);
                        width: 18px;
                        margin: -5px 0;
                        border-radius: 9px;
                        }
                QSlider::handle:horizontal:hover {
                        background: rgba(255, 255, 255, 0.7);
                        }
                QSlider::sub-page:horizontal {
                        background: rgba(250, 235, 215, 0.4);
                        border-radius: 4px;
                        }
""")
        self.rate_slider.valueChanged.connect(self.update_rate_label)
        self.settings_layout.addWidget(self.rate_slider)

# ----- VOLUME SLIDER WITH VALUE -----
        initial_volume = int(engine.getProperty("volume") * 100)
        self.volume_label = QtWidgets.QLabel(f"Volume: {initial_volume}%")
        self.volume_label.setStyleSheet("color: antiquewhite;")
        self.settings_layout.addWidget(self.volume_label)

        self.volume_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(1)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(initial_volume)
        self.volume_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 8px;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    }
                QSlider::handle:horizontal {
                    background: rgba(255, 255, 255, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.4);
                    width: 18px;
                    margin: -5px 0;
                    border-radius: 9px;
                    }
                QSlider::handle:horizontal:hover {
                    background: rgba(255, 255, 255, 0.7);
                    }
                QSlider::sub-page:horizontal {
                    background: rgba(250, 235, 215, 0.4);
                    border-radius: 4px;
                    }
""")
        self.volume_slider.valueChanged.connect(self.update_volume_label)
        self.settings_layout.addWidget(self.volume_slider)
        self.close_settings_btn = QtWidgets.QPushButton("Close Settings Panel")
        self.close_settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_settings_btn.setStyleSheet(""" 
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    color: antiquewhite;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 12px;
                    }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.2);
                    }
        """)
        self.close_settings_btn.setToolTip("Close Settings Panel")
        self.close_settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_settings_btn.clicked.connect(self.hide_settings_panel)
        self.settings_layout.addWidget(self.close_settings_btn)

        # Main container layout
        self.main_wrapper = QtWidgets.QHBoxLayout()
        self.main_wrapper.addWidget(self.central)
        self.main_wrapper.addWidget(self.settings_panel)

        wrapper_container = QtWidgets.QWidget()
        wrapper_container.setLayout(self.main_wrapper)
        self.setCentralWidget(wrapper_container)

        # Label
        self.response_label = QtWidgets.QLabel("Click '🎙️' and Say Something")
        self.response_label.setAlignment(QtCore.Qt.AlignCenter)
        self.response_label.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    color: rgba(250, 235, 215, 1);
                    padding: 10px;
                    background-color: rgba(255, 255, 255, 0.15);
                    border-radius: 10px;
                    }
        """)
        layout.addWidget(self.response_label)

        # Text area
        self.text_area = QtWidgets.QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlaceholderText("Response History will be shown here...")
        self.text_area.setStyleSheet("font-size: 14px; font-weight:bold; color: rgba(250, 235, 215, 1); background-color:  rgba(255, 255, 255, 0.1); border-radius: 12px; padding:10px; border:1px solid rgba(255, 255, 255, 0.2);")
        layout.addWidget(self.text_area)

        # Microphone Button
        self.start_button = QtWidgets.QPushButton("🎙️")
        self.start_button.setToolTip("Click and Speak")
        self.start_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.start_button.setStyleSheet("""
                QPushButton {
                    font-size: 24px;
                    font-weight: bold;
                    color: rgba(250, 235, 215, 1);
                    background-color: rgba(255, 255, 255, 0.08);
                    border-radius: 15px;
                    padding: 10px 20px;
                    }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.2);
                    }
        """)
        self.start_button.clicked.connect(self.listen_and_respond)
        layout.addWidget(self.start_button, alignment=QtCore.Qt.AlignCenter)

        self.main_wrapper.addWidget(self.central)

# drag functionality for trasparent window
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.offset = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.offset = None

    # ----- Settings Panel Slide Logic -----#
    def toggle_settings_panel(self):
        width = self.settings_panel.width()
        new_width = 300 if width == 0 else 0
        self.animate_panel(self.settings_panel, width, new_width)

    def hide_settings_panel(self):
        self.animate_panel(self.settings_panel, self.settings_panel.width(), 0)

#----- Animation for Settings Panel -----#
    def animate_panel(self, target, start, end):
        self.animation = QtCore.QPropertyAnimation(target, b"minimumWidth")
        self.animation.setDuration(400)
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        self.animation.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceAssistantApp()
    window.show()
    sys.exit(app.exec_())