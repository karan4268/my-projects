# A.T.O.M/theme.py
"""
Global Theme Manager — singleton.
All panels import `theme_manager` and connect to `theme_changed` signal.

Usage:
    from theme import theme_manager
    theme_manager.theme_changed.connect(self.apply_theme)

    def apply_theme(self, hex_color: str):
        # update your widget colors here
"""
from PyQt5.QtCore import QObject, pyqtSignal, QSettings
from PyQt5.QtGui import QColor
from pathlib import Path


# ── Built-in presets ──────────────────────────────────────────────────────── #
PRESETS = {
    "Teal":    "#4dffdb",   # original A.T.O.M default
    "Cyan":    "#00f0ff",
    "Green":   "#39ff14",   # neon green
    "Purple":  "#bf5fff",
    "Gold":    "#ffd700",
    "Red":     "#ff4444",
    "White":   "#e8e8e8",
    "Blue":    "#4d9fff",
}


class ThemeManager(QObject):
    """
    Singleton Qt object.
    Emit theme_changed(hex_string) whenever the active color changes.
    """
    theme_changed = pyqtSignal(str)   # hex color string e.g. "#4dffdb"

    def __init__(self):
        super().__init__()
        config_path = str(Path.home() / "atom_config.ini")
        self._settings = QSettings(config_path, QSettings.IniFormat)
        self._color: str = self._settings.value("theme_color", "#4dffdb")

    # ── Public API ─────────────────────────────────────────────────────────── #
    @property
    def color(self) -> str:
        return self._color

    @property
    def qcolor(self) -> QColor:
        return QColor(self._color)

    def r(self) -> int:  return self.qcolor.red()
    def g(self) -> int:  return self.qcolor.green()
    def b(self) -> int:  return self.qcolor.blue()

    def rgba(self, alpha: int = 255) -> str:
        """Return 'rgba(r,g,b,a)' string for stylesheet use."""
        return f"rgba({self.r()},{self.g()},{self.b()},{alpha})"

    def set_color(self, hex_color: str, save: bool = True):
        """Change the active theme color and notify all connected widgets."""
        if not QColor(hex_color).isValid():
            return
        self._color = hex_color
        if save:
            self._settings.setValue("theme_color", hex_color)
            self._settings.sync()
        self.theme_changed.emit(hex_color)


# ── Module-level singleton ─────────────────────────────────────────────────── #
theme_manager = ThemeManager()


# ── Stylesheet helpers ─────────────────────────────────────────────────────── #
def themed_border_style(color: str, bg_alpha: int = 25, radius: int = 6) -> str:
    c = QColor(color)
    r, g, b = c.red(), c.green(), c.blue()
    return (
        f"background-color: rgba({r},{g},{b},{bg_alpha});"
        f"border: 1px solid rgba({r},{g},{b},200);"
        f"border-radius: {radius}px;"
        f"color: {color};"
    )


def themed_button_style(color: str) -> str:
    c = QColor(color)
    r, g, b = c.red(), c.green(), c.blue()
    return f"""
        QPushButton {{
            background-color: rgba({r},{g},{b},25);
            border: 1px solid rgba({r},{g},{b},200);
            border-radius: 15px;
            color: {color};
            font-size: 18px;
        }}
        QPushButton:hover {{
            background-color: rgba({r},{g},{b},60);
        }}
        QPushButton:pressed {{
            background-color: rgba({r},{g},{b},100);
        }}
    """


def themed_key_style(color: str) -> str:
    c = QColor(color)
    r, g, b = c.red(), c.green(), c.blue()
    return f"""
        QPushButton {{
            background-color: rgba(0,0,0,0.25);
            border: 1px solid rgba({r},{g},{b},200);
            border-radius: 6px;
            font-size: 14px;
            color: rgba({r},{g},{b},200);
        }}
        QPushButton:hover  {{ background-color: rgba({r},{g},{b},50); }}
        QPushButton:pressed {{ background-color: rgba({r},{g},{b},100); }}
    """
