from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout

from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH
from ui.setting.tabs.debug.css import PREVIEW_ROW_SPACING, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from util.cfg import load_config, save_config
from util.i18n import tr
from util.log import _log


class DebugTab(QFrame):
    tab_name = tr("settings.tabs.debug.name")
    can_save = True

    def __init__(
        self,
        throw_error_callback: Callable[[], None],
        feedback_callback: Callable[[str, str], None],
        duration_changed_callback: Callable[[int], None],
        initial_duration_ms: int,
        move_left_callback: Callable[[int], None],
        move_right_callback: Callable[[int], None],
        jump_callback: Callable[[], None],
        hide_callback: Callable[[], None],
        show_app_callback: Callable[[], None],
        open_life_debug_callback: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        debug_config = load_config("debug")
        initial_log_level = str(debug_config.get("log_level", "INFO")).strip().upper()
        initial_log_size_mb = int(debug_config.get("log_max_file_size_mb", 32) or 32)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        debug_card = create_section_card(tr("settings.debug.card.tools.title"), tr("settings.debug.card.tools.desc"))
        debug_layout = debug_card.layout()

        warn_label = QLabel(tr("settings.debug.warn"))
        warn_label.setObjectName("helperText")
        debug_layout.addWidget(warn_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(ROW_SPACING)
        action_label = QLabel(tr("settings.debug.test_exception"))
        action_label.setObjectName("fieldLabel")
        action_label.setFixedWidth(LABEL_WIDTH)
        action_row.addWidget(action_label)
        error_button = QPushButton(tr("settings.debug.throw_exception"))
        error_button.setObjectName("primaryButton")
        error_button.setMinimumWidth(160)
        error_button.clicked.connect(throw_error_callback)
        action_row.addWidget(error_button)
        action_row.addStretch()
        debug_layout.addLayout(action_row)

        toast_card = create_section_card(tr("settings.debug.card.toast.title"), tr("settings.debug.card.toast.desc"))
        toast_layout = toast_card.layout()

        duration_row = QHBoxLayout()
        duration_row.setSpacing(ROW_SPACING)
        duration_label = QLabel(tr("settings.debug.toast_duration"))
        duration_label.setObjectName("fieldLabel")
        duration_label.setFixedWidth(LABEL_WIDTH)
        duration_row.addWidget(duration_label)
        self.toast_duration_spin = QSpinBox()
        self.toast_duration_spin.setRange(1, 60)
        self.toast_duration_spin.setValue(initial_duration_ms // 1000)
        self.toast_duration_spin.setSuffix(" s")
        self.toast_duration_spin.setFixedWidth(INPUT_WIDTH)
        self.toast_duration_spin.setAlignment(Qt.AlignRight)
        self.toast_duration_spin.valueChanged.connect(duration_changed_callback)
        duration_row.addWidget(self.toast_duration_spin)
        duration_row.addStretch()
        toast_layout.addLayout(duration_row)

        level_row = QHBoxLayout()
        level_row.setSpacing(ROW_SPACING)
        level_label = QLabel(tr("settings.debug.log_level"))
        level_label.setObjectName("fieldLabel")
        level_label.setFixedWidth(LABEL_WIDTH)
        level_row.addWidget(level_label)
        self.log_level_combo = QComboBox()
        self.log_level_combo.setFixedWidth(INPUT_WIDTH)
        self.log_level_combo.addItem(tr("settings.debug.log_level.debug"), "DEBUG")
        self.log_level_combo.addItem(tr("settings.debug.log_level.info"), "INFO")
        self.log_level_combo.addItem(tr("settings.debug.log_level.warn"), "WARN")
        self.log_level_combo.addItem(tr("settings.debug.log_level.error"), "ERROR")
        level_index = self.log_level_combo.findData(initial_log_level)
        if level_index < 0:
            level_index = self.log_level_combo.findData("INFO")
        if level_index >= 0:
            self.log_level_combo.setCurrentIndex(level_index)
        level_row.addWidget(self.log_level_combo)
        level_row.addStretch()
        toast_layout.addLayout(level_row)

        size_row = QHBoxLayout()
        size_row.setSpacing(ROW_SPACING)
        size_label = QLabel(tr("settings.debug.log_max_size"))
        size_label.setObjectName("fieldLabel")
        size_label.setFixedWidth(LABEL_WIDTH)
        size_row.addWidget(size_label)
        self.log_size_spin = QSpinBox()
        self.log_size_spin.setRange(1, 1024)
        self.log_size_spin.setValue(max(1, initial_log_size_mb))
        self.log_size_spin.setSuffix(" MB")
        self.log_size_spin.setFixedWidth(INPUT_WIDTH)
        self.log_size_spin.setAlignment(Qt.AlignRight)
        size_row.addWidget(self.log_size_spin)
        size_row.addStretch()
        toast_layout.addLayout(size_row)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(PREVIEW_ROW_SPACING)
        preview_label = QLabel(tr("settings.debug.preview"))
        preview_label.setObjectName("fieldLabel")
        preview_label.setFixedWidth(LABEL_WIDTH)
        preview_row.addWidget(preview_label)

        preview_success_button = QPushButton(tr("settings.debug.preview_success"))
        preview_success_button.clicked.connect(lambda: feedback_callback(tr("settings.window.feedback.saved"), "success"))
        preview_row.addWidget(preview_success_button)

        preview_error_button = QPushButton(tr("settings.debug.preview_error"))
        preview_error_button.clicked.connect(
            lambda: feedback_callback(tr("settings.debug.preview_error_msg"), "error")
        )
        preview_row.addWidget(preview_error_button)
        preview_row.addStretch()
        toast_layout.addLayout(preview_row)

        action_card = create_section_card(tr("settings.debug.card.action.title"), tr("settings.debug.card.action.desc"))
        action_layout = action_card.layout()

        move_count_row = QHBoxLayout()
        move_count_row.setSpacing(ROW_SPACING)
        move_count_label = QLabel(tr("settings.debug.move_count"))
        move_count_label.setObjectName("fieldLabel")
        move_count_label.setFixedWidth(LABEL_WIDTH)
        move_count_row.addWidget(move_count_label)
        self.move_count_spin = QSpinBox()
        self.move_count_spin.setRange(1, 999)
        self.move_count_spin.setValue(8)
        self.move_count_spin.setFixedWidth(INPUT_WIDTH)
        self.move_count_spin.setAlignment(Qt.AlignRight)
        move_count_row.addWidget(self.move_count_spin)
        move_count_row.addStretch()
        action_layout.addLayout(move_count_row)

        move_row = QHBoxLayout()
        move_row.setSpacing(PREVIEW_ROW_SPACING)
        move_label = QLabel(tr("settings.debug.walk"))
        move_label.setObjectName("fieldLabel")
        move_label.setFixedWidth(LABEL_WIDTH)
        move_row.addWidget(move_label)

        move_left_button = QPushButton(tr("settings.debug.walk_left"))
        move_left_button.clicked.connect(
            lambda: move_left_callback(int(self.move_count_spin.value()))
        )
        move_row.addWidget(move_left_button)

        move_right_button = QPushButton(tr("settings.debug.walk_right"))
        move_right_button.clicked.connect(
            lambda: move_right_callback(int(self.move_count_spin.value()))
        )
        move_row.addWidget(move_right_button)
        move_row.addStretch()
        action_layout.addLayout(move_row)

        quick_action_row = QHBoxLayout()
        quick_action_row.setSpacing(PREVIEW_ROW_SPACING)
        quick_action_label = QLabel(tr("settings.debug.quick_action"))
        quick_action_label.setObjectName("fieldLabel")
        quick_action_label.setFixedWidth(LABEL_WIDTH)
        quick_action_row.addWidget(quick_action_label)

        jump_button = QPushButton(tr("settings.debug.jump"))
        jump_button.clicked.connect(jump_callback)
        quick_action_row.addWidget(jump_button)

        hide_button = QPushButton(tr("settings.debug.hide"))
        hide_button.clicked.connect(hide_callback)
        quick_action_row.addWidget(hide_button)

        show_button = QPushButton(tr("settings.debug.show"))
        show_button.clicked.connect(show_app_callback)
        quick_action_row.addWidget(show_button)
        quick_action_row.addStretch()
        action_layout.addLayout(quick_action_row)

        # ---- 动作系统选择器 ---- #
        action_selector_row = QHBoxLayout()
        action_selector_row.setSpacing(PREVIEW_ROW_SPACING)
        action_selector_label = QLabel(tr("settings.debug.action.selector"))
        action_selector_label.setObjectName("fieldLabel")
        action_selector_label.setFixedWidth(LABEL_WIDTH)
        action_selector_row.addWidget(action_selector_label)

        self.action_combo = QComboBox()
        self.action_combo.setFixedWidth(INPUT_WIDTH + 80)
        self.action_combo.addItem(tr("settings.debug.action.select_hint"), "")
        # 填充所有已注册动作
        self._refresh_action_combo()

        action_selector_row.addWidget(self.action_combo)

        trigger_btn = QPushButton(tr("settings.debug.action.trigger"))
        trigger_btn.clicked.connect(self._trigger_selected_action)
        action_selector_row.addWidget(trigger_btn)

        stop_btn = QPushButton(tr("settings.debug.action.stop"))
        stop_btn.clicked.connect(self._stop_selected_action)
        action_selector_row.addWidget(stop_btn)

        action_selector_row.addStretch()
        action_layout.addLayout(action_selector_row)

        # ---- 休眠模式卡片 -------------------------------------------------- #
        debug_config2 = load_config("debug")
        initial_normal_tick_s = int(debug_config2.get("life_tick_interval_ms", 1000)) // 1000
        initial_afk_tick_s = int(debug_config2.get("life_afk_tick_interval_ms", 5000)) // 1000
        initial_afk_timeout_s = int(debug_config2.get("life_afk_timeout_s", 3600)) // 60  # 显示为分钟

        hibernate_card = create_section_card(
            tr("settings.debug.card.hibernate.title"),
            tr("settings.debug.card.hibernate.desc"),
        )
        hibernate_layout = hibernate_card.layout()

        normal_tick_row = QHBoxLayout()
        normal_tick_row.setSpacing(ROW_SPACING)
        normal_tick_label = QLabel(tr("settings.debug.tick_interval_normal"))
        normal_tick_label.setObjectName("fieldLabel")
        normal_tick_label.setFixedWidth(LABEL_WIDTH)
        normal_tick_row.addWidget(normal_tick_label)
        self.normal_tick_spin = QSpinBox()
        self.normal_tick_spin.setRange(1, 60)
        self.normal_tick_spin.setValue(max(1, initial_normal_tick_s))
        self.normal_tick_spin.setSuffix(" s")
        self.normal_tick_spin.setFixedWidth(INPUT_WIDTH)
        self.normal_tick_spin.setAlignment(Qt.AlignRight)
        normal_tick_row.addWidget(self.normal_tick_spin)
        normal_tick_row.addStretch()
        hibernate_layout.addLayout(normal_tick_row)

        afk_tick_row = QHBoxLayout()
        afk_tick_row.setSpacing(ROW_SPACING)
        afk_tick_label = QLabel(tr("settings.debug.tick_interval_afk"))
        afk_tick_label.setObjectName("fieldLabel")
        afk_tick_label.setFixedWidth(LABEL_WIDTH)
        afk_tick_row.addWidget(afk_tick_label)
        self.afk_tick_spin = QSpinBox()
        self.afk_tick_spin.setRange(1, 600)
        self.afk_tick_spin.setValue(max(1, initial_afk_tick_s))
        self.afk_tick_spin.setSuffix(" s")
        self.afk_tick_spin.setFixedWidth(INPUT_WIDTH)
        self.afk_tick_spin.setAlignment(Qt.AlignRight)
        afk_tick_row.addWidget(self.afk_tick_spin)
        afk_tick_row.addStretch()
        hibernate_layout.addLayout(afk_tick_row)

        afk_timeout_row = QHBoxLayout()
        afk_timeout_row.setSpacing(ROW_SPACING)
        afk_timeout_label = QLabel(tr("settings.debug.afk_timeout"))
        afk_timeout_label.setObjectName("fieldLabel")
        afk_timeout_label.setFixedWidth(LABEL_WIDTH)
        afk_timeout_row.addWidget(afk_timeout_label)
        self.afk_timeout_spin = QSpinBox()
        self.afk_timeout_spin.setRange(1, 1440)
        self.afk_timeout_spin.setValue(max(1, initial_afk_timeout_s))
        self.afk_timeout_spin.setSuffix(" min")
        self.afk_timeout_spin.setFixedWidth(INPUT_WIDTH)
        self.afk_timeout_spin.setAlignment(Qt.AlignRight)
        afk_timeout_row.addWidget(self.afk_timeout_spin)
        afk_timeout_row.addStretch()
        hibernate_layout.addLayout(afk_timeout_row)

        layout.addWidget(hibernate_card)
        layout.addStretch()

        # 扩展调试，放在调试标签最后一项

        expansion_card = create_section_card(
            tr("settings.debug.card.expansion.title"),
            tr("settings.debug.card.expansion.desc"),
        )
        expansion_layout = expansion_card.layout()

        life_row = QHBoxLayout()
        life_row.setSpacing(PREVIEW_ROW_SPACING)
        life_label = QLabel(tr("settings.debug.life", "养成窗口"))
        life_label.setObjectName("fieldLabel")
        life_label.setFixedWidth(LABEL_WIDTH)
        life_row.addWidget(life_label)

        life_debug_btn = QPushButton(tr("settings.debug.life_debug", "打开养成调试"))
        life_debug_btn.clicked.connect(open_life_debug_callback)
        life_row.addWidget(life_debug_btn)
        life_row.addStretch()
        expansion_layout.addLayout(life_row)


        layout.addWidget(toast_card)
        layout.addWidget(debug_card)
        layout.addWidget(action_card)
        layout.addWidget(expansion_card)

    def save_tab(self):
        """保存调试标签配置"""
        toast_duration_ms = self.toast_duration_spin.value() * 1000
        config = load_config("debug")
        config["toast_duration_ms"] = toast_duration_ms
        config["log_level"] = str(self.log_level_combo.currentData() or "INFO").upper()
        config["log_max_file_size_mb"] = max(1, int(self.log_size_spin.value()))
        config["life_tick_interval_ms"] = max(100, self.normal_tick_spin.value() * 1000)
        config["life_afk_tick_interval_ms"] = max(100, self.afk_tick_spin.value() * 1000)
        config["life_afk_timeout_s"] = max(60, self.afk_timeout_spin.value() * 60)
        save_config("debug", config)

        # 立即应用新的 tick 间隔和 AFK 超时
        from module.life.runtime import configure_tick_intervals
        from util.idle_monitor import IdleMonitor
        configure_tick_intervals(
            config["life_tick_interval_ms"],
            config["life_afk_tick_interval_ms"],
        )
        IdleMonitor.reconfigure(config["life_afk_timeout_s"])

        return tr("settings.debug.saved")

    def _get_action_system(self):
        try:
            from module.default.action import get_action_system
            return get_action_system()
        except Exception:
            return None

    def _refresh_action_combo(self):
        """刷新动作下拉框内容。"""
        # 保留当前选中项
        current_id = self.action_combo.currentData()
        self.action_combo.clear()
        self.action_combo.addItem(tr("settings.debug.action.select_hint"), "")

        asys = self._get_action_system()
        if asys is None:
            return

        # 分组：原版动画 vs 自定义动作
        vanilla_items = []
        custom_items = []
        for action_id in asys.get_all_action_ids():
            record = asys.action_registry.get(action_id)
            if not record:
                continue
            display = f"{record.name} ({action_id})"
            if record.is_vanilla:
                vanilla_items.append((display, action_id))
            else:
                custom_items.append((display, action_id))

        if vanilla_items:
            self.action_combo.insertSeparator(self.action_combo.count())
            for display, aid in vanilla_items:
                self.action_combo.addItem(display, aid)

        if custom_items:
            self.action_combo.insertSeparator(self.action_combo.count())
            for display, aid in custom_items:
                self.action_combo.addItem(display, aid)

        # 恢复选中项
        idx = self.action_combo.findData(current_id)
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)

    def _trigger_selected_action(self):
        """触发下拉框选中的动作。"""
        action_id = self.action_combo.currentData()
        if not action_id or not isinstance(action_id, str):
            return
        asys = self._get_action_system()
        if asys:
            asys.trigger_action(action_id)
            _log.INFO(f"[Debug]手动触发动作: {action_id}")

    def _stop_selected_action(self):
        """停止下拉框选中的动作。"""
        action_id = self.action_combo.currentData()
        if not action_id or not isinstance(action_id, str):
            return
        asys = self._get_action_system()
        if asys:
            asys.stop_action(action_id)
            _log.INFO(f"[Debug]手动停止动作: {action_id}")
