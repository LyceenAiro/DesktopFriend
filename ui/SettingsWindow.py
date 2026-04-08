from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QCheckBox, QPushButton
from PySide6.QtCore import Qt

from ui.PetWindow import PetWindow
from Event.Ai.walk import auto_walk
from util.log import _log

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        timer_layout = QHBoxLayout()
        timer_layout.addWidget(QLabel("移动动作间隔(ms):"))
        self.timer_spin = QSpinBox()
        self.timer_spin.setRange(50, 10000)
        self.timer_spin.setValue(PetWindow.move_timer)
        timer_layout.addWidget(self.timer_spin)
        layout.addLayout(timer_layout)

        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def save_settings(self):
        PetWindow.move_timer = self.timer_spin.value()
        _log.INFO(f"设置已保存: 移动动作间隔={PetWindow.move_timer}")
        self.accept()