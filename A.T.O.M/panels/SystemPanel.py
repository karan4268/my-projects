# panels/SystemPanel.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont
from PyQt5 import QtCore
import psutil
import datetime
from panels.circles import CircularProgress
from panels.cpugraph import Waveform

font = QFont("Orbitron")

class SystemPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.waveform = Waveform(self.window())
        self.waveform.hide()
        self.waveform.setStyleSheet("background:transparent; border-radius:5px" )
        self.init_ui()
    
    def create_labeled_circle(self, label_text):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)

        circle = CircularProgress()
        circle.setFixedSize(120, 120)
        layout.addWidget(circle)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(font)
        label.setStyleSheet("color: rgb(77, 255, 219); font-size: 14px; border: none;")
        layout.addWidget(label)

        return container, circle

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop)

        # Time Label
        self.time_label = QLabel()
        self.time_label.setFont(font)
        self.time_label.setStyleSheet("color: rgb(77, 255, 219); font-size: 22px; border: none;background-color:transparent;")
        main_layout.addWidget(self.time_label)

        # Horizontal layout for progress bars
        stats_layout = QHBoxLayout()
        stats_layout.setAlignment(Qt.AlignLeft)
        stats_layout.setSpacing(5)

        # CPU
        self.cpu_container, self.cpu_circle = self.create_labeled_circle("CPU")
        stats_layout.addWidget(self.cpu_container)
        self.cpu_container.setCursor(QtCore.Qt.PointingHandCursor)
        self.cpu_container.mousePressEvent = lambda event: self.waveform.toggle_waveform('cpu')

        # RAM
        self.ram_container, self.ram_circle = self.create_labeled_circle("RAM")
        stats_layout.addWidget(self.ram_container)
        self.ram_container.setCursor(QtCore.Qt.PointingHandCursor)
        self.ram_container.mousePressEvent = lambda event: self.waveform.toggle_waveform('ram')

        # Battery
        self.bat_container, self.battery_circle = self.create_labeled_circle("BAT🔋")
        stats_layout.addWidget(self.bat_container)

        for container in (self.cpu_container, self.ram_container, self.bat_container):
            container.setStyleSheet("background:none;border-radius:25px;border:1px solid rgba(77, 255, 219, 0.2)")

        main_layout.addLayout(stats_layout)
        self.setLayout(main_layout)

        # Timer for stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

        self.update_stats()

    def update_stats(self):
        now = datetime.datetime.now()
        self.time_label.setText("{}".format(now.strftime("%a, %d-%b-%Y \n %I:%M:%S %p")))

        self.cpu_circle.setValue(int(psutil.cpu_percent()))
        self.ram_circle.setValue(int(psutil.virtual_memory().percent))

        battery = psutil.sensors_battery()
        self.battery_circle.setValue(int(battery.percent) if battery else 0)
