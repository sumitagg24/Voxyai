"""
Shared design tokens and stylesheet for the Voxylis desktop UI.

Every window imports from here instead of embedding its own colours, so the
app looks like one product and a theme change is a single edit.
"""

from __future__ import annotations

# ── palette ──────────────────────────────────────────────────────────────────

DARK = {
    "bg": "#111114",
    "bg_elevated": "#18181d",
    "bg_input": "#1f1f26",
    "border": "#2c2c35",
    "border_strong": "#3a3a46",
    "text": "#e8e8ee",
    "text_muted": "#9a9aa8",
    "text_dim": "#6b6b7a",
    "accent": "#7c6cf0",
    "accent_hover": "#8d7ff5",
    "accent_soft": "#2a2545",
    "success": "#3ecf8e",
    "warning": "#e8b93b",
    "danger": "#e5484d",
    "danger_hover": "#f2555a",
    "recording": "#ff5c5c",
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
}


def palette(theme: str = "dark") -> dict:
    return dict(LIGHT if (theme or "dark").lower() == "light" else DARK)


def stylesheet(theme: str = "dark") -> str:
    """Return the application-wide Qt stylesheet."""
    c = palette(theme)
    return f"""
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: "Segoe UI", "Inter", system-ui, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background: {c['bg']}; }}

    QLabel#PageTitle {{ font-size: 22px; font-weight: 700; }}
    QLabel#PageSubtitle {{ color: {c['text_muted']}; font-size: 13px; }}
    QLabel#SectionTitle {{ font-size: 14px; font-weight: 600; color: {c['text']}; }}
    QLabel#Hint {{ color: {c['text_muted']}; font-size: 12px; }}
    QLabel#Mono {{ font-family: "Cascadia Code", "Consolas", monospace; font-size: 12px; color: {c['text_muted']}; }}
    QLabel#StatValue {{ font-size: 26px; font-weight: 700; }}
    QLabel#StatLabel {{ color: {c['text_muted']}; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }}
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
        padding: 9px 12px; border-radius: 7px; color: {c['text_muted']}; margin: 1px 0;
    }}
    QListWidget#NavList::item:hover {{ background: {c['bg_input']}; color: {c['text']}; }}
    QListWidget#NavList::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; font-weight: 600; }}

    QPushButton {{
        background: {c['bg_input']}; color: {c['text']}; border: 1px solid {c['border_strong']};
        border-radius: 7px; padding: 8px 16px;
    }}
    QPushButton:hover {{ background: {c['border']}; }}
    QPushButton:disabled {{ color: {c['text_dim']}; border-color: {c['border']}; }}
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
        border-radius: 7px; padding: 7px 10px; selection-background-color: {c['accent']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
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
        background: {c['bg_elevated']}; border: 1px solid {c['border']}; border-radius: 12px;
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
    """


def stat_card(title: str) -> str:
    """Stylesheet snippet for a small metric card."""
    c = palette()
    return f"#Card {{ background: {c['bg_elevated']}; border: 1px solid {c['border']};" f" border-radius: 12px; }}"
