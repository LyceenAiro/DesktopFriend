from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout

from Event.Ai.walk import auto_walk
from ui.PetWindow import PetWindow
from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH, PROB_LABEL_WIDTH, PROB_WIDTH
from ui.setting.tabs.smart.css import PROB_ROW_SPACING, ROW_MARGINS, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from ui.styles.toggle_switch import ToggleSwitch
from util.log import _log
from util.cfg import save_config


class SmartConfigTab(QFrame):
    tab_name = "智能配置"
    can_save = True

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        base_card = create_section_card("基础参数", "控制智能运动触发与移动范围限制")
        base_layout = base_card.layout()
        self.range_spin = self._build_spin_row(base_layout, "范围控制", 1, 8192, PetWindow.max_move_range, " px")
        self.check_spin = self._build_spin_row(base_layout, "检查间隔", 50, 1000, auto_walk.check_time, " ms")
        self.idle_spin = self._build_spin_row(base_layout, "空闲阈值", 1, 300, auto_walk.idle_threshold, " s")

        prob_card = create_section_card("动作权重", "几率总和不能超过 100%")
        prob_layout = prob_card.layout()
        self.left_spin = self._build_weight_row(prob_layout, "左移", auto_walk._walk_left_per)
        self.right_spin = self._build_weight_row(prob_layout, "右移", auto_walk._walk_right_per)
        self.jump_spin = self._build_weight_row(prob_layout, "跳跃", auto_walk._jump_per)

        switch_card = create_section_card("开关", "关闭后仅保留手动交互")
        switch_layout = switch_card.layout()
        self.automove_check = self._build_switch_row(switch_layout, "启用智能运动", PetWindow.AutoMove)

        layout.addWidget(base_card)
        layout.addSpacing(8)
        layout.addWidget(prob_card)
        layout.addSpacing(8)
        layout.addWidget(switch_card)
        layout.addStretch()

    def _build_spin_row(self, parent_layout, title: str, min_v: int, max_v: int, value: int, suffix: str) -> QSpinBox:
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row.addWidget(label)

        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setFixedWidth(INPUT_WIDTH)
        spin.setAlignment(Qt.AlignRight)
        row.addWidget(spin)

        row.addStretch()
        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
        return spin

    def _build_weight_row(self, parent_layout, title: str, value: int) -> QSpinBox:
        row = QHBoxLayout()
        row.setSpacing(PROB_ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(PROB_LABEL_WIDTH)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row.addWidget(label)

        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix(" %")
        spin.setFixedWidth(PROB_WIDTH)
        spin.setAlignment(Qt.AlignRight)
        row.addWidget(spin)

        row.addStretch()
        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
        return spin

    def _build_switch_row(self, parent_layout, title: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row.addWidget(label)

        row.addStretch()
        switch = ToggleSwitch()
        switch.setChecked(checked)
        row.addWidget(switch)

        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
        return switch

    def validate(self):
        total_per = self.left_spin.value() + self.right_spin.value() + self.jump_spin.value()
        if total_per > 100:
            raise ValueError(f"动作权重总和不能超过 100%，当前为 {total_per}%")

    def save_tab(self):
        self.validate()

        PetWindow.max_move_range = self.range_spin.value()
        auto_walk.check_time = self.check_spin.value()
        auto_walk.idle_threshold = self.idle_spin.value()
        auto_walk._walk_left_per = self.left_spin.value()
        auto_walk._walk_right_per = self.right_spin.value()
        auto_walk._jump_per = self.jump_spin.value()
        PetWindow.AutoMove = self.automove_check.isChecked()
        auto_walk.start_timer()

        # 热保存配置到文件
        config = {
            "check_time": auto_walk.check_time,
            "idle_threshold": auto_walk.idle_threshold,
            "max_move_range": PetWindow.max_move_range,
            "walk_left_per": auto_walk._walk_left_per,
            "walk_right_per": auto_walk._walk_right_per,
            "jump_per": auto_walk._jump_per,
            "auto_move": PetWindow.AutoMove,
        }
        save_config("smart", config)

        _log.INFO(
            f"智能配置已保存: 范围={PetWindow.max_move_range}, 检查间隔={auto_walk.check_time}ms, "
            f"空闲阈值={auto_walk.idle_threshold}s, 权重(左/右/跳)="
            f"{auto_walk._walk_left_per}/{auto_walk._walk_right_per}/{auto_walk._jump_per}, "
            f"AutoMove={PetWindow.AutoMove}"
        )
