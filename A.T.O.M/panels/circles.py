from PyQt5.QtCore import Qt, QRectF, QVariantAnimation
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget
from PyQt5.QtSvg import QSvgRenderer
import psutil

class CircularProgress(QWidget):
    def __init__(self, value=0, max_value=100, label="", is_battery=False, parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.label = label
        self.is_battery = is_battery  # mark battery circle
        self._display_value = value
        self._arc_color = QColor(77, 255, 219)
        self._charging = False
        self._pulse_width = 10

        # SVG
        self.svg_renderer = QSvgRenderer()
        self.svg_path = None

        self.setMinimumSize(100, 100)
        self.font = QFont("Orbitron", 11, QFont.Bold)
        self.label_font = QFont("Orbitron", 10)

        # Value animation
        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self._on_animated_value_changed)
        self.animation.setDuration(400)

        # Color animation
        self.color_anim = QVariantAnimation(self)
        self.color_anim.valueChanged.connect(self._on_color_anim)
        self.color_anim.setDuration(600)

        # Pulse animation (charging)
        self.pulse_anim = QVariantAnimation(self)
        self.pulse_anim.setStartValue(10)
        self.pulse_anim.setEndValue(15)
        self.pulse_anim.setDuration(1000)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.valueChanged.connect(self._on_pulse_anim)

        self.setStyleSheet("background: transparent;")

    # ---------------- VALUE ---------------- #
    def setValue(self, val):
        val = max(0, min(val, self.max_value))
        if val != self.value:
            self.animation.stop()
            self.animation.setStartValue(self._display_value)
            self.animation.setEndValue(val)
            self.animation.start()
            self.value = val

    def _on_animated_value_changed(self, val):
        self._display_value = val
        self.update_arc_color()
        self.update()

    # ---------------- COLOR ---------------- #
    def _on_color_anim(self, val: QColor):
        self._arc_color = val
        self.update()

    def set_arc_color(self, color: QColor):
        if color != self._arc_color:
            self.color_anim.stop()
            self.color_anim.setStartValue(self._arc_color)
            self.color_anim.setEndValue(color)
            self.color_anim.start()

    # ---------------- PULSE ---------------- #
    def _on_pulse_anim(self, val):
        self._pulse_width = val
        self.update()

    def start_pulse(self):
        if not self.pulse_anim.state():
            self.pulse_anim.start()

    def stop_pulse(self):
        if self.pulse_anim.state():
            self.pulse_anim.stop()
            self._pulse_width = 10

    # ---------------- SVG ---------------- #
    def set_svg_icon(self, filepath):
        self.svg_path = filepath
        self.svg_renderer.load(filepath)
        # Update charging pulse and color immediately
        if self.is_battery:
            self.update_arc_color()
        self.update()

    # ---------------- COLOR LOGIC ---------------- #
    def update_arc_color(self):
        percent = (self._display_value / self.max_value) * 100 if self.max_value else 0
        new_color = QColor(77, 255, 219)
        charging = False

        if not self.is_battery:
            # CPU / RAM thresholds
            if percent > 90:
                new_color = QColor(255, 69, 0)
            elif percent > 75:
                new_color = QColor(255, 165, 0)
        else:
            # Battery logic
            battery = psutil.sensors_battery()
            if battery and battery.power_plugged:
                new_color = QColor(0, 255, 0)
                charging = True
            else:
                if percent < 15:
                    new_color = QColor(255, 0, 0)
                elif percent < 30:
                    new_color = QColor(255, 165, 0)
                else:
                    new_color = QColor(77, 255, 219)

        # Animate color
        self.set_arc_color(new_color)

        # Start/stop pulse
        if self.is_battery:
            if charging and not self._charging:
                self._charging = True
                self.start_pulse()
            elif not charging and self._charging:
                self._charging = False
                self.stop_pulse()

    # ---------------- PAINT EVENT ---------------- #
    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        margin = 8
        rect = QRectF(margin, margin, width - 2 * margin, height - 2 * margin)
        center = rect.center()
        center_y = center.y()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Neon glow for charging battery
        if self.label == "BAT" and self._charging:
            glow_radius = self._pulse_width * 2
            for i in range(glow_radius, 0, -2):
                alpha = int(150 * (i / glow_radius))
                glow_color = QColor(self._arc_color.red(), self._arc_color.green(), self._arc_color.blue(), alpha)
                pen = QPen(glow_color, i)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                angle = int(360 * (self._display_value / self.max_value)) if self.max_value else 0
                painter.drawArc(rect, -90 * 16, -angle * 16)

        # Main arc
        pen_width = self._pulse_width if self._charging else 10
        glow_pen = QPen(self._arc_color, pen_width)
        glow_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(glow_pen)
        angle = int(360 * (self._display_value / self.max_value)) if self.max_value else 0
        painter.drawArc(rect, -90 * 16, -angle * 16)

        # Percentage text
        painter.setFont(self.font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, f"{int(self._display_value)}%")

        # Label
        painter.setFont(self.label_font)
        painter.setPen(QColor(77, 255, 219))
        label_rect = QRectF(0, center_y + 20, width, 20)
        painter.drawText(label_rect, Qt.AlignCenter, self.label)

        # SVG Icon Render settings
        if self.svg_path:
            size = min(width, height) * 0.25 # SVG icon scale
            x_offset = 0 # adjust icon position horizontally 
            y_offset = 27 # adjust icon position vertically
            icon_rect = QRectF(
                (width - size)/2 + x_offset,
                (height - size)/2 + y_offset,
                size,
                size
            )
            self.svg_renderer.render(painter, icon_rect)

        painter.end()
