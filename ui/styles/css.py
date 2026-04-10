NAV_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    border: none;
    color: #a6a6a6;
    padding: 10px 12px;
    text-align: left;
    border-radius: 6px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #3a3a3a;
    color: #f5f5f5;
}
QPushButton:pressed {
    background-color: #3a3a3a;
}
"""

NAV_BUTTON_ACTIVE_STYLE = """
QPushButton {
    background-color: #f95f53;
    border: none;
    color: #ffffff;
    padding: 10px 12px;
    text-align: left;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #f95f53;
    color: #ffffff;
}
"""

WINDOW_SHELL_STYLE = (
    "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
)

NAV_FRAME_STYLE = (
    "QFrame { background-color: #1f1f1f; border: none; border-right: 1px solid #3a3a3a; }"
)

SCROLL_AREA_STYLE = """
QScrollArea {
    background-color: #262626;
    border: none;
}
QScrollBar:vertical {
    background-color: rgba(255, 255, 255, 0.04);
    width: 11px;
    border: none;
    border-radius: 5px;
    margin: 6px 2px 6px 2px;
}
QScrollBar::handle:vertical {
    background-color: rgba(245, 245, 245, 0.55);
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(245, 245, 245, 0.8);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

BOTTOM_BAR_STYLE = (
    "QFrame#bottomBar { background-color: #1f1f1f; border-top: 1px solid #3a3a3a; "
    "border-bottom-left-radius: 13px; border-bottom-right-radius: 13px; }"
)

TOP_BAR_STYLE = "QFrame { background-color: transparent; border: none; }"

DIVIDER_STYLE = "QFrame { background-color: #3a3a3a; border: none; }"
