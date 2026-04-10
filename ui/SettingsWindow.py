from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, QPushButton, QFrame, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from ui.PetWindow import PetWindow
from ui.styles.toggle_switch import ToggleSwitch
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from Event.setting.system import AppStayTop
from util.log import _log

LABEL_WIDTH = 138
INPUT_WIDTH = 126

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fitted_once = False
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setFixedWidth(620)
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
        shadow.setBlurRadius(58)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 72))
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(
            "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
        )

        layout = QVBoxLayout(self.window_shell)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)

        title_label = QLabel("设置")
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        subtitle_label = QLabel("基础行为与显示参数")
        subtitle_label.setObjectName("subtitle")
        layout.addWidget(subtitle_label)

        behavior_card = self._create_section_card("动作节奏", "控制移动与待机动画的触发速度")
        behavior_layout = behavior_card.layout()

        timer_layout = QHBoxLayout()
        timer_layout.setSpacing(14)
        timer_label = QLabel("移动动作间隔")
        timer_label.setObjectName("fieldLabel")
        timer_label.setFixedWidth(LABEL_WIDTH)
        timer_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        timer_layout.addWidget(timer_label)
        self.timer_spin = QSpinBox()
        self.timer_spin.setRange(50, 10000)
        self.timer_spin.setValue(PetWindow.move_timer)
        self.timer_spin.setSuffix(" ms")
        self.timer_spin.setFixedWidth(INPUT_WIDTH)
        self.timer_spin.setAlignment(Qt.AlignRight)
        timer_layout.addWidget(self.timer_spin)
        timer_layout.addStretch()
        timer_layout.setContentsMargins(0, 6, 0, 6)
        behavior_layout.addLayout(timer_layout)

        default_timer_layout = QHBoxLayout()
        default_timer_layout.setSpacing(14)
        default_timer_label = QLabel("待机动态间隔")
        default_timer_label.setObjectName("fieldLabel")
        default_timer_label.setFixedWidth(LABEL_WIDTH)
        default_timer_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        default_timer_layout.addWidget(default_timer_label)
        self.default_timer_spin = QSpinBox()
        self.default_timer_spin.setRange(100, 5000)
        self.default_timer_spin.setValue(PetWindow.default_action_interval)
        self.default_timer_spin.setSuffix(" ms")
        self.default_timer_spin.setFixedWidth(INPUT_WIDTH)
        self.default_timer_spin.setAlignment(Qt.AlignRight)
        default_timer_layout.addWidget(self.default_timer_spin)
        default_timer_layout.addStretch()
        default_timer_layout.setContentsMargins(0, 6, 0, 6)
        behavior_layout.addLayout(default_timer_layout)
        layout.addWidget(behavior_card)
        layout.addSpacing(8)

        display_card = self._create_section_card("显示行为", "控制窗口呈现方式与待机开关")
        display_layout = display_card.layout()

        stay_top_layout = QHBoxLayout()
        stay_top_layout.setSpacing(14)
        stay_top_label = QLabel("窗口置顶")
        stay_top_label.setObjectName("fieldLabel")
        stay_top_label.setFixedWidth(LABEL_WIDTH)
        stay_top_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        stay_top_layout.addWidget(stay_top_label)
        stay_top_layout.addStretch()
        self.stay_top_check = ToggleSwitch()
        self.stay_top_check.setChecked(bool(PetWindow.windowFlags() & Qt.WindowStaysOnTopHint))
        stay_top_layout.addWidget(self.stay_top_check)
        stay_top_layout.setContentsMargins(0, 6, 0, 6)
        display_layout.addLayout(stay_top_layout)

        default_action_layout = QHBoxLayout()
        default_action_layout.setSpacing(14)
        default_action_label = QLabel("启用待机动态")
        default_action_label.setObjectName("fieldLabel")
        default_action_label.setFixedWidth(LABEL_WIDTH)
        default_action_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        default_action_layout.addWidget(default_action_label)
        default_action_layout.addStretch()
        self.default_action_check = ToggleSwitch()
        self.default_action_check.setChecked(PetWindow.default_action)
        default_action_layout.addWidget(self.default_action_check)
        default_action_layout.setContentsMargins(0, 6, 0, 6)
        display_layout.addLayout(default_action_layout)
        layout.addWidget(display_card)
        layout.addSpacing(6)

        helper_label = QLabel("提示: 数值越小，动作触发越频繁。")
        helper_label.setObjectName("helperText")
        layout.addWidget(helper_label)

        layout.addSpacing(10)

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
        self.setFixedHeight(max(420, hint_height))

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

    def save_settings(self):
        PetWindow.move_timer = self.timer_spin.value()
        PetWindow.set_default_action_interval(self.default_timer_spin.value())
        AppStayTop(PetWindow, self.stay_top_check)
        PetWindow.set_default_action_enabled(self.default_action_check.isChecked())
        _log.INFO(
            f"设置已保存: 移动动作间隔={PetWindow.move_timer}, 待机动态间隔={PetWindow.default_action_interval}, 置顶={self.stay_top_check.isChecked()}, 待机动态={PetWindow.default_action}"
        )
        self.accept()