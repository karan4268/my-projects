# panels/KeyboardPanel.py
from PyQt5.QtWidgets import QWidget, QPushButton, QGridLayout, QSizePolicy, QLineEdit, QTextEdit
from PyQt5.QtCore import Qt

class KeyboardWidget(QWidget):
    def __init__(self, target_input=None, parent=None):
        super().__init__(parent)
        self.target_input = target_input
        self.shift_enabled = False
        self.initUI()

    def initUI(self):
        layout = QGridLayout()
        layout.setSpacing(6)
        self.setLayout(layout)

        # Define rows (basic grid, we’ll expand special keys)
        rows = [
            # Row 1: Numbers + Backspace 
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "+", "BACK"],
            # Row 2: QWERTY row 
            ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P","{}","[]"],
            # Row 3: ASDF row 
            ["caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ":;", '"', "ENTER"],
            # Row 4: ZXCV row 
            [None, "SHIFT", "Z", "X", "C", "V", "B", "N", "M", ".", ",",None, None],
            # Row 5: Space bar (centered)
            ["SPACE"]
        ]

        self.buttons = {}

        for row_idx, row in enumerate(rows):
            col_idx = 0
            for key in row:
                if key is None:
                    col_idx += 1
                    continue

                btn = QPushButton(key)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                # Style
                if key in ["SHIFT", "ENTER", "SPACE", "BACK"]:
                    self.style_keyboard_button(btn, is_special=True)
                else:
                    self.style_keyboard_button(btn)

                btn.clicked.connect(lambda _, k=key: self.handle_key_press(k))
                self.buttons[key] = btn

                # Custom sizes for special keys
                if key == "SPACE":
                    # Center the space bar by adding empty columns before and after
                    total_cols = 10  # total columns in the widest row
                    space_span = 6
                    start_col = (total_cols - space_span) // 2
                    layout.addWidget(btn, row_idx, start_col, 1, space_span)
                    col_idx = total_cols  # skip all columns for this row
                elif key == "SHIFT":
                    layout.addWidget(btn, row_idx, col_idx, 1, 2)  # shift is wider
                    col_idx += 2
                elif key == "ENTER":
                    layout.addWidget(btn, row_idx, col_idx, 1, 2)  # enter is wider
                    col_idx += 2
                elif key == "BACK":
                    layout.addWidget(btn, row_idx, col_idx, 1, 2)  # backspace wider
                    col_idx += 2
                else:
                    layout.addWidget(btn, row_idx, col_idx)
                    col_idx += 1

    def style_keyboard_button(self, btn, is_special=False):
        if is_special:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(20, 20, 20, 0.4);
                    border: 1px solid #00ffe0;
                    border-radius: 8px;
                    font-size: 14px;
                    color: #00ffe0;
                }
                QPushButton:hover {
                    background: rgba(0, 255, 224, 0.15);
                    border: 1px solid #00fff7;
                }
                QPushButton:pressed {
                    background: rgba(77, 255, 219, 0.3);
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(10, 10, 10, 0.25);
                    border: 1px solid #007a7a;
                    border-radius: 10px;
                    font-size: 13px;
                    color: #00ffe0;
                }
                QPushButton:hover {
                    background: rgba(77, 255, 219, 0.1);
                }
                QPushButton:pressed {
                    background: rgba(77, 255, 219, 0.25);
                }
            """)

    def handle_key_press(self, key):
        if not self.target_input:
            return

        # Handle special keys
        if key == "SPACE":
            self.insert_text(" ")
        elif key == "SHIFT":
            self.shift_enabled = not self.shift_enabled
        elif key == "ENTER":
            self.insert_text("\n")
        elif key == "BACK":
            self.backspace()
        elif key == "123":
            # TODO: implement symbol/number layout switching
            pass
        else:
            if self.shift_enabled:
                key = key.upper()
                self.shift_enabled = False
            self.insert_text(key)

    def insert_text(self, text):
        """ Insert text into QLineEdit or QTextEdit """
        if isinstance(self.target_input, QLineEdit):
            cursor_pos = self.target_input.cursorPosition()
            current_text = self.target_input.text()
            new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
            self.target_input.setText(new_text)
            self.target_input.setCursorPosition(cursor_pos + len(text))

        elif isinstance(self.target_input, QTextEdit):
            cursor = self.target_input.textCursor()
            cursor.insertText(text)
            self.target_input.setTextCursor(cursor)

    def backspace(self):
        if isinstance(self.target_input, QLineEdit):
            cursor_pos = self.target_input.cursorPosition()
            current_text = self.target_input.text()
            if cursor_pos > 0:
                new_text = current_text[:cursor_pos - 1] + current_text[cursor_pos:]
                self.target_input.setText(new_text)
                self.target_input.setCursorPosition(cursor_pos - 1)

        elif isinstance(self.target_input, QTextEdit):
            cursor = self.target_input.textCursor()
            if cursor.position() > 0:
                cursor.deletePreviousChar()
                self.target_input.setTextCursor(cursor)
