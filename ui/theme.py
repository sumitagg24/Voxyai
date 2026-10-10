"""
Shared design tokens and stylesheet for the Voxylis desktop UI.
Control Room design system — mirrors web/static/css/base.css.

Every window imports from here instead of embedding its own colours,
so the app looks like one product and a theme change is a single edit.
"""

from __future__ import annotations

# ── palette (Control Room) ──────────────────────────────────────────────────────
# Mirrors web/static/css/base.css tokens

DARK = {
    "bg": "#0e0f12",
    "bg_elevated": "#16181d",
    "bg_input": "#1d2027",
    "border": "#2a2d35",
    "border_strong": "#3a3a46",
    "text": "#eaeaea",
    "text_muted": "#8a8d93",
    "text_dim": "#5b5d6a",
    "accent": "#7c6cf0",
    "accent_hover": "#8d7ff5",
    "accent_soft": "#2a2545",
    "success": "#3ecf8e",
    "warning": "#e8b93b",
    "danger": "#e5484d",
    "danger_hover": "#f2555a",
    "recording": "#ff5c5c",   # ONLY for REC/live/destructive
    "focus": "#ff5c5c",
}

LIGHT = {
    "bg": "#fbfbfd",
    "bg_elevated": "#ffffff",
    "bg_input": "#f2f2f6",
    "border": "#e2e2ea",
    "border_strong": "#cfcfd8",
    "text": "#1a1a20",
    "text_muted": "#5c5c6b",
    "text_dim": "#8a8a99",
    "accent": "#5a4bd1",
    "accent_hover": "#4a3dc0",
    "accent_soft": "#ece9fb",
    "success": "#1f9d63",
    "warning": "#a97c10",
    "danger": "#d13b40",
    "danger_hover": "#b92f34",
    "recording": "#e5484d",
    "focus": "#d13b40",
}


def palette(theme: str = "dark") -> dict:
    return dict(LIGHT if (theme or "dark").lower() == "light" else DARK)


def stylesheet(theme: str = "dark") -> str:
    """Return the application-wide Qt stylesheet (Control Room)."""
    c = palette(theme)
    return f"""
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: "Segoe UI Variable", "Segoe UI", "Inter", system-ui, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background: {c['bg']}; }}

    QLabel#PageTitle {{ font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }}
    QLabel#PageSubtitle {{ color: {c['text_muted']}; font-size: 13px; }}
    QLabel#SectionTitle {{ font-size: 14px; font-weight: 600; color: {c['text']}; }}
    QLabel#Hint {{ color: {c['text_muted']}; font-size: 12px; }}
    QLabel#Mono {{ font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace; font-size: 12px; color: {c['text_muted']}; }}
    QLabel#StatValue {{ font-size: 26px; font-weight: 700; }}
    QLabel#StatLabel {{ color: {c['text_muted']}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }}
    QLabel#BadgeOk {{ color: {c['success']}; font-weight: 600; }}
    QLabel#BadgeWarn {{ color: {c['warning']}; font-weight: 600; }}
    QLabel#BadgeBad {{ color: {c['danger']}; font-weight: 600; }}

    #Sidebar {{ background: {c['bg_elevated']}; border-right: 1px solid {c['border']}; }}
    #SidebarBrand {{ font-size: 16px; font-weight: 700; padding: 18px 18px 6px 18px; }}
    #SidebarVersion {{ color: {c['text_dim']}; font-size: 11px; padding: 0 18px 12px 18px; }}

    QListWidget#NavList {{
        background: transparent; border: none; outline: none; padding: 4px 8px;
    }}
    QListWidget#NavList::item {{
        padding: 9px 12px; border-radius: 6px; color: {c['text_muted']}; margin: 1px 0;
    }}
    QListWidget#NavList::item:hover {{ background: {c['bg_input']}; color: {c['text']}; }}
    QListWidget#NavList::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; font-weight: 600; }}

    QPushButton {{
        background: {c['bg_input']}; color: {c['text']}; border: 1px solid {c['border_strong']};
        border-radius: 6px; padding: 8px 16px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {c['border']}; }}
    QPushButton:disabled {{ color: {c['text_dim']}; border-color: {c['border']}; background: {c['bg_input']}; }}
    QPushButton#Primary {{ background: {c['accent']}; border-color: {c['accent']}; color: #ffffff; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
    QPushButton#Danger {{ background: transparent; border-color: {c['danger']}; color: {c['danger']}; }}
    QPushButton#Danger:hover {{ background: {c['danger']}; color: #ffffff; }}
    QPushButton#Record {{ font-weight: 700; }}
    QPushButton#Record[recording="true"] {{ background: {c['recording']}; border-color: {c['recording']}; color: #ffffff; }}
    QPushButton#Link {{ background: transparent; border: none; color: {c['accent']}; padding: 2px 4px; text-align: left; }}
    QPushButton#Link:hover {{ text-decoration: underline; }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background: {c['bg_input']}; border: 1px solid {c['border_strong']};
        border-radius: 6px; padding: 7px 10px; selection-background-color: {c['accent']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{ border-color: {c['focus']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {c['bg_elevated']}; border: 1px solid {c['border_strong']};
        selection-background-color: {c['accent_soft']}; color: {c['text']};
    }}

    QCheckBox {{ spacing: 9px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px; border-radius: 4px;
        border: 1px solid {c['border_strong']}; background: {c['bg_input']};
    }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}

    #Card {{
        background: {c['bg_elevated']}; border: 1px solid {c['border']}; border-radius: 10px;
    }}
    #Banner {{
        border-radius: 10px; padding: 2px;
        background: {c['bg_elevated']}; border: 1px solid {c['border']};
    }}
    #BannerError {{ border-radius: 10px; background: {c['bg_elevated']}; border: 1px solid {c['danger']}; }}
    #BannerWarn {{ border-radius: 10px; background: {c['bg_elevated']}; border: 1px solid {c['warning']}; }}

    QGroupBox {{
        border: 1px solid {c['border']}; border-radius: 10px; margin-top: 14px; padding: 14px 12px 12px 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {c['text_muted']}; }}

    QTableWidget, QTableView {{
        background: {c['bg_elevated']}; border: 1px solid {c['border']};
        border-radius: 10px; gridline-color: {c['border']};
        selection-background-color: {c['accent_soft']}; selection-color: {c['text']};
    }}
    QHeaderView::section {{
        background: {c['bg_elevated']}; color: {c['text_muted']}; border: none;
        border-bottom: 1px solid {c['border']}; padding: 8px;
    }}

    QListWidget {{
        background: {c['bg_elevated']}; border: 1px solid {c['border']}; border-radius: 10px;
    }}
    QListWidget::item {{ padding: 8px; border-bottom: 1px solid {c['border']}; }}
    QListWidget::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QSlider::groove:horizontal {{ height: 4px; background: {c['border_strong']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 14px; height: 14px; background: {c['accent']}; border-radius: 7px; margin: -5px 0; }}
    QProgressBar {{
        background: {c['bg_input']}; border: 1px solid {c['border']}; border-radius: 6px;
        text-align: center; color: {c['text_muted']};
    }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}
    QToolTip {{
        background: {c['bg_elevated']}; color: {c['text']};
        border: 1px solid {c['border_strong']}; padding: 5px;
    }}
    QStatusBar {{ background: {c['bg_elevated']}; border-top: 1px solid {c['border']}; color: {c['text_muted']}; }}

    /* Lamp motif — REC indicator */
    QLabel#Lamp {{
        border-radius: 50%; border: 1px solid transparent;
        background: {c['border']};
    }}
    QLabel#Lamp[live="true"] {{
        background: {c['recording']};
        border-color: {c['recording']};
        /* Qt doesn't support box-shadow on QLabel; use a styled widget instead for glow */
    }}

    /* Meter / level bar */
    QWidget#MeterBar {{ background: {c['bg_input']}; border-radius: 4px; }}
    QWidget#MeterFill {{ background: {c['recording']}; border-radius: 4px; }}
    """

def stat_card(title: str) -> str:
    """Stylesheet snippet for a small metric card."""
    c = palette()
    return f"#Card {{ background: {c['bg_elevated']}; border: 1px solid {c['border']}; border-radius: 10px; }}"


# ── Component helpers (used by pages.py) ───────────────────────────────────────
def h1(text: str, parent=None) -> "QLabel":
    from PyQt5.QtWidgets import QLabel
    lbl = QLabel(text, parent)
    lbl.setObjectName("PageTitle")
    return lbl

def h2(text: str, parent=None) -> "QLabel":
    from PyQt5.QtWidgets import QLabel
    lbl = QLabel(text, parent)
    lbl.setObjectName("SectionTitle")
    return lbl

def body(text: str, parent=None) -> "QLabel":
    from PyQt5.QtWidgets import QLabel
    lbl = QLabel(text, parent)
    lbl.setWordWrap(True)
    return lbl

def hint(text: str, parent=None) -> "QLabel":
    from PyQt5.QtWidgets import QLabel
    lbl = QLabel(text, parent)
    lbl.setObjectName("Hint")
    return lbl

def mono(text: str, parent=None) -> "QLabel":
    from PyQt5.QtWidgets import QLabel
    lbl = QLabel(text, parent)
    lbl.setObjectName("Mono")
    return lbl

def primary_button(text: str, parent=None) -> "QPushButton":
    from PyQt5.QtWidgets import QPushButton
    btn = QPushButton(text, parent)
    btn.setObjectName("Primary")
    return btn

def danger_button(text: str, parent=None) -> "QPushButton":
    from PyQt5.QtWidgets import QPushButton
    btn = QPushButton(text, parent)
    btn.setObjectName("Danger")
    return btn

def record_button(text: str, parent=None) -> "QPushButton":
    from PyQt5.QtWidgets import QPushButton
    btn = QPushButton(text, parent)
    btn.setObjectName("Record")
    return btn

def link_button(text: str, parent=None) -> "QPushButton":
    from PyQt5.QtWidgets import QPushButton
    btn = QPushButton(text, parent)
    btn.setObjectName("Link")
    return btn

def field_row(label_text: str, widget, parent=None, hint_text: str = "") -> "QWidget":
    """Label + widget + optional hint in a vertical layout."""
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
    row = QWidget(parent)
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(f"font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:{palette()['text_muted']};font-weight:600;")
    layout.addWidget(lbl)
    layout.addWidget(widget)
    if hint_text:
        h = QLabel(hint_text)
        h.setObjectName("Hint")
        layout.addWidget(h)
    return row

def section_frame(parent=None) -> "QFrame":
    """A bordered content frame."""
    from PyQt5.QtWidgets import QFrame
    frame = QFrame(parent)
    frame.setObjectName("Card")
    return frame