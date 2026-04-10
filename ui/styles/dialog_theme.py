from PySide6.QtWidgets import QWidget

ADOBE_DIALOG_STYLE = """
QDialog {
    background-color: #262626;
    color: #f0f0f0;
}
QLabel {
    color: #d6d6d6;
    font-size: 13px;
    min-height: 20px;
}
QLabel#title {
    color: #f5f5f5;
    font-size: 22px;
    font-weight: 650;
    min-height: 30px;
}
QLabel#subtitle {
    color: #b8b8b8;
    font-size: 12px;
    min-height: 20px;
}
QLabel#fieldLabel {
    color: #dcdcdc;
    font-size: 13px;
    font-weight: 500;
    min-height: 24px;
}
QLabel#helperText {
    color: #9d9d9d;
    font-size: 11px;
    min-height: 18px;
}
QFrame#sectionCard {
    background-color: #202020;
    border: 1px solid #353535;
    border-radius: 12px;
}
QLabel#sectionTitle {
    color: #f0f0f0;
    font-size: 14px;
    font-weight: 600;
    min-height: 24px;
}
QLabel#sectionHint {
    color: #9f9f9f;
    font-size: 11px;
    min-height: 18px;
}
QSpinBox {
    min-height: 30px;
    color: #f0f0f0;
    background-color: #1f1f1f;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    padding: 3px 8px;
    padding-right: 24px;
    selection-background-color: #4a2220;
}
QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #3c3c3c;
    border-bottom: 1px solid #3c3c3c;
    background-color: #2f2f2f;
    border-top-right-radius: 6px;
}
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #3c3c3c;
    background-color: #2a2a2a;
    border-bottom-right-radius: 6px;
}
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background-color: #3a3a3a;
}
QSpinBox::up-arrow,
QSpinBox::down-arrow {
    width: 10px;
    height: 10px;
}
QTextEdit {
    background-color: #1f1f1f;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    color: #e8e8e8;
    font-size: 12px;
}
QPushButton {
    min-width: 88px;
    min-height: 34px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #d7d7d7;
    background-color: #353535;
    border: 1px solid #4a4a4a;
}
QPushButton:hover {
    background-color: #3d3d3d;
}
QPushButton#primaryButton {
    color: white;
    background-color: #e6453a;
    border: 1px solid #ff776d;
}
QPushButton#primaryButton:hover {
    background-color: #f6574b;
}
"""


def apply_adobe_dialog_theme(widget: QWidget):
    widget.setStyleSheet(ADOBE_DIALOG_STYLE)


def apply_frameless_window_theme(widget: QWidget):
    widget.setStyleSheet(
        widget.styleSheet()
        + """
        QDialog {
            background: transparent;
        }
        QFrame#windowShell {
            background-color: #262626;
            border: 1px solid #3a3a3a;
            border-radius: 14px;
        }
        """
    )
