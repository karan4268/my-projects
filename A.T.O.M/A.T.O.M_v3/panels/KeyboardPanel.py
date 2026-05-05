# A.T.O.M/panels/KeyboardPanel.py
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QSizePolicy,
    QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QSplitter, QApplication
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor

from theme import theme_manager, themed_key_style

_FONT = QFont("Orbitron")


class KeyboardWidget(QWidget):
    def __init__(self, target_input=None, parent=None):
        super().__init__(parent)
        self.target_input = target_input
        self.shift_enabled = False
        self.caps_enabled  = False
        self.buttons       = {}
        self._init_ui()
        theme_manager.theme_changed.connect(self.apply_theme)
        self.apply_theme(theme_manager.color)  # apply current theme on init

    def _init_ui(self):
        layout = QGridLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Key layout ──────────────────────────────────────────────
        keys = [
            ['`','1','2','3','4','5','6','7','8','9','0','-','=','BACK'],
            ['TAB','Q','W','E','R','T','Y','U','I','O','P','[',']','\\'],
            ['CAPS','A','S','D','F','G','H','J','K','L',';',"'",'ENTER'],
            ['SHIFT','Z','X','C','V','B','N','M',',','.','/',  'SHIFT'],
            ['CTRL', 'ALT', None, None, 'SPACE', None, None, 'ALT', 'CTRL'],
        ]

        # Special key widths (column span)
        _SPANS = {
            'BACK': 2, 'TAB': 2, 'CAPS': 2, 'ENTER': 2,
            'SHIFT': 2, 'SPACE': 5, 'CTRL': 2, 'ALT': 2,
        }

        # Special key labels
        _LABELS = {
            'BACK': '⌫', 'ENTER': '↵', 'SHIFT': '⇧',
            'CAPS': 'CAPS', 'TAB': '⇥', 'SPACE': '',
            'CTRL': 'CTRL', 'ALT': 'ALT',
        }

        for row, key_row in enumerate(keys):
            col = 0
            for key in key_row:
                if key is None:
                    col += 1
                    continue
                label  = _LABELS.get(key, key)
                span   = _SPANS.get(key, 1)
                button = QPushButton(label)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                button.setMinimumHeight(36)
                button.setFont(QFont("Consolas", 9))
                button.clicked.connect(lambda checked, k=key: self.on_key_press(k))
                self._style_key(button, key, theme_manager.color)
                layout.addWidget(button, row, col, 1, span)
                col += span
                self.buttons[key] = button

        self.setLayout(layout)

    def _style_key(self, button: QPushButton, key: str, color: str):
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()

        # Special keys get a slightly different tint
        special = key in ('BACK', 'ENTER', 'SHIFT', 'CAPS', 'TAB', 'CTRL', 'ALT')
        func    = key in ('SPACE',)

        if special:
            bg      = f"rgba({r},{g},{b},0.18)"
            bg_hov  = f"rgba({r},{g},{b},0.35)"
            border  = f"rgba({r},{g},{b},0.5)"
        elif func:
            bg      = f"rgba({r},{g},{b},0.06)"
            bg_hov  = f"rgba({r},{g},{b},0.18)"
            border  = f"rgba({r},{g},{b},0.25)"
        else:
            bg      = f"rgba(0,0,0,0.25)"
            bg_hov  = f"rgba({r},{g},{b},0.22)"
            border  = f"rgba({r},{g},{b},0.30)"

        button.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: rgb({r},{g},{b});
                border: 1px solid {border};
                border-radius: 5px;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {bg_hov};
                border-color: rgb({r},{g},{b});
            }}
            QPushButton:pressed {{
                background: rgba({r},{g},{b},0.45);
            }}
        """)

    def apply_theme(self, color: str):
        for key, btn in self.buttons.items():
            self._style_key(btn, key, color)

    # ── Key logic ────────────────────────────────────────────────────
    def on_key_press(self, key):
        if not self.target_input:
            return

        is_text_edit = isinstance(self.target_input, QTextEdit)
        is_line_edit = isinstance(self.target_input, QLineEdit)

        def insert(text):
            if is_text_edit:
                self.target_input.insertPlainText(text)
            elif is_line_edit:
                self.target_input.insert(text)

        def backspace():
            if is_text_edit:
                self.target_input.textCursor().deletePreviousChar()
            elif is_line_edit:
                self.target_input.backspace()

        if key == 'SPACE':
            insert(' ')
        elif key == 'ENTER':
            if is_text_edit:
                self.target_input.insertPlainText('\n')
            elif is_line_edit:
                self.target_input.returnPressed.emit()
        elif key == 'BACK':
            backspace()
        elif key == 'TAB':
            insert('\t')
        elif key == 'SHIFT':
            self.shift_enabled = not self.shift_enabled
            self._update_shift_display()
        elif key == 'CAPS':
            self.caps_enabled = not self.caps_enabled
            self._update_shift_display()
        elif key in ('CTRL', 'ALT'):
            pass  # modifier keys — no action for now
        else:
            upper = self.shift_enabled ^ self.caps_enabled
            insert(key.upper() if upper else key.lower())
            if self.shift_enabled:
                self.shift_enabled = False
                self._update_shift_display()

    def _update_shift_display(self):
        """Update key labels to reflect current shift/caps state."""
        upper = self.shift_enabled ^ self.caps_enabled
        for key, btn in self.buttons.items():
            if len(key) == 1 and key.isalpha():
                btn.setText(key.upper() if upper else key.lower())
        # Highlight SHIFT and CAPS buttons when active
        c = QColor(theme_manager.color)
        r, g, b = c.red(), c.green(), c.blue()
        for special_key in ('SHIFT', 'CAPS'):
            btn = self.buttons.get(special_key)
            if not btn:
                continue
            active = self.shift_enabled if special_key == 'SHIFT' else self.caps_enabled
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba({r},{g},{b},0.55);
                        color: rgb({r},{g},{b});
                        border: 1px solid rgb({r},{g},{b});
                        border-radius: 5px;
                        font-family: Consolas, monospace;
                        font-size: 9pt;
                    }}
                """)
            else:
                self._style_key(btn, special_key, theme_manager.color)


# ── Collapsible wrapper ───────────────────────────────────────────────────────
class CollapsibleKeyboard(QWidget):
    """
    Wraps KeyboardWidget in a collapsible panel.
    When expanded, emits `visibility_changed(True)` so the parent layout
    can shrink the terminal panel to make room.
    """
    visibility_changed = pyqtSignal(bool)   # True = shown, False = hidden

    def __init__(self, target_input, parent=None):
        super().__init__(parent)
        self.target_input  = target_input
        self.is_collapsed  = True
        self._anim_height  = 0

        # ── Toggle button ────────────────────────────────────────────
        self.toggle_btn = QPushButton("⌨ Keyboard")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFont(_FONT)
        self.toggle_btn.setToolTip("Show / Hide On-screen Keyboard")
        self.toggle_btn.setFixedHeight(30)
        self.toggle_btn.clicked.connect(self.toggle_keyboard)
        self._refresh_toggle_style(theme_manager.color)

        # ── Keyboard ─────────────────────────────────────────────────
        self.keyboard = KeyboardWidget(target_input=self.target_input)
        self.keyboard.setVisible(False)
        self.keyboard.setMinimumHeight(0)
        self.keyboard.setMaximumHeight(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.keyboard)

        theme_manager.theme_changed.connect(self._refresh_toggle_style)
        self._refresh_toggle_style(theme_manager.color)  # apply on init

    def _refresh_toggle_style(self, color: str):
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,0,0,0.15);
                border: 1px solid rgba({r},{g},{b},0.4);
                border-radius: 6px;
                color: rgb({r},{g},{b});
                font-size: 11px;
                padding: 4px 10px;
                text-align: left;
            }}
            QPushButton:checked {{
                background: rgba({r},{g},{b},0.18);
                border-color: rgb({r},{g},{b});
            }}
            QPushButton:hover {{
                background: rgba({r},{g},{b},0.12);
            }}
        """)
        if hasattr(self, 'keyboard'):
            self.keyboard.apply_theme(color)

    def toggle_keyboard(self):
        self.is_collapsed = not self.is_collapsed
        show = not self.is_collapsed

        if show:
            self.keyboard.setVisible(True)
            # Animate open
            self._animate_height(0, 220)
        else:
            # Animate close then hide
            self._animate_height(220, 0, hide_after=True)

        self.visibility_changed.emit(show)
        self.toggle_btn.setChecked(show)

    def _animate_height(self, start: int, end: int, hide_after: bool = False):
        self._anim = QPropertyAnimation(self.keyboard, b"maximumHeight")
        self._anim.setDuration(180)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        if hide_after:
            self._anim.finished.connect(lambda: self.keyboard.setVisible(False))
        self._anim.start()