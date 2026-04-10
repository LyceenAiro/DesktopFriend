from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout

from ui.setting.common import create_section_card
from ui.setting.constants import INPUT_WIDTH, LABEL_WIDTH
from ui.setting.tabs.debug.css import PREVIEW_ROW_SPACING, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from util.cfg import save_config


class DebugTab(QFrame):
    tab_name = "调试"
    can_save = True

    def __init__(
        self,
        throw_error_callback: Callable[[], None],
        feedback_callback: Callable[[str, str], None],
        duration_changed_callback: Callable[[int], None],
        initial_duration_ms: int,
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        debug_card = create_section_card("调试工具", "用于手动验证异常处理流程")
        debug_layout = debug_card.layout()

        warn_label = QLabel("该操作会主动抛出一个测试异常，请仅在调试时使用。")
        warn_label.setObjectName("helperText")
        debug_layout.addWidget(warn_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(ROW_SPACING)
        action_label = QLabel("异常测试")
        action_label.setObjectName("fieldLabel")
        action_label.setFixedWidth(LABEL_WIDTH)
        action_row.addWidget(action_label)
        error_button = QPushButton("抛出测试错误")
        error_button.setObjectName("primaryButton")
        error_button.setMinimumWidth(160)
        error_button.clicked.connect(throw_error_callback)
        action_row.addWidget(error_button)
        action_row.addStretch()
        debug_layout.addLayout(action_row)

        toast_card = create_section_card("提示动画", "用于预览保存成功/失败提示，并调整停留时长")
        toast_layout = toast_card.layout()

        duration_row = QHBoxLayout()
        duration_row.setSpacing(ROW_SPACING)
        duration_label = QLabel("提示停留时长")
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
        preview_label = QLabel("动画预览")
        preview_label.setObjectName("fieldLabel")
        preview_label.setFixedWidth(LABEL_WIDTH)
        preview_row.addWidget(preview_label)

        preview_success_button = QPushButton("成功提示")
        preview_success_button.clicked.connect(lambda: feedback_callback("已保存", "success"))
        preview_row.addWidget(preview_success_button)

        preview_error_button = QPushButton("失败提示")
        preview_error_button.clicked.connect(
            lambda: feedback_callback("保存失败：这是一个调试提示", "error")
        )
        preview_row.addWidget(preview_error_button)
        preview_row.addStretch()
        toast_layout.addLayout(preview_row)

        layout.addWidget(toast_card)
        layout.addWidget(debug_card)
        layout.addStretch()

    def save_tab(self):
        """保存调试标签配置"""
        toast_duration_ms = self.toast_duration_spin.value() * 1000
        config = {
            "toast_duration_ms": toast_duration_ms,
        }
        save_config("debug", config)
