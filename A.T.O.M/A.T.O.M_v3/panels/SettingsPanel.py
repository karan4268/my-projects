# A.T.O.M/panels/SettingsPanel.py
"""
Settings Panel — floating window for global theme configuration.
Opens from the ⚙️ button in the titlebar.
"""
import ctypes
import sys

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QColorDialog, QGraphicsDropShadowEffect, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QSlider
import tts_atom

from theme import theme_manager, PRESETS, themed_border_style


_FONT = QFont("Orbitron", 10)
_FONT_SM = QFont("Orbitron", 8)


# ── Color swatch button ───────────────────────────────────────────────────── #
class SwatchButton(QPushButton):
    """A circular color swatch that acts as a preset selector."""

    def __init__(self, color: str, label: str = "", parent=None):
        super().__init__(parent)
        self.color = color
        self.label = label
        self.selected = False
        self.setFixedSize(44, 44)
        self.setToolTip(f"{label}  {color}")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background:transparent; border:none;")


    def set_selected(self, val: bool):
        self.selected = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        c = QColor(self.color)
        cx, cy, r = self.width() // 2, self.height() // 2, 16

        # Outer glow ring if selected
        if self.selected:
            glow_pen = QPen(c, 3)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - r - 4, cy - r - 4, (r + 4) * 2, (r + 4) * 2)

        # Fill
        painter.setBrush(QBrush(c))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        painter.end()

# ── Preview bar ───────────────────────────────────────────────────────────── #
class PreviewBar(QWidget):
    """Live preview strip showing what the selected color looks like."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = theme_manager.color
        self.setFixedHeight(56)
        self.setMinimumWidth(260)

    def set_color(self, hex_color: str):
        self.color = hex_color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        c = QColor(self.color)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(10, 10, 10))

        # Arc segment preview
        pen = QPen(c, 8, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(8, 8, 40, 40, -90 * 16, -270 * 16)

        # Text samples
        font_big = QFont("Orbitron", 12, QFont.Bold)
        font_sm = QFont("Orbitron", 8)
        painter.setPen(QPen(c))
        painter.setFont(font_big)
        painter.drawText(60, 26, "A.T.O.M")
        painter.setFont(font_sm)
        painter.setPen(QPen(QColor(255, 255, 255, 160)))
        painter.drawText(60, 42, f"Theme preview  •  {self.color}")

        # Border line
        painter.setPen(QPen(c, 1))
        painter.drawLine(0, h - 1, w, h - 1)

        painter.end()


# ── Main Settings Panel ───────────────────────────────────────────────────── #
class SettingsPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_hiding = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self._drag_offset = None
        self._pending_color = theme_manager.color
        self._swatch_buttons: dict[str, SwatchButton] = {}

        self._build_ui()
        self._apply_blur()

        # Fade-in animation
        from PyQt5.QtWidgets import QGraphicsOpacityEffect
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity")
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._on_fade_finished)

    # ── UI construction ───────────────────────────────────────────────────── #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        # ── Title bar ──
        title_row = QHBoxLayout()
        lbl = QLabel("⚙  Settings")
        lbl.setFont(QFont("Orbitron", 13, QFont.Bold))
        lbl.setStyleSheet(f"color: {theme_manager.color}; border:none; background:transparent;")
        self._title_label = lbl

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background:rgba(255,60,60,160); border-radius:13px;"
            "color:white; font-size:12px; border:none;}"
            "QPushButton:hover { background:rgba(255,60,60,220); }"
        )
        close_btn.clicked.connect(self.hide_animated)

        title_row.addWidget(lbl)
        title_row.addStretch()
        title_row.addWidget(close_btn)
        root.addLayout(title_row)

        root.addWidget(self._divider())

        # ── Section: Theme Color ──
        root.addWidget(self._section_label("THEME COLOR"))

        # Swatches grid
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(6)
        for name, hex_color in PRESETS.items():
            btn = SwatchButton(hex_color, name)
            btn.clicked.connect(lambda _, h=hex_color, n=name: self._on_preset_click(h, n))
            self._swatch_buttons[name] = btn
            swatch_row.addWidget(btn)
        swatch_row.addStretch()
        root.addLayout(swatch_row)

        # Swatch labels row
        label_row = QHBoxLayout()
        label_row.setSpacing(6)
        for name in PRESETS:
            lbl2 = QLabel(name)
            lbl2.setFont(QFont("Orbitron", 6))
            lbl2.setFixedWidth(44)
            lbl2.setAlignment(Qt.AlignCenter)
            lbl2.setStyleSheet("color: rgba(180,180,180,180); border:none; background:transparent;")
            label_row.addWidget(lbl2)
        label_row.addStretch()
        root.addLayout(label_row)

        # Custom color row
        custom_row = QHBoxLayout()
        custom_lbl = QLabel("Custom:")
        custom_lbl.setFont(_FONT_SM)
        custom_lbl.setStyleSheet("color: rgba(200,200,200,200); border:none; background:transparent;")

        self._hex_label = QLabel(theme_manager.color)
        self._hex_label.setFont(QFont("Courier New", 10, QFont.Bold))
        self._hex_label.setStyleSheet(
            f"color: {theme_manager.color}; border:none; background:transparent;"
        )

        pick_btn = QPushButton("🎨 Pick Color")
        pick_btn.setFont(_FONT_SM)
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.setFixedHeight(28)
        pick_btn.clicked.connect(self._on_pick_color)
        self._pick_btn = pick_btn

        custom_row.addWidget(custom_lbl)
        custom_row.addWidget(self._hex_label)
        custom_row.addStretch()
        custom_row.addWidget(pick_btn)
        root.addLayout(custom_row)

        root.addWidget(self._divider())

        # ── Section: TTS Controls ──
        root.addWidget(self._section_label("TTS CONTROL"))

        tts_box = QVBoxLayout()
        tts_box.setSpacing(6)

        info_lbl = QLabel("Adjust the voice characteristics for TTS responses.")
        info_lbl.setFont(_FONT_SM)
        info_lbl.setStyleSheet("color: rgba(180,180,180,160); border:none; background:transparent;")
        tts_box.addWidget(info_lbl)


        speaker_widget = QWidget()
        speaker_layout = QHBoxLayout(speaker_widget)
        speaker_layout.setContentsMargins(0, 0, 0, 0)
        speaker_layout.setSpacing(8)

        speaker_label = QLabel("Speaker:")
        speaker_label.setFont(_FONT_SM)
        speaker_label.setStyleSheet("color: rgba(200,200,200,200); border:none; background:transparent;")

        speaker_dropdown = QComboBox()
        speaker_dropdown.setFont(_FONT_SM)
        speaker_dropdown.setCursor(Qt.PointingHandCursor)

        # --- Populate with readable names ---
        for key, name in tts_atom.SPEAKER_MAP.items():
            speaker_dropdown.addItem(name, key)

        # --- Set current ---
        current = getattr(tts_atom, "TTS_SPEAKER", "p230")
        index = speaker_dropdown.findData(current)
        if index >= 0:
            speaker_dropdown.setCurrentIndex(index)

        # --- Change handler ---
        def on_speaker_change():
            selected_key = speaker_dropdown.currentData()
            tts_atom.TTS_SPEAKER = selected_key

        speaker_dropdown.currentIndexChanged.connect(on_speaker_change)

        speaker_layout.addWidget(speaker_label)
        speaker_layout.addWidget(speaker_dropdown)
        speaker_layout.addStretch()

        self._tts_speaker_dropdown = speaker_dropdown
        tts_box.addWidget(speaker_widget)

        tts_box.addWidget(self._create_slider(
            "Speed", 80, 130, int(tts_atom.TTS_SPEED * 100),
            lambda v: setattr(tts_atom, "TTS_SPEED", v / 100)
        ))

        tts_box.addWidget(self._create_slider(
            "Pitch", 80, 120, int(tts_atom.TTS_PITCH * 100),
            lambda v: setattr(tts_atom, "TTS_PITCH", v / 100)
        ))

        tts_box.addWidget(self._create_slider(
            "Volume", 0, 200, int(tts_atom.TTS_VOLUME * 100),
            lambda v: setattr(tts_atom, "TTS_VOLUME", v / 100)
        ))

        tts_box.addWidget(self._create_slider(
            "Pause", 0, 500, tts_atom.TTS_PAUSE,
            lambda v: setattr(tts_atom, "TTS_PAUSE", v)
        ))


        root.addLayout(tts_box)

        root.addWidget(self._divider())

        # ── Preview ──
        root.addWidget(self._section_label("PREVIEW"))
        self._preview = PreviewBar()
        root.addWidget(self._preview)
        # --- Test Button ---
        test_btn = QPushButton("▶ Test Voice")
        test_btn.setFont(_FONT)
        test_btn.setFixedHeight(30)
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.clicked.connect(self._test_tts)

        # Match theme styling
        self._tts_test_btn = test_btn
        tts_box.addWidget(test_btn)

        root.addWidget(self._divider())

        # ── Apply / Reset ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._apply_btn = QPushButton("✓  Apply")
        self._apply_btn.setFont(_FONT)
        self._apply_btn.setFixedHeight(34)
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.clicked.connect(self._on_apply)

        reset_btn = QPushButton("↺  Reset")
        reset_btn.setFont(_FONT)
        reset_btn.setFixedHeight(34)
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)
        self._reset_btn = reset_btn

        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(reset_btn)
        root.addLayout(btn_row)

        self._refresh_styles(theme_manager.color)
        self._mark_swatch(theme_manager.color)

    # ── Helpers ───────────────────────────────────────────────────────────── #
    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: rgba({theme_manager.r()},{theme_manager.g()},{theme_manager.b()},50); border:none;")
        self._dividers = getattr(self, "_dividers", [])
        self._dividers.append(line)
        return line

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Orbitron", 7, QFont.Bold))
        lbl.setStyleSheet("color: rgba(180,180,180,160); letter-spacing:2px; border:none; background:transparent;")
        return lbl

    def _create_slider(self, name, min_val, max_val, default, setter):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label = QLabel(f"{name}: {default}")
        label.setFont(_FONT_SM)
        label.setStyleSheet("color: rgba(200,200,200,200); border:none; background:transparent;")

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)

        def on_change(val):
            label.setText(f"{name}: {val}")
            setter(val)

        slider.valueChanged.connect(on_change)

        layout.addWidget(label)
        layout.addWidget(slider)

        return container

    def _test_tts(self):
        try:
            tts_atom.speak_response("This is a test of the Atom voice system.")
        except Exception as e:
            print("[TTS TEST ERROR]", e)

    def _refresh_styles(self, color: str):
        """Update all color-dependent styles in the panel itself."""
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()

        self.setObjectName("SettingsPanel")

        self.setStyleSheet(f"""
        #SettingsPanel {{
            background-color: rgba(8,12,18,230);
            border-radius: 14px;}}""")

        self._title_label.setStyleSheet(
            f"color: {color}; border:none; background:transparent;"
        )
        self._hex_label.setStyleSheet(
            f"color: {color}; border:none; background:transparent;"
        )
        self._hex_label.setText(color)
        

        btn_style = f"""
            QPushButton {{
                background-color: rgba({r},{g},{b},40);
                border: 1px solid rgba({r},{g},{b},180);
                border-radius: 8px; color: {color};
            }}
            QPushButton:hover {{ background-color: rgba({r},{g},{b},80); }}
            QPushButton:pressed {{ background-color: rgba({r},{g},{b},130); }}
        """
        self._apply_btn.setStyleSheet(btn_style)
        self._reset_btn.setStyleSheet(btn_style)
        self._pick_btn.setStyleSheet(btn_style)

        if hasattr(self, "_tts_speaker_dropdown"):
            self._tts_speaker_dropdown.setStyleSheet(f"""
                QComboBox {{
                    background-color: rgba({r},{g},{b},40);
                    border: 1px solid rgba({r},{g},{b},180);
                    border-radius: 6px;
                    padding: 4px;
                    color: {color};
                }}
                QComboBox:hover {{
                    background-color: rgba({r},{g},{b},80);
                }}
                QComboBox QAbstractItemView {{
                    background-color: rgba(10,10,10,240);
                    selection-background-color: rgba({r},{g},{b},120);
                    color: {color};
                }}
            """)
        
        if hasattr(self, "_tts_test_btn"):
            self._tts_test_btn.setStyleSheet(btn_style)

        for line in getattr(self, "_dividers", []):
            line.setStyleSheet(
                f"background: rgba({r},{g},{b},50); border:none; max-height:1px;"
            )
        

    def _mark_swatch(self, color: str):
        """Highlight the swatch matching the current color."""
        for name, btn in self._swatch_buttons.items():
            btn.set_selected(btn.color.lower() == color.lower())

    # ── Slot handlers ─────────────────────────────────────────────────────── #
    def _on_preset_click(self, hex_color: str, name: str):
        self._pending_color = hex_color
        self._mark_swatch(hex_color)
        self._preview.set_color(hex_color)
        self._refresh_styles(hex_color)

    def _on_pick_color(self):
        dialog = QColorDialog(QColor(self._pending_color), self)

        dialog.setWindowTitle("Select Theme Color")
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)  # fixes dark theme bug
        dialog.setOption(QColorDialog.ShowAlphaChannel, False)

        if dialog.exec_():
            color = dialog.selectedColor()
            if color.isValid():
                hex_color = color.name()
                self._pending_color = hex_color
                self._mark_swatch(hex_color)
                self._preview.set_color(hex_color)
                self._refresh_styles(hex_color)

    def _on_apply(self):
        theme_manager.set_color(self._pending_color)

    def _on_reset(self):
        default = "#4dffdb"
        self._pending_color = default
        self._mark_swatch(default)
        self._preview.set_color(default)
        self._refresh_styles(default)
        theme_manager.set_color(default)

    # ── Show / Hide with animation ─────────────────────────────────────────── #

    def show_animated(self, near_widget: QWidget = None):
        if near_widget:
            pos = near_widget.mapToGlobal(near_widget.rect().bottomLeft())

            x = pos.x()
            y = pos.y() + 4

            # ✅ Get screen geometry (handles fullscreen properly)
            screen = QApplication.screenAt(pos)
            if screen is None:
                screen = QApplication.primaryScreen()

            geo = screen.availableGeometry()

            # ✅ Clamp horizontally
            if x + self.width() > geo.right():
                x = geo.right() - self.width() - 10
            if x < geo.left():
                x = geo.left() + 10

            # ✅ Clamp vertically
            if y + self.height() > geo.bottom():
                y = geo.bottom() - self.height() - 10
            if y < geo.top():
                y = geo.top() + 10

            self.move(x, y)

        self._pending_color = theme_manager.color
        self._preview.set_color(theme_manager.color)
        self._refresh_styles(theme_manager.color)
        self._mark_swatch(theme_manager.color)

        self.show()

        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def hide_animated(self):
        self._is_hiding = True
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()
    
    def _on_fade_finished(self):
        if getattr(self, "_is_hiding", False):
            self.hide()
            self._is_hiding = False

    # ── Drag to move ──────────────────────────────────────────────────────── #
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    # ── Windows blur ──────────────────────────────────────────────────────── #
    def _apply_blur(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())

            class AP(ctypes.Structure):
                _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                             ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]

            class WD(ctypes.Structure):
                _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(AP)),
                             ("SizeOfData", ctypes.c_size_t)]

            accent = AP()
            accent.AccentState = 3
            accent.GradientColor = 0xCC080C12

            data = WD()
            data.Attribute = 19
            data.Data = ctypes.pointer(accent)
            data.SizeOfData = ctypes.sizeof(accent)

            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        except Exception:
            pass
