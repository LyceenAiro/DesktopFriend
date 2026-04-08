from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
import traceback
import sys

class ErrorDialog(QDialog):
    def __init__(self, exc_type, exc_value, exc_traceback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("错误")
        self.setModal(True)
        self.setFixedSize(600, 400)

        layout = QVBoxLayout()

        # 错误标题
        title_label = QLabel("发生未处理的错误：")
        title_label.setStyleSheet("font-weight: bold; color: red;")
        layout.addWidget(title_label)

        # 错误信息
        error_text = f"{exc_type.__name__}: {exc_value}"
        error_label = QLabel(error_text)
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        # 详细堆栈跟踪
        stack_label = QLabel("详细堆栈跟踪：")
        layout.addWidget(stack_label)

        stack_text = QTextEdit()
        stack_text.setPlainText("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        stack_text.setReadOnly(True)
        layout.addWidget(stack_text)

        # 按钮布局
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        quit_button = QPushButton("退出程序")
        quit_button.clicked.connect(self.quit_app)
        button_layout.addWidget(quit_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def quit_app(self):
        sys.exit(1)