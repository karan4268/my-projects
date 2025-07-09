import sys
import os
import ctypes
from PyQt5 import QtWidgets, QtCore, QtGui
import File_sort as sorter 

class GlassWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(" File Sorter")
        self.setGeometry(100, 100, 500, 400)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowMinimizeButtonHint)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.6); color: white; font-family: Arial, sans-serif;border-radius: 5px; border: 2px solid rgba(255, 255, 255, 0.4);")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.apply_blur_effect()
        self.offset = None
        self.init_ui()


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
        accent.GradientColor = 0x99000000  # semi-transparent black

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

    def init_ui(self):
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        # Custom window button
        title_bar = QtWidgets.QHBoxLayout()
        title_bar.addStretch()
        #minimize button
        minimize_btn = QtWidgets.QPushButton("—")
        minimize_btn.setCursor(QtCore.Qt.PointingHandCursor)
        minimize_btn.setToolTip("Minimize")
        minimize_btn.setFixedSize(30, 30)
        minimize_btn.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); color:rgba(250, 235, 215, 1); font-size: 18px; border: none;padding: 0; border-radius: 15px;")
        minimize_btn.clicked.connect(self.showMinimized)
        title_bar.addWidget(minimize_btn)
        #close button
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("background-color: red; color:rgba(250, 235, 215, 1); font-size: 18px; border: none;padding: 0;border-radius: 15px;")
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        title_bar = QtWidgets.QLabel("File Organizer")
        title_bar.setAlignment(QtCore.Qt.AlignCenter)
        title_bar.setStyleSheet("font-size: 20px; color:rgba(250, 235, 215, 1); padding: 10px; background-color: rgba(255, 255, 255, 0.15); border-radius: 10px; border:none;")
        layout.addWidget(title_bar)

        # UI

#-------# Source UI
        self.source_input = QtWidgets.QLineEdit()
        self.source_input.setPlaceholderText("Select or Type source address")
        # Hover and click effects
        self.source_input.setToolTip("Enter source folder path")
        self.source_btn = QtWidgets.QPushButton("Browse")
        # browse button hover and click effects
        self.source_btn.setToolTip("Browse Source")
        self.source_btn.clicked.connect(self.browse_source)

#-------# Destination UI
        self.dest_input = QtWidgets.QLineEdit()
        self.dest_input.setPlaceholderText("Select or Type destination address")
        #Hover and click effects
        self.dest_input.setToolTip("Enter destination folder path")
        self.dest_btn = QtWidgets.QPushButton("Browse")
        # browse button hover and click effects
        self.dest_btn.setToolTip("Browse Destination")
        self.dest_btn.clicked.connect(self.browse_dest)

#-------# Sort button
        self.sort_btn = QtWidgets.QPushButton("Start Sorting")
        # Hover and click effects
        self.sort_btn.setToolTip("Sort files based on extensions and keywords")
        self.sort_btn.clicked.connect(self.start_sorting)

        # Status box
        self.status_box = QtWidgets.QTextEdit()
        self.status_box.setPlaceholderText("Logs...")
        self.status_box.setReadOnly(True)
        # auto-scroll to show the most recent log
        self.status_box.textChanged.connect(lambda: self.status_box.verticalScrollBar().setValue(self.status_box.verticalScrollBar().maximum()))

        # Extension adding section
        self.ext_input = QtWidgets.QLineEdit()
        self.ext_input.setPlaceholderText("Enter new extension or keyword (e.g., .webp, receipt)")
        self.category_dropdown = QtWidgets.QComboBox()
        self.category_dropdown.addItems(sorter.CATEGORIES.keys())
        self.add_ext_btn = QtWidgets.QPushButton("➕ Add to Category")
        self.add_ext_btn.setToolTip("Add new extension or keyword to selected category")
        self.add_ext_btn.clicked.connect(self.add_extension)

        # Style all widgets
        widgets = [self.status_box]
        for w in widgets:
            w.setStyleSheet("font-size: 14px; font-weight:bold; color: rgba(250, 235, 215, 1); background-color:  rgba(255, 255, 255, 0.1); border-radius: 12px; padding:10px; border:1px solid rgba(255, 255, 255, 0.2);")

        #Style buttons
        buttons = [self.source_btn, self.dest_btn, self.sort_btn, self.add_ext_btn]
        for b in buttons:
            b.setStyleSheet("font-size: 14px; font-weight:bold; color: rgba(250, 235, 215, 1); background-color: rgba(255, 255, 255, 0.05); border-radius: 12px; padding:10px; border:none;")
            b.setCursor(QtCore.Qt.PointingHandCursor)

        # Style inputs bar
        title_widgets = [self.ext_input, self.category_dropdown,self.dest_input,self.source_input]
        for t in title_widgets:
            t.setStyleSheet("font-size: 14px; font-weight:bold; color: rgba(250, 235, 215, 1); background-color: rgba(255, 255, 255, 0.05); border-radius: 12px; padding:10px;border: none;")

        # Add to layout

        # Source row
        source_row = QtWidgets.QHBoxLayout()
        source_row.addWidget(self.source_input)
        self.source_btn.setFixedWidth(120)
        source_row.addWidget(self.source_btn)
        layout.addLayout(source_row)

        #distnation row
        dest_row = QtWidgets.QHBoxLayout()
        dest_row.addWidget(self.dest_input)
        self.dest_btn.setFixedWidth(120)
        dest_row.addWidget(self.dest_btn)
        layout.addLayout(dest_row)

        # Add buttons and status box
        layout.addWidget(self.dest_input)
        layout.addWidget(self.dest_btn)
        layout.addWidget(self.sort_btn)
        layout.addWidget(self.status_box)
        layout.addSpacing(15)
        label = QtWidgets.QLabel("Add Extension or Keyword:")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet(" padding: 4px; color: rgba(250, 235, 215, 1); border: none; background-color: rgba(255, 255, 255, 0.1); border-radius: 8px;")
        layout.addWidget(label)

        layout.addWidget(self.ext_input)
        layout.addWidget(self.category_dropdown)
        layout.addWidget(self.add_ext_btn)

        self.setCentralWidget(central)

    def browse_source(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_input.setText(folder)

    def browse_dest(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.dest_input.setText(folder)

    def log_status(self, msg):
        self.status_box.append(msg)

    def start_sorting(self):
        src = self.source_input.text().strip()
        dst = self.dest_input.text().strip()

        if not os.path.isdir(src) or not os.path.isdir(dst):
            self.log_status("❌ Please select valid folders.")
            return

        sorter.SOURCE_FOLDER = src
        sorter.DEST_FOLDER = dst

        for folder in sorter.CATEGORIES.keys():
            os.makedirs(os.path.join(dst, folder), exist_ok=True)
        os.makedirs(os.path.join(dst, "Uncategorized"), exist_ok=True)

        self.log_status("Sorting started...")
        sorter.sort_files()
        self.log_status("✔️ Sorting complete!")

    def add_extension(self):
        category = self.category_dropdown.currentText()
        item = self.ext_input.text().strip().lower()

        if not item:
            self.log_status("⚠️ Please enter an extension or keyword.")
            return

        if item in sorter.CATEGORIES[category]:
            self.log_status(f"'{item}' already exists in '{category}'.")
        else:
            sorter.CATEGORIES[category].append(item)
            self.log_status(f"➕ Added '{item}' to '{category}'.")
            self.ext_input.setText("")

    # Drag to move support
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() == QtCore.Qt.LeftButton:
            self.move(self.pos() + event.pos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.offset = None


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = GlassWindow()
    window.show()

    sys.exit(app.exec_())
