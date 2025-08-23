
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsOpacityEffect
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QRect, QEasingCurve
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication 
import pyqtgraph as pg
import psutil
from pyqtgraph import TextItem
import ctypes

class SlideOutWaveform(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

class Waveform(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedWidth(540)
        self.setFixedHeight(180)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags( Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.move(-600, 100)  # initially off screen
        self.setStyleSheet("border: 5px rgba(77, 255, 219, 0.5)")

        self.current_type = None  # Track what is currently shown (CPU or RAM)
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)

        # Layouts
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.graph_layout = QHBoxLayout()
        self.layout.addLayout(self.graph_layout)

        # Fonts
        font = QFont("Orbitron", 10)


# ---------------- CPU Graph ---------------- #
        self.cpu_plot = pg.PlotWidget()
        self.cpu_plot.setFixedSize(400, 150)
        self.cpu_plot.setYRange(0, 100)
        self.cpu_plot.setBackground("transparent")
        self.cpu_plot.hideAxis('bottom')
        self.cpu_plot.hideAxis('left')
        self.cpu_plot.setMouseEnabled(x=False, y=False)
        self.cpu_plot.hideButtons()
        self.cpu_plot.setMenuEnabled(False)
        self.cpu_plot.getViewBox().setMouseEnabled(x=False, y=False)
        self.cpu_plot.setAntialiasing(True)

        self.cpu_label = TextItem(text="CPU Activity", color=(77, 255, 219), anchor=(0.5, 1.0))
        self.cpu_label.setFont(QFont("Orbitron", 8, QFont.Bold))
        self.cpu_plot.addItem(self.cpu_label)
        self.cpu_label.setPos(20, 90)

        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen((77, 255, 219), width=2))
        self.cpu_data = [0] * 100


# ---------------- RAM Graph ---------------- #
        self.ram_plot = pg.PlotWidget()
        self.ram_plot.setFixedSize(400, 150)
        self.ram_plot.setYRange(0, 100)
        self.ram_plot.setBackground("transparent")
        self.ram_plot.hideAxis('bottom')
        self.ram_plot.hideAxis('left')
        self.ram_plot.setMouseEnabled(x=False, y=False)
        self.ram_plot.hideButtons()
        self.ram_plot.setMenuEnabled(False)
        self.ram_plot.getViewBox().setMouseEnabled(x=False, y=False)
        self.ram_plot.setAntialiasing(True)

        self.ram_label = TextItem(text="RAM Usage", color=(77, 255, 219), anchor=(0.5, 1.0))
        self.ram_label.setFont(QFont("Orbitron", 8, QFont.Bold))
        self.ram_plot.addItem(self.ram_label)
        self.ram_label.setPos(20, 90)

        self.ram_curve = self.ram_plot.plot(pen=pg.mkPen((77, 255, 219), width=2))
        self.ram_data = [0] * 100


        # Add both but keep hidden initially
        self.graph_layout.addWidget(self.cpu_plot)
        self.graph_layout.addWidget(self.ram_plot)
        self.cpu_plot.hide()
        self.ram_plot.hide()

        # Timer to update stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(100)

        # Auto-hide timer
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide_slide)

        # Slide animation
        self.slide_anim = QPropertyAnimation(self, b"geometry")
        self.fade_anim = QPropertyAnimation(self.opacity, b"opacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)

    def update_stats(self):
        cpu_percent = psutil.cpu_percent()
        ram_percent = psutil.virtual_memory().percent

        self.cpu_data = self.cpu_data[1:] + [cpu_percent]
        self.ram_data = self.ram_data[1:] + [ram_percent]

        self.cpu_curve.setData(self.cpu_data)
        self.ram_curve.setData(self.ram_data)

    def toggle_waveform(self, type_):
        if self.current_type == type_ and self.isVisible():
            self.hide_slide()
            return

        self.cpu_plot.hide()
        self.ram_plot.hide()

        if type_ == 'cpu':
            self.cpu_plot.show()
        elif type_ == 'ram':
            self.ram_plot.show()

        self.current_type = type_
        self.show_slide()

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

    def show_slide(self):
        self.setVisible(True)
        
        # Refresh window flags (important for fullscreen)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.show()  # MUST call after setting flags

        self.apply_blur_effect()

        # Start slide animation
        self.slide_anim.stop()
        self.fade_anim.stop()

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        y_offset = 100  # or adjust depending on design

        self.slide_anim.setDuration(500)
        main_geom = self.parent().geometry()
        self.slide_anim.setStartValue(QRect(main_geom.x() - self.width(), main_geom.y() + 400, self.width(), self.height())) 
        # postion based on circular progress bar
        self.slide_anim.setEndValue(QRect(main_geom.x() + 30, main_geom.y() + 400, self.width(), self.height()))

        self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.slide_anim.start()
        self.raise_()

        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        self.auto_hide_timer.start(5000)


    def hide_slide(self):
        self.slide_anim.stop()

        self.fade_anim.stop()

        self.slide_anim.setDuration(500)
        self.slide_anim.setStartValue(QRect(self.x(), self.y(), self.width(), self.height()))
        self.slide_anim.setEndValue(QRect(-600, self.y(), self.width(), self.height()))
        self.slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self.slide_anim.start()

        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()
