from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QListView, QSpinBox, QVBoxLayout, QLabel

from Event.setting.system import AppStayTop
from resources.image_resources import get_resource_pack_name
from ui.PetWindow import PetWindow
from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH
from ui.setting.tabs.basic.css import ROW_MARGINS, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from ui.styles.toggle_switch import ToggleSwitch
from util.log import _log
from util.cfg import load_config, save_config
from util.i18n import get_available_locales, get_locale, tr


class BasicSettingsTab(QFrame):
    tab_name = tr("settings.tabs.basic.name")
    can_save = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self._basic_config = load_config("basic")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        action_card = create_section_card(tr("settings.basic.card.action.title"), tr("settings.basic.card.action.desc"))
        action_layout = action_card.layout()
        self.timer_spin = self._build_spin_row(
            action_layout,
            tr("settings.basic.move_interval"),
            50,
            10000,
            PetWindow.move_timer,
            " ms",
        )
        self.default_timer_spin = self._build_spin_row(
            action_layout,
            tr("settings.basic.idle_interval"),
            100,
            5000,
            PetWindow.default_action_interval,
            " ms",
        )

        display_card = create_section_card(tr("settings.basic.card.display.title"), tr("settings.basic.card.display.desc"))
        display_layout = display_card.layout()
        self.stay_top_check = self._build_switch_row(
            display_layout,
            tr("settings.basic.stay_top"),
            bool(PetWindow.windowFlags() & Qt.WindowStaysOnTopHint),
        )
        self.default_action_check = self._build_switch_row(
            display_layout,
            tr("settings.basic.idle_action"),
            PetWindow.default_action,
        )
        preference_card = create_section_card(
            tr("settings.basic.card.preference.title"),
            tr("settings.basic.card.preference.desc"),
        )
        preference_layout = preference_card.layout()
        self.default_pack_check = self._build_switch_row(
            preference_layout,
            tr("settings.basic.auto_load_pack"),
            bool(self._basic_config.get("auto_load_resource_pack", False)),
        )
        self.locale_combo = self._build_locale_row(preference_layout)

        layout.addWidget(action_card)
        layout.addSpacing(8)
        layout.addWidget(display_card)
        layout.addSpacing(8)
        layout.addWidget(preference_card)
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

    def _build_locale_row(self, parent_layout) -> QComboBox:
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(tr("settings.basic.language"))
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
        row.addWidget(label)

        combo = QComboBox()
        combo.setFixedWidth(INPUT_WIDTH + 36)
        combo.setView(QListView())
        combo.view().setObjectName("localeComboView")
        combo.setStyleSheet(
            """
            QComboBox QAbstractItemView#localeComboView {
                background-color: #1f1f1f;
                border: 1px solid #3c3c3c;
                color: #f0f0f0;
                outline: none;
                padding: 2px;
                selection-background-color: #4a2220;
                selection-color: #ffffff;
            }
            QComboBox QAbstractItemView#localeComboView::item {
                min-height: 24px;
                padding: 4px 8px;
            }
            """
        )

        current_locale = str(self._basic_config.get("locale", get_locale())).strip().lower()
        selected_index = -1

        for idx, (locale_code, display_name) in enumerate(get_available_locales()):
            combo.addItem(display_name, locale_code)
            if locale_code == current_locale:
                selected_index = idx

        if selected_index >= 0:
            combo.setCurrentIndex(selected_index)

        row.addWidget(combo)
        row.addStretch()
        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
        return combo

    def save_tab(self):
        previous_locale = str(self._basic_config.get("locale", get_locale())).strip().lower()
        selected_locale = str(self.locale_combo.currentData() or "zh_cn").strip().lower()

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
            "locale": selected_locale,
        }
        save_config("basic", config)
        self._basic_config = config

        _log.DEBUG(
            f"基础设置已保存: 移动动作间隔={PetWindow.move_timer}ms, "
            f"待机动态间隔={PetWindow.default_action_interval}ms, "
            f"置顶={self.stay_top_check.isChecked()}, 待机动作={PetWindow.default_action}, "
            f"自动加载资源包={self.default_pack_check.isChecked()}"
        )

        if selected_locale != previous_locale:
            return tr("settings.basic.language.restart_required")
        return None
