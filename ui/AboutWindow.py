from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from util.version import version

class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setModal(True)
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        title_label = QLabel("DesktopFriend")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        version_label = QLabel(f"v{version}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        author_label = QLabel("LyceenAiro@2026")
        author_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(author_label)

        link_label = QLabel("github.com/LyceenAiro/DesktopFriend")
        link_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(link_label)

        self.setLayout(layout)