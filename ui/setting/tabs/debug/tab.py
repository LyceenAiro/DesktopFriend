from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout

from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH
from ui.setting.tabs.debug.css import PREVIEW_ROW_SPACING, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from util.cfg import load_config, save_config
from util.i18n import tr


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
        parent=None,
    ):
        super().__init__(parent)
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

        layout.addWidget(toast_card)
        layout.addWidget(debug_card)
        layout.addWidget(action_card)
        layout.addStretch()

    def save_tab(self):
        """保存调试标签配置"""
        toast_duration_ms = self.toast_duration_spin.value() * 1000
        config = load_config("debug")
        config["toast_duration_ms"] = toast_duration_ms
        save_config("debug", config)
