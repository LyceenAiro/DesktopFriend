from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QCheckBox, QPushButton, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from ui.PetWindow import PetWindow
from Event.Ai.walk import auto_walk
from util.log import _log

class SmartConfigWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("智能配置")
        self.setModal(True)
        self.setFixedSize(300, 300)

        layout = QVBoxLayout()

        # 范围控制
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("范围控制(px):"))
        self.range_spin = QSpinBox()
        self.range_spin.setRange(1, 8192)
        self.range_spin.setValue(PetWindow.max_move_range)
        range_layout.addWidget(self.range_spin)
        layout.addLayout(range_layout)

        # 检查间隔
        check_layout = QHBoxLayout()
        check_layout.addWidget(QLabel("检查间隔(ms):"))
        self.check_spin = QSpinBox()
        self.check_spin.setRange(50, 1000)
        self.check_spin.setValue(auto_walk.check_time)
        check_layout.addWidget(self.check_spin)
        layout.addLayout(check_layout)

        # 空闲阈值
        idle_layout = QHBoxLayout()
        idle_layout.addWidget(QLabel("空闲阈值(秒):"))
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(1, 300)
        self.idle_spin.setValue(auto_walk.idle_threshold)
        idle_layout.addWidget(self.idle_spin)
        layout.addLayout(idle_layout)

        # 左移几率
        left_layout = QHBoxLayout()
        left_layout.addWidget(QLabel("左移几率(%):"))
        self.left_spin = QSpinBox()
        self.left_spin.setRange(0, 100)
        self.left_spin.setValue(auto_walk._walk_left_per)
        left_layout.addWidget(self.left_spin)
        layout.addLayout(left_layout)

        # 右移几率
        right_layout = QHBoxLayout()
        right_layout.addWidget(QLabel("右移几率(%):"))
        self.right_spin = QSpinBox()
        self.right_spin.setRange(0, 100)
        self.right_spin.setValue(auto_walk._walk_right_per)
        right_layout.addWidget(self.right_spin)
        layout.addLayout(right_layout)

        # 跳跃几率
        jump_layout = QHBoxLayout()
        jump_layout.addWidget(QLabel("跳跃几率(%):"))
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(0, 100)
        self.jump_spin.setValue(auto_walk._jump_per)
        jump_layout.addWidget(self.jump_spin)
        layout.addLayout(jump_layout)

        # AutoMove 开关
        self.automove_check = QCheckBox("启用智能运动(测试)")
        self.automove_check.setChecked(PetWindow.AutoMove)
        layout.addWidget(self.automove_check)

        # 保存按钮
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def _highlight_invalid(self, widget):
        palette = widget.palette()
        palette.setColor(QPalette.Base, QColor(255, 180, 180))
        widget.setPalette(palette)

    def _clear_highlight(self):
        for widget in [self.left_spin, self.right_spin, self.jump_spin]:
            widget.setPalette(self.palette())

    def save_settings(self):
        self._clear_highlight()
        total_per = self.left_spin.value() + self.right_spin.value() + self.jump_spin.value()
        if total_per > 100:
            self._highlight_invalid(self.left_spin)
            self._highlight_invalid(self.right_spin)
            self._highlight_invalid(self.jump_spin)
            QMessageBox.warning(
                self,
                "保存失败",
                f"动作几率总和不能超过 100%。当前总和为 {total_per}%，请调整后重试。"
            )
            return

        self._clear_highlight()
        total_per = self.left_spin.value() + self.right_spin.value() + self.jump_spin.value()
        if total_per > 100:
            self._highlight_invalid(self.left_spin)
            self._highlight_invalid(self.right_spin)
            self._highlight_invalid(self.jump_spin)
            QMessageBox.warning(
                self,
                "保存失败",
                f"动作几率总和不能超过 100%。当前总和为 {total_per}%，请调整后重试。"
            )
            return
        PetWindow.max_move_range = self.range_spin.value()
        auto_walk.check_time = self.check_spin.value()
        auto_walk.idle_threshold = self.idle_spin.value()
        auto_walk._walk_left_per = self.left_spin.value()
        auto_walk._walk_right_per = self.right_spin.value()
        auto_walk._jump_per = self.jump_spin.value()
        PetWindow.AutoMove = self.automove_check.isChecked()
        # 重新启动定时器以应用新间隔
        auto_walk.start_timer()
        _log.INFO(f"智能配置已保存: 范围={PetWindow.max_move_range}, 检查间隔={auto_walk.check_time}, 空闲阈值={auto_walk.idle_threshold}, 左移={auto_walk._walk_left_per}, 右移={auto_walk._walk_right_per}, 跳跃={auto_walk._jump_per}, AutoMove={PetWindow.AutoMove}")
        self.accept()