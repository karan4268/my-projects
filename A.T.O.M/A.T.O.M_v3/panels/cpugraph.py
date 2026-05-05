# A.T.O.M/panels/cpugraph.py
import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, QRect, QEasingCurve
from PyQt5.QtGui import QFont, QColor
import pyqtgraph as pg
from pyqtgraph import TextItem
import psutil

from theme import theme_manager


def _apply_blur_windows(hwnd):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        class AP(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]
        class WD(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(AP)),
                        ("SizeOfData", ctypes.c_size_t)]
        accent = AP(); accent.AccentState = 3; accent.GradientColor = 0x99000000
        data = WD(); data.Attribute = 19; data.Data = ctypes.pointer(accent); data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass


def _to_rgb(hex_color):
    c = QColor(hex_color)
    return c.red(), c.green(), c.blue()


class Waveform(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(540); self.setFixedHeight(180)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.move(-600, 100)
        self.current_type = None

        # ✅ NEW: animation state guard
        self.is_animating = False

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        layout = QVBoxLayout(self)
        self.graph_layout = QHBoxLayout()
        layout.addLayout(self.graph_layout)

        r, g, b = _to_rgb(theme_manager.color)

        self.cpu_plot = pg.PlotWidget()
        self.cpu_plot.setFixedSize(400, 150); self.cpu_plot.setYRange(0, 100)
        self.cpu_plot.setBackground("transparent"); self.cpu_plot.hideAxis('bottom')
        self.cpu_plot.hideAxis('left'); self.cpu_plot.setMouseEnabled(x=False, y=False)
        self.cpu_plot.hideButtons(); self.cpu_plot.setMenuEnabled(False)
        self.cpu_plot.getViewBox().setMouseEnabled(x=False, y=False); self.cpu_plot.setAntialiasing(True)
        self.cpu_label = TextItem(text="CPU Activity", color=(r,g,b), anchor=(0.5,1.0))
        self.cpu_label.setFont(QFont("Orbitron", 8, QFont.Bold))
        self.cpu_plot.addItem(self.cpu_label); self.cpu_label.setPos(20, 90)
        self.cpu_curve = self.cpu_plot.plot(pen=pg.mkPen((r,g,b), width=2))
        self.cpu_data = [0]*100

        self.ram_plot = pg.PlotWidget()
        self.ram_plot.setFixedSize(400, 150); self.ram_plot.setYRange(0, 100)
        self.ram_plot.setBackground("transparent"); self.ram_plot.hideAxis('bottom')
        self.ram_plot.hideAxis('left'); self.ram_plot.setMouseEnabled(x=False, y=False)
        self.ram_plot.hideButtons(); self.ram_plot.setMenuEnabled(False)
        self.ram_plot.getViewBox().setMouseEnabled(x=False, y=False); self.ram_plot.setAntialiasing(True)
        self.ram_label = TextItem(text="RAM Usage", color=(r,g,b), anchor=(0.5,1.0))
        self.ram_label.setFont(QFont("Orbitron", 8, QFont.Bold))
        self.ram_plot.addItem(self.ram_label); self.ram_label.setPos(20, 90)
        self.ram_curve = self.ram_plot.plot(pen=pg.mkPen((r,g,b), width=2))
        self.ram_data = [0]*100

        self.graph_layout.addWidget(self.cpu_plot); self.graph_layout.addWidget(self.ram_plot)
        self.cpu_plot.hide(); self.ram_plot.hide()

        self.timer = QTimer(self); self.timer.timeout.connect(self.update_stats); self.timer.start(100)
        self.auto_hide_timer = QTimer(self); self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide_slide)

        self.slide_anim = QPropertyAnimation(self, b"geometry")
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.fade_anim.finished.connect(self._on_fade_finished)

    def _on_fade_finished(self):
        # Only hide after fade-out
        if self.fade_anim.endValue() == 0.0:
            self.setVisible(False)
        self.is_animating = False

    def apply_theme(self, color):
        r, g, b = _to_rgb(color)
        self.cpu_curve.setPen(pg.mkPen((r,g,b), width=2))
        self.ram_curve.setPen(pg.mkPen((r,g,b), width=2))
        self.cpu_label.setColor((r,g,b))
        self.ram_label.setColor((r,g,b))

    def update_stats(self):
        cpu = psutil.cpu_percent(); ram = psutil.virtual_memory().percent
        self.cpu_data = self.cpu_data[1:] + [cpu]; self.ram_data = self.ram_data[1:] + [ram]
        self.cpu_curve.setData(self.cpu_data); self.ram_curve.setData(self.ram_data)

    def toggle_waveform(self, type_):
        if self.is_animating:
            return

        if self.current_type == type_ and self.isVisible():
            self.hide_slide()
            return

        self.cpu_plot.hide(); self.ram_plot.hide()

        if type_ == 'cpu':
            self.cpu_plot.show()
        elif type_ == 'ram':
            self.ram_plot.show()

        self.current_type = type_
        self.show_slide()

    def show_slide(self):
        if self.is_animating:
            return

        self.is_animating = True

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setVisible(True)
        self.show()

        _apply_blur_windows(int(self.winId()))

        self.slide_anim.stop()
        self.fade_anim.stop()

        parent = self.parent()
        if parent:
            g = parent.geometry()
            start = QRect(g.x()-self.width(), g.y()+400, self.width(), self.height())
            end   = QRect(g.x()+30,           g.y()+400, self.width(), self.height())
        else:
            start = QRect(-600, 400, self.width(), self.height())
            end   = QRect(30,   400, self.width(), self.height())

        self.slide_anim.setDuration(500)
        self.slide_anim.setStartValue(start)
        self.slide_anim.setEndValue(end)
        self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.slide_anim.start()

        self.raise_()

        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        self.auto_hide_timer.stop()
        self.auto_hide_timer.start(5000)

    def hide_slide(self):
        if self.is_animating:
            return

        self.is_animating = True

        self.auto_hide_timer.stop()
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