# panels/KeyboardPanel.py
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QSizePolicy,
    QLineEdit, QTextEdit, QVBoxLayout, QSlider ,QGraphicsDropShadowEffect
)
from PyQt5.QtCore import QPropertyAnimation, QSize, QEasingCurve,Qt
from PyQt5.QtGui import QFont,QColor

font = QFont("Orbitron")
class KeyboardWidget(QWidget):
    def __init__(self, target_input=None, parent=None):
        super().__init__(parent)
        self.target_input = target_input
        self.shift_enabled = False
        self.buttons = {}
        self.initUI()
        # Glow effect
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setBlurRadius(20)
        self.glow.setColor(QColor(77, 255, 219))
        self.glow.setOffset(0)

    def initUI(self):
        layout = QGridLayout()
        layout.setSpacing(5)
        keys = [
            ['1','2','3','4','5','6','7','8','9','0','-','+','BACK'],
            ['TAB','Q','W','E','R','T','Y','U','I','O','P','[',']'],
            ['CAPS','A','S','D','F','G','H','J','K','L',';',"'",'ENTER'],
            ['SHIFT','Z','X','C','V','B','N','M',',','.','?', 'SHIFT'],
            [None,None,'SPACE']
        ]

        for row, key_row in enumerate(keys):
            col = 0
            for key in key_row:
                if key is None:
                    col += 1
                    continue

                button = QPushButton(key)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                button.setStyleSheet(self.key_style())
                button.clicked.connect(lambda checked, k=key: self.on_key_press(k))

                # special sizing rules
                if key == "SPACE":
                    layout.addWidget(button, row, col, 1, 5)  # wide
                    col += 5
                elif key == "SHIFT":
                    layout.addWidget(button, row, col, 1, 2)  # longer shift
                    col += 2
                elif key == "BACK":
                    layout.addWidget(button, row, col, 1, 2)  # long backspace
                    col += 2
                elif key == "ENTER":
                    layout.addWidget(button, row, col, 1, 2)  # L-shape (2 rows tall, 2 col wide)
                    col += 2
                else:
                    layout.addWidget(button, row, col, 1, 1)
                    col += 1

                self.buttons[key] = button

        self.setLayout(layout)

    def key_style(self):
        return """
            QPushButton {
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(77, 255, 219, 0.8);
                border-radius: 6px;
                font-size: 14px;
                color: rgba(77, 255, 219, 0.8);
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 224, 0.2);
            }
            QPushButton:pressed {
                background-color: rgba(0, 255, 224, 0.4);
            }
        """

    def on_key_press(self, key):
        if not self.target_input:
            return

        if isinstance(self.target_input, (QLineEdit, QTextEdit)):
            cursor = self.target_input.textCursor() if isinstance(self.target_input, QTextEdit) else None
            if key == "SPACE":
                self.target_input.insertPlainText(" ") if cursor else self.target_input.insert(" ")
            elif key == "ENTER":
                self.target_input.insertPlainText("\n") if cursor else self.target_input.returnPressed.emit()
            elif key == "BACK":
                if cursor:
                    cursor.deletePreviousChar()
                else:
                    self.target_input.backspace()
            elif key == "TAB":
                self.target_input.insertPlainText("\t") if cursor else self.target_input.insert("\t")
            elif key == "SHIFT":
                self.shift_enabled = not self.shift_enabled
            elif key == "CAPS":
                self.shift_enabled = not self.shift_enabled
            else:
                char = key.upper() if self.shift_enabled else key.lower()
                self.target_input.insertPlainText(char) if cursor else self.target_input.insert(char)

class CollapsibleKeyboard(QWidget):
    def __init__(self, target_input, parent=None):
        super().__init__(parent)
        self.target_input = target_input  # <-- this is your chat input
        self.is_collapsed = True
        self.toggle_btn = QPushButton("⌨ Keyboard")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFont(font)
        self.setToolTip("Toggle Keyboard")
        self.toggle_btn.clicked.connect(self.toggle_keyboard)
        
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.1);
                border: 1px solid rgb(77, 255, 219);
                border-radius: 25px;
                color: rgb(77, 255, 219);
                font-size: 12px;
                text-align: left;
                padding: 6px;
                max-width: 85px;
            }
            QPushButton:checked {
                background-color: rgba(77, 255, 219, 80);
            }
        """)

        # This is the actual virtual keyboard
        self.keyboard = KeyboardWidget(target_input=self.target_input)
        self.keyboard.setVisible(False)  # hidden by default

        layout = QVBoxLayout(self)
        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.keyboard)

    def toggle_keyboard(self):
        self.is_collapsed = not self.is_collapsed
        self.keyboard.setVisible(not self.is_collapsed)