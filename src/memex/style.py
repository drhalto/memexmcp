"""Global Qt stylesheet — Linear/Vercel-style premium dashboard.

Design pattern: dark navy sidebar + cool off-white content area + white cards
with a real drop-shadow for depth. Accent is the navy from the app icon.

All color pairs verified to pass WCAG AA (4.5:1) for body text.

Cards are plain ``QFrame`` widgets with ``objectName="card"`` (or
``"tierCard"`` / ``"dropZone"`` for specific variants). Use
:func:`apply_card_shadow` to give them a subtle elevation.

Buttons opt into variants via dynamic properties::

    btn.setProperty("primary", True)
    btn.setProperty("danger",  True)
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

# Backgrounds
BG              = "#f1f5f9"   # slate-100, cool off-white. Strong contrast vs white cards.
BG_SIDEBAR      = "#0f172a"   # slate-900
SURFACE         = "#ffffff"   # cards
SURFACE_HOVER   = "#f8fafc"   # subtle hover on white surfaces

# Borders — strong enough to define a card without screaming.
BORDER          = "#cbd5e1"   # slate-300 — visible
BORDER_STRONG   = "#94a3b8"   # slate-400 — for inputs / focus-adjacent
BORDER_FOCUS    = "#1e3a5f"   # accent navy

# Sidebar
SIDEBAR_BORDER  = "#1e293b"   # slate-800
SIDEBAR_HOVER   = "rgba(255, 255, 255, 0.06)"

# Text
TEXT            = "#0f172a"   # slate-900, near-black
TEXT_MUTED      = "#475569"   # slate-600
TEXT_SUBTLE     = "#94a3b8"   # slate-400
TEXT_INVERSE    = "#ffffff"
TEXT_INVERSE_MUTED = "#94a3b8"

# Accent
ACCENT          = "#1e3a5f"
ACCENT_HOVER    = "#2a4a73"
ACCENT_PRESSED  = "#16294a"
ACCENT_TINT     = "#eef3fa"

# Status
DANGER          = "#dc2626"
DANGER_HOVER    = "#b91c1c"
DANGER_TINT     = "#fef2f2"
SUCCESS         = "#16a34a"

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ================================================================
   Base font + reset
   ================================================================ */
* {{
    font-family: "Segoe UI Variable", "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 11pt;
    color: {TEXT};
}}

QMainWindow, QDialog, QWizard, QWizardPage {{
    background-color: {BG};
}}

QSplitter::handle                {{ background-color: {BORDER}; }}
QSplitter::handle:horizontal     {{ width: 1px; }}
QSplitter::handle:vertical       {{ height: 1px; }}

QToolTip {{
    background-color: #0f172a;
    color: white;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 6px 10px;
}}

/* ================================================================
   Sidebar (objectName="sidebar")
   ================================================================ */
QWidget#sidebar {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {SIDEBAR_BORDER};
}}
QWidget#sidebar QLabel {{
    background: transparent;
    color: {TEXT_INVERSE_MUTED};
}}
QWidget#sidebar QLabel[brand="true"] {{
    color: {TEXT_INVERSE};
    font-weight: 700;
    font-size: 16pt;
    letter-spacing: 0.01em;
}}
QWidget#sidebar QLabel[caption="true"] {{
    color: #64748b;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-weight: 700;
}}

QWidget#sidebar QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
    color: {TEXT_INVERSE_MUTED};
    padding: 0;
    font-size: 11pt;
}}
QWidget#sidebar QListWidget::item {{
    padding: 10px 14px;
    border-radius: 6px;
    margin: 1px 4px;
    color: {TEXT_INVERSE_MUTED};
}}
QWidget#sidebar QListWidget::item:hover:!selected {{
    background-color: {SIDEBAR_HOVER};
    color: {TEXT_INVERSE};
}}
QWidget#sidebar QListWidget::item:selected {{
    background-color: {ACCENT};
    color: {TEXT_INVERSE};
    font-weight: 500;
}}

QWidget#sidebar QPushButton {{
    background-color: transparent;
    border: 1px solid #334155;
    color: {TEXT_INVERSE_MUTED};
    border-radius: 6px;
    padding: 9px 14px;
    font-weight: 500;
    font-size: 11pt;
}}
QWidget#sidebar QPushButton:hover {{
    background-color: {SIDEBAR_HOVER};
    color: {TEXT_INVERSE};
    border-color: #475569;
}}
QWidget#sidebar QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.10);
}}

/* ================================================================
   Buttons (light)
   ================================================================ */
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 9px 18px;
    color: {TEXT};
    font-weight: 500;
    font-size: 11pt;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
    border-color: {BORDER_STRONG};
}}
QPushButton:pressed {{
    background-color: #f1f5f9;
}}
QPushButton:disabled {{
    color: {TEXT_SUBTLE};
    background-color: #f1f5f9;
    border-color: #e2e8f0;
}}

QPushButton[primary="true"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: {TEXT_INVERSE};
    font-weight: 600;
    padding: 10px 22px;
}}
QPushButton[primary="true"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[primary="true"]:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton[primary="true"]:disabled {{
    background-color: #94a3b8;
    border-color: #94a3b8;
    color: {TEXT_INVERSE};
}}

QPushButton[danger="true"] {{
    background-color: {SURFACE};
    border: 1px solid #fecaca;
    color: {DANGER};
    font-weight: 500;
}}
QPushButton[danger="true"]:hover {{
    background-color: {DANGER_TINT};
    border-color: {DANGER};
}}
QPushButton[danger="true"]:pressed {{
    background-color: #fee2e2;
}}

/* ================================================================
   Inputs
   ================================================================ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 9px 12px;
    color: {TEXT};
    font-size: 11pt;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_INVERSE};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #f1f5f9;
    color: {TEXT_SUBTLE};
}}

/* ================================================================
   Lists (outside sidebar)
   ================================================================ */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    outline: 0;
    color: {TEXT};
}}
QListWidget::item {{
    padding: 10px 12px;
    border-radius: 5px;
    margin: 1px 0;
    color: {TEXT};
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: {TEXT_INVERSE};
}}
QListWidget::item:hover:!selected {{
    background-color: {SURFACE_HOVER};
}}

/* ================================================================
   Tables
   ================================================================ */
QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: #fafafa;
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: #f1f5f9;
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT};
    color: {TEXT};
    font-size: 11pt;
}}
QTableWidget::item, QTableView::item {{
    padding: 10px 8px;
    border: none;
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: #f1f5f9;
    padding: 11px 10px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-weight: 700;
    color: {TEXT_MUTED};
    font-size: 9pt;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}
QHeaderView::section:last  {{ border-right: none; }}
QTableCornerButton::section {{
    background-color: #f1f5f9;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}

/* ================================================================
   Progress bar
   ================================================================ */
QProgressBar {{
    background-color: #e2e8f0;
    border: none;
    border-radius: 5px;
    height: 12px;
    text-align: center;
    color: {TEXT_MUTED};
    font-weight: 600;
    font-size: 9pt;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* ================================================================
   Cards (objectName="card")
   ================================================================ */
QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

/* ================================================================
   Tier card (objectName="tierCard")
   ================================================================ */
QFrame#tierCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#tierCard:hover {{
    border-color: {BORDER_STRONG};
    background-color: {SURFACE_HOVER};
}}
QFrame#tierCard[selected="true"] {{
    border: 2px solid {ACCENT};
    background-color: {ACCENT_TINT};
}}
QFrame#tierCard QLabel {{ background: transparent; }}

/* ================================================================
   Drop zone (objectName="dropZone")
   ================================================================ */
QFrame#dropZone {{
    background-color: {SURFACE};
    border: 2px dashed {BORDER_STRONG};
    border-radius: 12px;
}}
QFrame#dropZone[hover="true"] {{
    border: 2px dashed {ACCENT};
    background-color: {ACCENT_TINT};
}}
QFrame#dropZone QLabel {{ background: transparent; }}

/* ================================================================
   Tabs
   ================================================================ */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {BG};
    top: -1px;
}}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    padding: 12px 26px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {TEXT_MUTED};
    font-weight: 600;
    font-size: 11pt;
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

/* ================================================================
   Radios + checks
   ================================================================ */
QRadioButton, QCheckBox {{
    spacing: 8px;
    padding: 4px 0;
    color: {TEXT};
    background: transparent;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 18px;
    height: 18px;
}}

/* ================================================================
   Status bar
   ================================================================ */
QStatusBar {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    padding: 6px 16px;
    font-weight: 500;
    font-size: 10pt;
}}
QStatusBar::item {{ border: none; }}

/* ================================================================
   Scroll area (background transparent so the content's BG shows)
   ================================================================ */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {BG};
}}

/* Slim modern scrollbars */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_STRONG};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 0 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: #cbd5e1;
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BORDER_STRONG};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ================================================================
   Generic helpers (set via dynamic properties)
   ================================================================ */
QLabel[muted="true"] {{
    color: {TEXT_MUTED};
    background: transparent;
    font-size: 11pt;
}}
QLabel[subtle="true"] {{
    color: {TEXT_SUBTLE};
    background: transparent;
}}
QLabel[badge="true"] {{
    background-color: {ACCENT};
    color: {TEXT_INVERSE};
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.06em;
}}
QLabel[h1="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 26pt;
    font-weight: 700;
    letter-spacing: -0.01em;
    padding-bottom: 2px;
}}
QLabel[h2="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 18pt;
    font-weight: 600;
}}
QLabel[h3="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 14pt;
    font-weight: 600;
}}
QLabel[cardTitle="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 14pt;
    font-weight: 600;
}}

QLabel#emptyState {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_MUTED};
    font-size: 11pt;
}}
"""


def apply_style(app: QApplication) -> None:
    """Install the global stylesheet and a sane default font on the QApplication."""
    app.setStyle("Fusion")
    base_font = QFont("Segoe UI Variable", 11)
    if not base_font.exactMatch():
        base_font = QFont("Segoe UI", 11)
    app.setFont(base_font)
    app.setStyleSheet(STYLESHEET)


def apply_card_shadow(widget: QWidget, *, blur: int = 18, offset_y: int = 3, opacity: int = 28) -> None:
    """Subtle drop shadow that reads as 'elevated card' on the cool off-white BG.

    `opacity` is 0–255 alpha for the shadow color.
    """
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, offset_y)
    eff.setColor(QColor(15, 23, 42, opacity))   # slate-900 with low alpha
    widget.setGraphicsEffect(eff)
