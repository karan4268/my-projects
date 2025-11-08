
from PyQt5.QtCore import Qt, QRectF, QVariantAnimation
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget


class CircularProgress(QWidget):
    def __init__(self, value=0, max_value=100, label="",parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.label = label
        self._display_value = value

        self.setMinimumSize(100, 100)
        self.font = QFont("Orbitron", 11, QFont.Bold)
        self.label_font = QFont("Orbitron", 10)

        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self._on_animated_value_changed)
        self.animation.setDuration(400)

        self.setStyleSheet("background: transparent;")

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
        self.update()

    def paintEvent(self, event):
        width = self.width()
        height = self.height()
        margin = 8
        radius = min(width, height) // 2 - margin

        rect = QRectF(margin, margin, width - 2 * margin, height - 2 * margin)
        center_x = rect.center().x()
        center_y = rect.center().y()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background Circle
        background_pen = QPen(QColor(20, 20, 30), 8)
        painter.setPen(background_pen)
        painter.drawEllipse(rect)

        # Determine arc color dynamically
        if self.label == "🔋":
            # Battery-specific thresholds
            if self._display_value < 15:
                arc_color = QColor(255, 0, 0)      # Red
            elif self._display_value < 30:
                arc_color = QColor(255, 165, 0)    # Orange
            else:
                arc_color = QColor(77, 255, 219)   # Cyan
        elif self.label == "🔌":
            arc_color = QColor(0, 255, 0)          # Green when charging
        else:
            # Default behavior for CPU/RAM
            percent = (self._display_value / self.max_value) * 100 if self.max_value else 0
            if percent > 90:
                arc_color = QColor(255, 69, 0)    # Red
            elif percent > 75:
                arc_color = QColor(255, 165, 0)  # Orange
            else:
                arc_color = QColor(77, 255, 219)  # Teal

        # Draw neon arc
        glow_pen = QPen(arc_color, 10)
        glow_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(glow_pen)

        angle = int(360 * (self._display_value / self.max_value)) if self.max_value else 0
        painter.drawArc(rect, -90 * 16, -angle * 16)

        # Percentage text
        painter.setFont(self.font)
        painter.setPen(QColor(255, 255, 255))
        percent_text = f"{int(self._display_value)}%"
        painter.drawText(self.rect(), Qt.AlignCenter, percent_text)

        # Label
        painter.setFont(self.label_font)
        painter.setPen(QColor(77, 255, 219))
        label_rect = QRectF(0, center_y + 20, width, 20)
        painter.drawText(label_rect, Qt.AlignCenter, self.label)

        painter.end()

