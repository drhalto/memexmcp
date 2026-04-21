"""Global Qt stylesheet — modern Windows-friendly light theme.

Accent color is the navy from the app icon. To get a primary or danger
button, set the dynamic property on the QPushButton:

    btn.setProperty("primary", True)
    btn.setProperty("danger", True)

(Then call ``btn.style().unpolish(btn); btn.style().polish(btn)`` if you
flip it after creation.)
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

ACCENT = "#1e3a5f"          # navy from the icon
ACCENT_HOVER = "#2a4a73"
ACCENT_PRESSED = "#16294a"
DANGER = "#c0392b"
DANGER_HOVER = "#a8311f"
BG = "#f6f7f9"
SURFACE = "#ffffff"
BORDER = "#e2e5ea"
BORDER_STRONG = "#c8ccd3"
TEXT = "#1a1d21"
TEXT_MUTED = "#6b7280"
TEXT_SUBTLE = "#9aa0a6"
HOVER = "#f0f2f5"
SELECTED_BG = ACCENT
SELECTED_FG = "#ffffff"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}

QMainWindow, QDialog, QWizard {{
    background-color: {BG};
}}

QWidget {{
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 7px 14px;
    color: {TEXT};
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {HOVER};
    border-color: #a9aeb6;
}}
QPushButton:pressed {{
    background-color: #e6e9ee;
}}
QPushButton:disabled {{
    color: #b8bcc4;
    background-color: #f1f2f5;
    border-color: #dfe2e7;
}}

QPushButton[primary="true"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
    padding: 8px 18px;
}}
QPushButton[primary="true"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton[primary="true"]:disabled {{
    background-color: #b6bcc6;
    border-color: #b6bcc6;
    color: white;
}}

QPushButton[danger="true"] {{
    background-color: {SURFACE};
    border: 1px solid #e3b8b3;
    color: {DANGER};
}}
QPushButton[danger="true"]:hover {{
    background-color: #fdf3f1;
    border-color: {DANGER};
}}
QPushButton[danger="true"]:pressed {{
    background-color: #fbe4e0;
}}

/* ---------- Inputs ---------- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: #f5f6f8;
    color: #98a0aa;
}}

/* ---------- Lists ---------- */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    outline: 0;
}}
QListWidget::item {{
    padding: 9px 12px;
    border-radius: 5px;
    margin: 1px 0;
}}
QListWidget::item:selected {{
    background-color: {SELECTED_BG};
    color: {SELECTED_FG};
}}
QListWidget::item:hover:!selected {{
    background-color: {HOVER};
}}

/* ---------- Tables ---------- */
QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: #f9fafb;
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: #eef0f3;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QTableWidget::item, QTableView::item {{
    padding: 8px 6px;
    border: none;
}}
QHeaderView::section {{
    background-color: #f1f3f6;
    padding: 9px 8px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
    color: {TEXT_MUTED};
}}
QHeaderView::section:last {{ border-right: none; }}
QTableCornerButton::section {{
    background-color: #f1f3f6;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}

/* ---------- Progress bar ---------- */
QProgressBar {{
    background-color: #e6e9ef;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: {TEXT_MUTED};
    font-weight: 500;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* ---------- GroupBox cards ---------- */
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 18px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {ACCENT};
    background-color: {BG};
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {BG};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 10px 22px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {TEXT_MUTED};
    font-weight: 500;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG};
    border-color: {BORDER};
    color: {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

/* ---------- Radios + checks ---------- */
QRadioButton, QCheckBox {{
    spacing: 8px;
    padding: 4px 0;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

/* ---------- Status bar ---------- */
QStatusBar {{
    background-color: #eef0f4;
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}

/* ---------- Tier card frame (used in Settings + wizard) ---------- */
QFrame#tierCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0;
}}
QFrame#tierCard[selected="true"] {{
    border: 2px solid {ACCENT};
    background-color: #f3f6fb;
}}
QFrame#tierCard QLabel {{
    background: transparent;
}}
QLabel[muted="true"] {{
    color: {TEXT_MUTED};
}}
QLabel[badge="true"] {{
    background-color: {ACCENT};
    color: white;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 8pt;
    font-weight: 700;
}}

/* ---------- Drop zone ---------- */
QFrame#dropZone {{
    background-color: {SURFACE};
    border: 2px dashed {BORDER_STRONG};
    border-radius: 10px;
}}
QFrame#dropZone[hover="true"] {{
    border: 2px dashed {ACCENT};
    background-color: #eef3fa;
}}
"""


def apply_style(app: QApplication) -> None:
    """Install the global stylesheet and a sane default font on the QApplication."""
    app.setStyle("Fusion")
    base_font = QFont("Segoe UI", 10)
    app.setFont(base_font)
    app.setStyleSheet(STYLESHEET)
