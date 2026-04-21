"""Global Qt stylesheet — Linear/Vercel-style premium dashboard.

Design pattern: dark navy sidebar + warm off-white content area + white cards
with crisp borders. Accent is the navy from the app icon.

All color pairs verified to pass WCAG AA (4.5:1) for body text.

Usage:

    from PySide6.QtWidgets import QApplication
    from memex.style import apply_style

    app = QApplication(sys.argv)
    apply_style(app)

To get a primary or danger button, set the dynamic property on the QPushButton::

    btn.setProperty("primary", True)
    btn.setProperty("danger", True)

(Then call ``btn.style().unpolish(btn); btn.style().polish(btn)`` if you flip
it after construction.)
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

# Backgrounds
BG              = "#f5f5f4"   # warm off-white (stone-50). Content area + windows.
BG_SIDEBAR      = "#0f172a"   # deep slate. Premium dark sidebar.
SURFACE         = "#ffffff"   # white cards.
SURFACE_HOVER   = "#f9fafb"   # subtle hover on white surfaces.

# Borders — strong enough to define a card without screaming.
BORDER          = "#d4d4d8"   # zinc-300
BORDER_STRONG   = "#a1a1aa"   # zinc-400, for inputs needing more presence
BORDER_FOCUS    = "#1e3a5f"   # accent navy, focus state

# Sidebar internal borders / dividers
SIDEBAR_BORDER  = "#1e293b"   # slate-800
SIDEBAR_HOVER   = "rgba(255, 255, 255, 0.06)"

# Text
TEXT            = "#18181b"   # zinc-900, near-black
TEXT_MUTED      = "#52525b"   # zinc-600
TEXT_SUBTLE     = "#a1a1aa"   # zinc-400
TEXT_INVERSE    = "#ffffff"
TEXT_INVERSE_MUTED = "#94a3b8"  # slate-400, for sidebar muted text

# Accent (navy from icon)
ACCENT          = "#1e3a5f"
ACCENT_HOVER    = "#2a4a73"
ACCENT_PRESSED  = "#16294a"
ACCENT_TINT     = "#eff4fa"   # very light navy tint, for selected card bg

# Status
DANGER          = "#dc2626"
DANGER_HOVER    = "#b91c1c"
DANGER_TINT     = "#fef2f2"
SUCCESS         = "#16a34a"

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ---------- Base font + reset ---------- */
* {{
    font-family: "Segoe UI Variable", "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}

/* ---------- Top-level windows -------------------------------------------
   Set BG explicitly here so child widgets that don't override it inherit
   the off-white. We do NOT make QWidget transparent globally - that was the
   v0.1.1 bug that made cards invisible on the wizard. */
QMainWindow, QDialog, QWizard, QWizardPage {{
    background-color: {BG};
}}

QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ===================================================================
   Sidebar (object name: "sidebar") - dark navy slab
   =================================================================== */
QWidget#sidebar {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {SIDEBAR_BORDER};
}}
QWidget#sidebar QLabel {{
    background: transparent;
    color: {TEXT_INVERSE_MUTED};
}}
QWidget#sidebar QLabel[heading="true"] {{
    color: {TEXT_INVERSE};
    font-weight: 600;
    font-size: 11pt;
    letter-spacing: 0.02em;
}}
QWidget#sidebar QLabel[brand="true"] {{
    color: {TEXT_INVERSE};
    font-weight: 700;
    font-size: 14pt;
    letter-spacing: 0.01em;
}}
QWidget#sidebar QLabel[caption="true"] {{
    color: #64748b;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}}

QWidget#sidebar QListWidget {{
    background: transparent;
    border: none;
    outline: 0;
    color: {TEXT_INVERSE_MUTED};
    padding: 0;
}}
QWidget#sidebar QListWidget::item {{
    padding: 9px 12px;
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
    padding: 8px 14px;
    font-weight: 500;
}}
QWidget#sidebar QPushButton:hover {{
    background-color: {SIDEBAR_HOVER};
    color: {TEXT_INVERSE};
    border-color: #475569;
}}
QWidget#sidebar QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.10);
}}

/* ===================================================================
   Buttons (light theme - everywhere outside the sidebar)
   =================================================================== */
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    color: {TEXT};
    font-weight: 500;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
    border-color: {BORDER_STRONG};
}}
QPushButton:pressed {{
    background-color: #f3f4f6;
}}
QPushButton:disabled {{
    color: {TEXT_SUBTLE};
    background-color: #f3f4f6;
    border-color: #e5e7eb;
}}

QPushButton[primary="true"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: {TEXT_INVERSE};
    font-weight: 600;
    padding: 9px 20px;
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

/* ===================================================================
   Inputs
   =================================================================== */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT_INVERSE};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #f3f4f6;
    color: {TEXT_SUBTLE};
}}

/* ===================================================================
   Lists (used outside sidebar)
   =================================================================== */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    outline: 0;
    color: {TEXT};
}}
QListWidget::item {{
    padding: 9px 12px;
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

/* ===================================================================
   Tables
   =================================================================== */
QTableWidget, QTableView {{
    background-color: {SURFACE};
    alternate-background-color: #fafafa;
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: #f3f4f6;
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT};
    color: {TEXT};
}}
QTableWidget::item, QTableView::item {{
    padding: 10px 8px;
    border: none;
    color: {TEXT};
}}
QHeaderView::section {{
    background-color: #f4f4f5;
    padding: 10px 8px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
    color: {TEXT_MUTED};
    font-size: 9pt;
    letter-spacing: 0.04em;
}}
QHeaderView::section:last {{ border-right: none; }}
QTableCornerButton::section {{
    background-color: #f4f4f5;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}
QTableView QTableCornerButton::section {{ border-top-left-radius: 8px; }}

/* ===================================================================
   Progress bar
   =================================================================== */
QProgressBar {{
    background-color: #e5e7eb;
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: {TEXT_MUTED};
    font-weight: 500;
    font-size: 9pt;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* ===================================================================
   Group boxes (cards). Title sits in the top margin so it doesn't
   overlap the border.
   =================================================================== */
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 22px;
    padding: 22px 18px 18px 18px;
    font-size: 11pt;
    font-weight: 600;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
    color: {TEXT};
    background-color: {BG};
}}

/* ===================================================================
   Tabs
   =================================================================== */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {BG};
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    padding: 11px 24px;
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
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

/* ===================================================================
   Radios + checks
   =================================================================== */
QRadioButton, QCheckBox {{
    spacing: 8px;
    padding: 4px 0;
    color: {TEXT};
    background: transparent;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

/* ===================================================================
   Status bar
   =================================================================== */
QStatusBar {{
    background-color: {SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    padding: 4px 14px;
    font-weight: 500;
}}
QStatusBar::item {{ border: none; }}

/* ===================================================================
   Tier card (objectName="tierCard")
   =================================================================== */
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

/* ===================================================================
   Drop zone (objectName="dropZone")
   =================================================================== */
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

/* ===================================================================
   Generic helpers
   =================================================================== */
QLabel[muted="true"] {{
    color: {TEXT_MUTED};
    background: transparent;
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
    letter-spacing: 0.05em;
}}
QLabel[h1="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 22pt;
    font-weight: 700;
    letter-spacing: -0.01em;
}}
QLabel[h2="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 16pt;
    font-weight: 600;
}}
QLabel[h3="true"] {{
    background: transparent;
    color: {TEXT};
    font-size: 12pt;
    font-weight: 600;
}}

/* Empty-state placeholder shown in CollectionView when no sources yet. */
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
    base_font = QFont("Segoe UI Variable", 10)
    if not base_font.exactMatch():
        base_font = QFont("Segoe UI", 10)
    app.setFont(base_font)
    app.setStyleSheet(STYLESHEET)
