from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QPushButton, QMessageBox, QFrame, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from ui.PetWindow import PetWindow
from ui.styles.toggle_switch import ToggleSwitch
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from Event.Ai.walk import auto_walk
from util.log import _log

LABEL_WIDTH = 148
INPUT_WIDTH = 132
PROB_LABEL_WIDTH = 130
PROB_WIDTH = 132

class SmartConfigWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fitted_once = False
        self.setWindowTitle("智能配置")
        self.setModal(True)
        self.setFixedWidth(680)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(self.window_shell)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 72))
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(
            "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
        )

        layout = QVBoxLayout(self.window_shell)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)

        title_label = QLabel("智能配置")
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        subtitle_label = QLabel("自动行走策略与概率配置")
        subtitle_label.setObjectName("subtitle")
        layout.addWidget(subtitle_label)

        base_card = self._create_section_card("基础参数", "控制智能运动触发时机与可移动范围")
        base_layout = base_card.layout()

        range_layout = QHBoxLayout()
        range_layout.setSpacing(14)
        range_label = QLabel("范围控制")
        range_label.setObjectName("fieldLabel")
        range_label.setFixedWidth(LABEL_WIDTH)
        range_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        range_layout.addWidget(range_label)
        self.range_spin = QSpinBox()
        self.range_spin.setRange(1, 8192)
        self.range_spin.setValue(PetWindow.max_move_range)
        self.range_spin.setSuffix(" px")
        self.range_spin.setFixedWidth(INPUT_WIDTH)
        self.range_spin.setAlignment(Qt.AlignRight)
        range_layout.addWidget(self.range_spin)
        range_layout.addStretch()
        range_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(range_layout)

        check_layout = QHBoxLayout()
        check_layout.setSpacing(14)
        check_label = QLabel("检查间隔")
        check_label.setObjectName("fieldLabel")
        check_label.setFixedWidth(LABEL_WIDTH)
        check_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        check_layout.addWidget(check_label)
        self.check_spin = QSpinBox()
        self.check_spin.setRange(50, 1000)
        self.check_spin.setValue(auto_walk.check_time)
        self.check_spin.setSuffix(" ms")
        self.check_spin.setFixedWidth(INPUT_WIDTH)
        self.check_spin.setAlignment(Qt.AlignRight)
        check_layout.addWidget(self.check_spin)
        check_layout.addStretch()
        check_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(check_layout)

        idle_layout = QHBoxLayout()
        idle_layout.setSpacing(14)
        idle_label = QLabel("空闲阈值")
        idle_label.setObjectName("fieldLabel")
        idle_label.setFixedWidth(LABEL_WIDTH)
        idle_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        idle_layout.addWidget(idle_label)
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(1, 300)
        self.idle_spin.setValue(auto_walk.idle_threshold)
        self.idle_spin.setSuffix(" s")
        self.idle_spin.setFixedWidth(INPUT_WIDTH)
        self.idle_spin.setAlignment(Qt.AlignRight)
        idle_layout.addWidget(self.idle_spin)
        idle_layout.addStretch()
        idle_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(idle_layout)
        layout.addWidget(base_card)
        layout.addSpacing(8)

        prob_card = self._create_section_card("动作权重", "三个几率总和不能超过 100%")
        prob_layout = prob_card.layout()

        prob_layout.addLayout(self._create_weight_row("左移", "left_spin", auto_walk._walk_left_per))
        prob_layout.addLayout(self._create_weight_row("右移", "right_spin", auto_walk._walk_right_per))
        prob_layout.addLayout(self._create_weight_row("跳跃", "jump_spin", auto_walk._jump_per))
        layout.addWidget(prob_card)
        layout.addSpacing(8)

        switch_card = self._create_section_card("开关", "关闭后仅保留手动交互")
        switch_layout = switch_card.layout()

        automove_layout = QHBoxLayout()
        automove_layout.setSpacing(14)
        automove_label = QLabel("启用智能运动")
        automove_label.setObjectName("fieldLabel")
        automove_label.setFixedWidth(LABEL_WIDTH)
        automove_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        automove_layout.addWidget(automove_label)
        automove_layout.addStretch()
        self.automove_check = ToggleSwitch()
        self.automove_check.setChecked(PetWindow.AutoMove)
        automove_layout.addWidget(self.automove_check)
        automove_layout.setContentsMargins(0, 6, 0, 6)
        switch_layout.addLayout(automove_layout)
        layout.addWidget(switch_card)
        layout.addSpacing(6)

        hint_label = QLabel("提示: 概率总和超过 100% 时无法保存。")
        hint_label.setObjectName("helperText")
        layout.addWidget(hint_label)

        layout.addSpacing(10)

        # 保存按钮
        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        save_button = QPushButton("保存")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_settings)
        button_row.addWidget(save_button)

        layout.addLayout(button_row)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted_once:
            self._fit_height_to_content()
            self._fitted_once = True

    def _fit_height_to_content(self):
        self.window_shell.layout().activate()
        hint_height = self.window_shell.sizeHint().height() + 24
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            max_height = int(screen.availableGeometry().height() * 0.9)
            hint_height = min(hint_height, max_height)
        self.setFixedHeight(max(560, hint_height))

    def _create_section_card(self, title: str, hint: str) -> QFrame:
        card = QFrame()
        card.setObjectName("sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)

        section_title = QLabel(title)
        section_title.setObjectName("sectionTitle")
        card_layout.addWidget(section_title)

        section_hint = QLabel(hint)
        section_hint.setObjectName("sectionHint")
        card_layout.addWidget(section_hint)
        return card

    def _create_weight_row(self, label_text: str, spin_attr_name: str, value: int) -> QHBoxLayout:
        row_layout = QHBoxLayout()
        row_layout.setSpacing(16)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(PROB_LABEL_WIDTH)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row_layout.addWidget(label)

        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix(" %")
        spin.setFixedWidth(PROB_WIDTH)
        spin.setAlignment(Qt.AlignRight)
        row_layout.addWidget(spin)
        row_layout.addStretch()
        row_layout.setContentsMargins(0, 6, 0, 6)

        setattr(self, spin_attr_name, spin)
        return row_layout

    def save_settings(self):
        total_per = self.left_spin.value() + self.right_spin.value() + self.jump_spin.value()
        if total_per > 100:
            QMessageBox.warning(
                self,
                "保存失败",
                f"动作几率总和不能超过 100%。当前总和为 {total_per}%"
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