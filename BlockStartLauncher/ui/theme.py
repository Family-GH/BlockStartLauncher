DARK = {
    "bg": "#0A111C",
    "panel": "#101B2B",
    "panel2": "#17263A",
    "panel3": "#1D3048",
    "accent": "#38BDF8",
    "accent_hover": "#7DD3FC",
    "accent2": "#8B5CF6",
    "text": "#E6EDF7",
    "muted": "#8FA5C2",
    "border": "#2A405D",
    "border_light": "#3B587D",
    "border_dark": "#070C14",
    "on_accent": "#04111F",
    "good": "#4ADE80",
    "warn": "#FACC15",
    "bad": "#FB7185",
}

LIGHT = {
    "bg": "#EEF3F8",
    "panel": "#FFFFFF",
    "panel2": "#E6EEF8",
    "panel3": "#D7E3F2",
    "accent": "#0369A1",
    "accent_hover": "#0284C7",
    "accent2": "#6D28D9",
    "text": "#0F172A",
    "muted": "#536983",
    "border": "#AFC2D8",
    "border_light": "#FFFFFF",
    "border_dark": "#7C93AE",
    "on_accent": "#FFFFFF",
    "good": "#15803D",
    "warn": "#A16207",
    "bad": "#BE123C",
}


def get_stylesheet(theme="dark"):
    palette = LIGHT if str(theme).lower() == "light" else DARK
    bg = palette["bg"]
    panel = palette["panel"]
    panel2 = palette["panel2"]
    panel3 = palette["panel3"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    accent2 = palette["accent2"]
    text = palette["text"]
    muted = palette["muted"]
    border = palette["border"]
    border_light = palette["border_light"]
    border_dark = palette["border_dark"]
    on_accent = palette["on_accent"]
    good = palette["good"]
    warn = palette["warn"]
    bad = palette["bad"]
    return f"""
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: "Microsoft YaHei";
    font-size: 9.5pt;
}}
QMainWindow, QDialog {{ background-color: {bg}; }}
QTabWidget::pane {{
    border: 2px solid {border};
    border-top-color: {border_light};
    border-left-color: {border_light};
    border-radius: 2px;
    background-color: {panel};
    top: -2px;
}}
QTabBar::tab {{
    background: transparent;
    color: {muted};
    padding: 8px 16px;
    margin-right: 3px;
    border-radius: 1px;
}}
QTabBar::tab:selected {{ background-color: {panel2}; color: {accent}; font-weight: 700; }}
QTabBar::tab:hover {{ color: {text}; }}
QPushButton {{
    background-color: {panel2};
    color: {text};
    border: 2px solid {border};
    border-top-color: {border_light};
    border-left-color: {border_light};
    border-bottom-color: {border_dark};
    border-right-color: {border_dark};
    border-radius: 1px;
    min-height: 34px;
    padding: 0 13px;
}}
QPushButton:hover {{ border-color: {accent}; background-color: {panel3}; }}
QPushButton:pressed {{
    background-color: {accent};
    color: {on_accent};
    border-top-color: {border_dark};
    border-left-color: {border_dark};
    border-bottom-color: {border_light};
    border-right-color: {border_light};
}}
QPushButton:disabled {{ color: {muted}; border-color: {border}; background-color: {panel}; }}
QPushButton#PrimaryButton {{
    background-color: {accent};
    color: {on_accent};
    border: 2px solid {accent_hover};
    border-top-color: #BAE6FD;
    border-left-color: #BAE6FD;
    border-bottom-color: #075985;
    border-right-color: #075985;
    font-weight: 700;
}}
QPushButton#PrimaryButton:hover {{ background-color: {accent_hover}; }}
QPushButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {border};
    color: {muted};
}}
QPushButton#GhostButton:hover {{ color: {text}; border-color: {accent}; }}
QPushButton#LaunchButton {{
    background-color: {accent};
    color: {on_accent};
    border: 3px solid {accent_hover};
    border-top-color: #BAE6FD;
    border-left-color: #BAE6FD;
    border-bottom-color: #075985;
    border-right-color: #075985;
    border-radius: 2px;
    font-size: 15pt;
    font-weight: 700;
    min-height: 56px;
}}
QPushButton#LaunchButton:hover {{ background-color: {accent_hover}; }}
QPushButton#DangerButton {{ color: {bad}; }}
QFrame#Sidebar {{
    background-color: {panel};
    border-right: 2px solid {border};
    border-radius: 0;
}}
QPushButton#NavButton {{
    background-color: transparent;
    color: {muted};
    border: none;
    border-left: 4px solid transparent;
    border-radius: 1px;
    min-height: 42px;
    padding: 0 10px;
    text-align: left;
    font-size: 10.5pt;
}}
QPushButton#NavButton:hover {{ background-color: {panel2}; color: {text}; }}
QPushButton#NavButton:checked {{
    background-color: {panel2};
    color: {accent};
    border-left: 4px solid {accent};
    font-weight: 700;
}}
QLabel#AppName {{ font-size: 16pt; font-weight: 700; }}
QLabel#SidebarFooter {{ color: {muted}; font-size: 8.5pt; }}
QLineEdit, QSpinBox, QComboBox {{
    background-color: {panel2};
    color: {text};
    border: 2px solid {border};
    border-top-color: {border_dark};
    border-left-color: {border_dark};
    border-radius: 1px;
    min-height: 31px;
    padding: 0 7px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {panel};
    color: {text};
    border: 2px solid {border};
    selection-background-color: {accent};
    selection-color: {on_accent};
    outline: none;
}}
QListWidget {{
    background-color: {panel2};
    border: 2px solid {border};
    border-radius: 1px;
    padding: 3px;
}}
QListWidget::item {{ border-radius: 0; padding: 7px 8px; }}
QListWidget::item:selected {{ background-color: {accent}; color: {on_accent}; }}
QListWidget::item:hover {{ background-color: {panel3}; }}
QTableWidget {{
    background-color: {panel2};
    alternate-background-color: {panel};
    gridline-color: {border};
    border: 2px solid {border};
    border-radius: 1px;
}}
QTableWidget::item:selected {{ background-color: {accent}; color: {on_accent}; }}
QHeaderView::section {{
    background-color: {panel3};
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px;
}}
QProgressBar {{
    background-color: {bg};
    border: 2px solid {border};
    border-radius: 0;
    height: 12px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 0; }}
QTextEdit, QPlainTextEdit {{
    background-color: {panel2};
    color: {text};
    border: 2px solid {border};
    border-radius: 1px;
    font-family: Consolas, "Microsoft YaHei";
    font-size: 9.5pt;
    padding: 6px;
}}
QScrollArea {{ border: none; background-color: transparent; }}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
QCheckBox {{ spacing: 8px; }}
QGroupBox {{
    background-color: {panel};
    border: 2px solid {border};
    border-top-color: {border_light};
    border-left-color: {border_light};
    border-radius: 1px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {accent};
    font-weight: 700;
}}
QFrame#Card {{
    background-color: {panel};
    border: 2px solid {border};
    border-top-color: {border_light};
    border-left-color: {border_light};
    border-bottom-color: {border_dark};
    border-right-color: {border_dark};
    border-radius: 2px;
}}
QFrame#Card:hover {{ border-color: {accent}; }}
QFrame#HudCard {{
    background-color: {panel2};
    border: 2px solid {border};
    border-radius: 2px;
}}
QLabel#Muted {{ color: {muted}; }}
QLabel#BigTitle {{ font-size: 22pt; font-weight: 700; }}
QLabel#VersionLabel {{ font-size: 12pt; color: {muted}; }}
QLabel#SectionTitle {{ font-size: 11pt; font-weight: 700; color: {text}; }}
QLabel#PixelBadge {{
    background-color: {panel2};
    border: 1px solid {border};
    padding: 2px 7px;
    color: {muted};
    font-size: 8.5pt;
}}
QLabel#StatusGood {{
    background-color: {panel2};
    border-left: 4px solid {good};
    padding: 5px 8px;
    color: {text};
}}
QLabel#StatusWarn {{
    background-color: {panel2};
    border-left: 4px solid {warn};
    padding: 5px 8px;
    color: {text};
}}
QLabel#StatusBad {{
    background-color: {panel2};
    border-left: 4px solid {bad};
    padding: 5px 8px;
    color: {text};
}}
QLabel#UpdateBanner {{
    background-color: {panel2};
    border: 2px solid {accent};
    border-radius: 1px;
    padding: 7px;
}}
QTextEdit#LogView {{
    background-color: {bg};
    border: 2px solid {border};
    border-radius: 1px;
    font-family: Consolas, "Microsoft YaHei";
    font-size: 8.5pt;
}}
QScrollBar:vertical {{
    background: {bg};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {border};
    min-height: 28px;
    border-radius: 0;
    border-left: 1px solid {border_light};
}}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {bg};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    min-width: 28px;
    border-radius: 0;
    border-top: 1px solid {border_light};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{
    background-color: {panel3};
    color: {text};
    border: 1px solid {accent};
    border-radius: 0;
    padding: 4px 7px;
}}
QMenu {{
    background-color: {panel};
    color: {text};
    border: 2px solid {border};
    border-radius: 1px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 0; }}
QMenu::item:selected {{ background-color: {accent}; color: {on_accent}; }}
"""
