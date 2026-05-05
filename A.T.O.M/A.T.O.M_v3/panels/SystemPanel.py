# A.T.O.M/panels/SystemPanel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5 import QtCore
import psutil, datetime

from panels.circles import CircularProgress
from panels.cpugraph import Waveform
from theme import theme_manager

_FONT = QFont("Orbitron")

class SystemPanel(QWidget):
    BATTERY_SVG_FULL     = "F:\Experiments\A.T.O.M_v3\Batt.svg"
    BATTERY_SVG_CHARGING = "F:\Experiments\A.T.O.M_v3\Charger.svg"

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.waveform = Waveform(self.window())
        self.waveform.hide()
        self.waveform.setStyleSheet("background:transparent; border-radius:5px")
        self._containers = []; self._circle_labels = []
        self.init_ui()
        theme_manager.theme_changed.connect(self.apply_theme)

    def create_labeled_circle(self, label_text):
        container = QWidget(); layout = QVBoxLayout(container); layout.setAlignment(Qt.AlignCenter)
        circle = CircularProgress(); circle.setFixedSize(120, 120); layout.addWidget(circle)
        label = QLabel(label_text); label.setAlignment(Qt.AlignCenter); label.setFont(_FONT)
        label.setStyleSheet(f"color: {theme_manager.color}; font-size: 14px; border: none;")
        layout.addWidget(label)
        return container, circle, label

    def init_ui(self):
        main_layout = QVBoxLayout(); main_layout.setAlignment(Qt.AlignTop)
        self.time_label = QLabel()
        self.time_label.setFont(_FONT)
        self.time_label.setStyleSheet(f"color: {theme_manager.color}; font-size: 22px; border: none; background-color:transparent;")
        main_layout.addWidget(self.time_label)

        stats_layout = QHBoxLayout(); stats_layout.setAlignment(Qt.AlignLeft); stats_layout.setSpacing(5)

        self.cpu_container, self.cpu_circle, self.cpu_lbl = self.create_labeled_circle("CPU")
        stats_layout.addWidget(self.cpu_container)
        self.cpu_container.setCursor(QtCore.Qt.PointingHandCursor)
        self.cpu_container.mousePressEvent = lambda e: self.waveform.toggle_waveform('cpu')

        self.ram_container, self.ram_circle, self.ram_lbl = self.create_labeled_circle("RAM")
        stats_layout.addWidget(self.ram_container)
        self.ram_container.setCursor(QtCore.Qt.PointingHandCursor)
        self.ram_container.mousePressEvent = lambda e: self.waveform.toggle_waveform('ram')

        self.bat_container, self.battery_circle, self.bat_lbl = self.create_labeled_circle("BAT")
        self.battery_circle.is_battery = True
        stats_layout.addWidget(self.bat_container)

        self._containers = [self.cpu_container, self.ram_container, self.bat_container]
        self._circle_labels = [self.cpu_lbl, self.ram_lbl, self.bat_lbl]
        self._refresh_container_styles(theme_manager.color)

        main_layout.addLayout(stats_layout); self.setLayout(main_layout)

        self.stats_timer = QTimer(); self.stats_timer.timeout.connect(self.update_stats); self.stats_timer.start(1000)
        self.battery_timer = QTimer(self); self.battery_timer.timeout.connect(self.update_battery_status); self.battery_timer.start(500)
        self.update_stats(); self.update_battery_status()

    def apply_theme(self, color):
        self.time_label.setStyleSheet(f"color: {color}; font-size: 22px; border: none; background-color:transparent;")
        for lbl in self._circle_labels:
            lbl.setStyleSheet(f"color: {color}; font-size: 14px; border: none;")
        self._refresh_container_styles(color)
        for circle in (self.cpu_circle, self.ram_circle, self.battery_circle):
            circle.set_theme_color(color)
        self.waveform.apply_theme(color)

    def _refresh_container_styles(self, color):
        c = QColor(color); r,g,b = c.red(),c.green(),c.blue()
        style = f"background:none; border-radius:25px; border:1px solid rgba({r},{g},{b},50);"
        for container in self._containers:
            container.setStyleSheet(style)

    def update_stats(self):
        now = datetime.datetime.now()
        self.time_label.setText(now.strftime("%a, %d-%b-%Y \n %I:%M:%S %p"))
        self.cpu_circle.setValue(int(psutil.cpu_percent()))
        self.ram_circle.setValue(int(psutil.virtual_memory().percent))

    def update_battery_status(self):
        battery = psutil.sensors_battery()
        if not battery: return
        self.battery_circle.setValue(int(battery.percent))
        if battery.power_plugged: self.battery_circle.set_svg_icon(self.BATTERY_SVG_CHARGING)
        else: self.battery_circle.set_svg_icon(self.BATTERY_SVG_FULL)
