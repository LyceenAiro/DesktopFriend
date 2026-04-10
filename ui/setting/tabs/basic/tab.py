from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSpinBox, QVBoxLayout, QLabel

from Event.setting.system import AppStayTop
from resources.image_resources import get_resource_pack_name
from ui.PetWindow import PetWindow
from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH
from ui.setting.tabs.basic.css import ROW_MARGINS, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from ui.styles.toggle_switch import ToggleSwitch
from util.log import _log
from util.cfg import load_config, save_config


class BasicSettingsTab(QFrame):
    tab_name = "基础设置"
    can_save = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self._basic_config = load_config("basic")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        action_card = create_section_card("动作节奏", "调整宠物运动的频率")
        action_layout = action_card.layout()
        self.timer_spin = self._build_spin_row(
            action_layout,
            "移动动作间隔",
            50,
            10000,
            PetWindow.move_timer,
            " ms",
        )
        self.default_timer_spin = self._build_spin_row(
            action_layout,
            "待机动态间隔",
            100,
            5000,
            PetWindow.default_action_interval,
            " ms",
        )

        display_card = create_section_card("显示行为", "控制宠物窗口的显示方式")
        display_layout = display_card.layout()
        self.stay_top_check = self._build_switch_row(
            display_layout,
            "窗口置顶",
            bool(PetWindow.windowFlags() & Qt.WindowStaysOnTopHint),
        )
        self.default_action_check = self._build_switch_row(
            display_layout,
            "待机动作",
            PetWindow.default_action,
        )
        self.default_pack_check = self._build_switch_row(
            display_layout,
            "默认自动加载资源包",
            bool(self._basic_config.get("auto_load_resource_pack", False)),
        )

        layout.addWidget(action_card)
        layout.addSpacing(8)
        layout.addWidget(display_card)
        layout.addStretch()

    def _build_spin_row(
        self,
        parent_layout,
        title: str,
        min_v: int,
        max_v: int,
        value: int,
        suffix: str,
    ) -> QSpinBox:
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
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

    def _build_switch_row(self, parent_layout, title: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
        row.addWidget(label)

        row.addStretch()
        switch = ToggleSwitch()
        switch.setChecked(checked)
        row.addWidget(switch)

        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
        return switch

    def save_tab(self):
        PetWindow.move_timer = self.timer_spin.value()
        PetWindow.set_default_action_interval(self.default_timer_spin.value())
        AppStayTop(PetWindow, self.stay_top_check)
        PetWindow.set_default_action_enabled(self.default_action_check.isChecked())

        # 热保存配置到文件
        config = {
            "move_timer": PetWindow.move_timer,
            "default_action_interval": PetWindow.default_action_interval,
            "stay_top": self.stay_top_check.isChecked(),
            "default_action": PetWindow.default_action,
            "auto_load_resource_pack": self.default_pack_check.isChecked(),
            "default_resource_pack": get_resource_pack_name(),
        }
        save_config("basic", config)

        _log.INFO(
            f"基础设置已保存: 移动动作间隔={PetWindow.move_timer}ms, "
            f"待机动态间隔={PetWindow.default_action_interval}ms, "
            f"置顶={self.stay_top_check.isChecked()}, 待机动作={PetWindow.default_action}, "
            f"自动加载资源包={self.default_pack_check.isChecked()}"
        )
