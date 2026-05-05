# A.T.O.M/panels/circles.py
from PyQt5.QtCore import Qt, QRectF, QVariantAnimation, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget
from PyQt5.QtSvg import QSvgRenderer
import psutil

from theme import theme_manager


class CircularProgress(QWidget):
    # ------------------------------------------------------------------
    # Thread-safe update signal.
    #
    # SystemPanel's stats-polling loop runs on a background thread and
    # calls setValue() on these widgets directly.  Qt widget methods
    # (including anything that calls update() or starts a QAnimation)
    # must only run on the GUI thread.  Calling them from a worker
    # thread corrupts Qt's rendering state and causes a Windows access
    # violation in whatever C code is running concurrently — in
    # practice this was ctransformers mid-inference.
    #
    # Fix: background threads should emit request_value instead of
    # calling setValue() directly.  Qt's cross-thread signal delivery
    # marshals the call onto the GUI thread via the event loop.
    #
    #   Safe from any thread:  widget.request_value.emit(42)
    #   Safe from GUI thread:  widget.setValue(42)   (unchanged)
    # ------------------------------------------------------------------
    request_value = pyqtSignal(int)

    def __init__(self, value=0, max_value=100, label="", is_battery=False, parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.label = label
        self.is_battery = is_battery
        self._display_value = float(value)
        self._theme_color = QColor(theme_manager.color)
        self._arc_color = QColor(theme_manager.color)
        self._charging = False
        self._pulse_width = 10
        # Wire signal → setValue so cross-thread emissions land on GUI thread
        self.request_value.connect(self.setValue)

        self._cached_battery_plugged = False
        if self.is_battery:
            self._battery_cache_timer = QTimer(self)
            self._battery_cache_timer.timeout.connect(self._refresh_battery_cache)
            self._battery_cache_timer.start(2000)
            self._refresh_battery_cache()

        self.svg_renderer = QSvgRenderer()
        self.svg_path = None

        self.setMinimumSize(100, 100)
        self.font = QFont("Orbitron", 11, QFont.Bold)
        self.label_font = QFont("Orbitron", 10)

        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self._on_animated_value_changed)
        self.animation.setDuration(400)

        self.color_anim = QVariantAnimation(self)
        self.color_anim.valueChanged.connect(self._on_color_anim)
        self.color_anim.setDuration(600)

        self.pulse_anim = QVariantAnimation(self)
        self.pulse_anim.setStartValue(6)
        self.pulse_anim.setEndValue(18)
        self.pulse_anim.setDuration(800)
        self.pulse_anim.setLoopCount(-1)
        from PyQt5.QtCore import QEasingCurve
        self.pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse_anim.valueChanged.connect(self._on_pulse_anim)

        self.setStyleSheet("background: transparent;")

    def set_theme_color(self, hex_color: str):
        self._theme_color = QColor(hex_color)
        self.update_arc_color()

    def _refresh_battery_cache(self):
        battery = psutil.sensors_battery()
        self._cached_battery_plugged = bool(battery and battery.power_plugged)
        self.update_arc_color()  # re-check charging state even when value hasn't changed

    def setValue(self, val: int):
        val = max(0, min(val, self.max_value))
        if val != self.value:
            self.animation.stop()
            self.animation.setStartValue(self._display_value)
            self.animation.setEndValue(float(val))
            self.animation.start()
            self.value = val

    def _on_animated_value_changed(self, val):
        self._display_value = val
        self.update_arc_color()
        self.update()

    def _on_color_anim(self, val: QColor):
        self._arc_color = val
        self.update()

    def set_arc_color(self, color: QColor):
        if color != self._arc_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(QColor(self._arc_color))
            self.color_anim.setEndValue(color)
            self.color_anim.start()

    def _on_pulse_anim(self, val):
        self._pulse_width = val
        self.update()

    def start_pulse(self):
        if self.pulse_anim.state() != QVariantAnimation.Running:
            self.pulse_anim.start()

    def stop_pulse(self):
        if self.pulse_anim.state() == QVariantAnimation.Running:
            self.pulse_anim.stop()
        self._pulse_width = 6
        self.update()

    def set_svg_icon(self, filepath: str):
        self.svg_path = filepath
        self.svg_renderer.load(filepath)
        if self.is_battery:
            self.update_arc_color()
        self.update()

    def update_arc_color(self):
        percent = (self._display_value / self.max_value * 100) if self.max_value else 0
        new_color = QColor(self._theme_color)
        charging = False

        if not self.is_battery:
            if percent > 90:
                new_color = QColor(255, 69, 0)
            elif percent > 75:
                new_color = QColor(255, 165, 0)
        else:
            charging = self._cached_battery_plugged
            if charging:
                new_color = QColor(0, 255, 0)
            elif percent < 15:
                new_color = QColor(255, 0, 0)
            elif percent < 30:
                new_color = QColor(255, 165, 0)

        self.set_arc_color(new_color)

        if self.is_battery:
            if charging and not self._charging:
                self._charging = True
                self.start_pulse()
            elif not charging and self._charging:
                self._charging = False
                self.stop_pulse()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        margin = 8
        rect = QRectF(margin, margin, w - 2 * margin, h - 2 * margin)
        center_y = rect.center().y()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_battery and self._charging:
            angle = int(360 * self._display_value / self.max_value) if self.max_value else 0
            cr, cg, cb = self._arc_color.red(), self._arc_color.green(), self._arc_color.blue()
            # Draw 3 glow layers — outer to inner, decreasing alpha
            for width, alpha in [(self._pulse_width * 3, 40),
                                  (self._pulse_width * 2, 80),
                                  (self._pulse_width,     160)]:
                gp = QPen(QColor(cr, cg, cb, alpha), width)
                gp.setCapStyle(Qt.RoundCap)
                painter.setPen(gp)
                painter.drawArc(rect, -90 * 16, -angle * 16)

        # Subtle background track
        tr, tg, tb = self._arc_color.red(), self._arc_color.green(), self._arc_color.blue()
        track = QPen(QColor(tr, tg, tb, 30), 10)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)

        pen_w = self._pulse_width if self._charging else 10
        main_pen = QPen(self._arc_color, pen_w)
        main_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(main_pen)
        angle = int(360 * self._display_value / self.max_value) if self.max_value else 0
        painter.drawArc(rect, -90 * 16, -angle * 16)

        painter.setFont(self.font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, f"{int(self._display_value)}%")

        painter.setFont(self.label_font)
        painter.setPen(self._arc_color)
        label_rect = QRectF(0, center_y + 20, w, 20)
        painter.drawText(label_rect, Qt.AlignCenter, self.label)

        if self.svg_path:
            size = min(w, h) * 0.25
            icon_rect = QRectF((w - size) / 2, (h - size) / 2 + 27, size, size)
            self.svg_renderer.render(painter, icon_rect)

        painter.end()