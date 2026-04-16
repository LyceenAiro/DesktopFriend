from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui.ConfirmDialog import ConfirmDialog
from ui.setting.common import create_section_card
from ui.setting.tabs.life.css import ROW_SPACING, TAB_MARGINS, TAB_SPACING
from ui.styles.toggle_switch import ToggleSwitch
from util.cfg import load_config, save_config
from util.i18n import tr


class LifeManagementTab(QFrame):
    tab_name = tr("settings.tabs.life.name")
    can_save = True

    def __init__(
        self,
        is_enabled_getter: Callable[[], bool],
        set_enabled_callback: Callable[[bool], None],
        reset_callback: Callable[[], None],
        feedback_callback: Callable[[str, str], None],
        is_dead_getter: Callable[[], bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._is_enabled_getter = is_enabled_getter
        self._set_enabled_callback = set_enabled_callback
        self._reset_callback = reset_callback
        self._feedback_callback = feedback_callback
        self._is_dead_getter = is_dead_getter

        life_cfg = load_config("life")
        initial_enabled = bool(life_cfg.get("life_enabled", is_enabled_getter()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        # ---- 卡片一：启用开关 ----
        enabled_card = create_section_card(
            tr("settings.life.card.enabled.title"),
            tr("settings.life.card.enabled.desc"),
        )
        enabled_layout = enabled_card.layout()

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(ROW_SPACING)

        toggle_label = QLabel(tr("settings.life.enabled.label"))
        toggle_label.setObjectName("fieldLabel")
        toggle_row.addWidget(toggle_label)
        toggle_row.addStretch()
        self.enabled_switch = ToggleSwitch()
        self.enabled_switch.setChecked(initial_enabled)
        toggle_row.addWidget(self.enabled_switch)
        enabled_layout.addLayout(toggle_row)

        hint_label = QLabel(tr("settings.life.enabled.hint"))
        hint_label.setObjectName("helperText")
        hint_label.setWordWrap(True)
        enabled_layout.addWidget(hint_label)

        layout.addWidget(enabled_card)

        # ---- 卡片二：重置养成 ----
        reset_card = create_section_card(
            tr("settings.life.card.reset.title"),
            tr("settings.life.card.reset.desc"),
        )
        reset_layout = reset_card.layout()

        warn_label = QLabel(tr("settings.life.reset.warn"))
        warn_label.setObjectName("helperText")
        warn_label.setStyleSheet("color: #e07070;")
        warn_label.setWordWrap(True)
        reset_layout.addWidget(warn_label)

        reset_row = QHBoxLayout()
        reset_row.setSpacing(ROW_SPACING)
        self._reset_btn = QPushButton(tr("settings.life.reset.button"))
        self._reset_btn.setObjectName("primaryButton")
        self._reset_btn.setMinimumWidth(160)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        reset_row.addWidget(self._reset_btn)
        reset_row.addStretch()
        reset_layout.addLayout(reset_row)

        self._dead_warn_label = QLabel(tr("settings.life.reset.dead_warn"))
        self._dead_warn_label.setObjectName("helperText")
        self._dead_warn_label.setStyleSheet("color: #e09050; font-weight: bold;")
        self._dead_warn_label.setWordWrap(True)
        self._dead_warn_label.setVisible(False)
        reset_layout.addWidget(self._dead_warn_label)

        layout.addWidget(reset_card)
        layout.addStretch()

    def save_tab(self) -> None:
        enabled = self.enabled_switch.isChecked()
        save_config("life", {"life_enabled": enabled})
        self._set_enabled_callback(enabled)
        if enabled:
            self._feedback_callback(tr("settings.life.enabled.on"), "success")
        else:
            self._feedback_callback(tr("settings.life.enabled.off"), "info")

    def refresh_state(self) -> None:
        """根据当前死亡状态更新重置区域的高亮提示。"""
        if self._is_dead_getter is None:
            return
        is_dead = bool(self._is_dead_getter())
        self._dead_warn_label.setVisible(is_dead)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh_state()

    def _on_reset_clicked(self) -> None:
        dlg = ConfirmDialog(
            title=tr("settings.life.reset.confirm.title"),
            message=tr("settings.life.reset.confirm.message"),
            parent=self,
        )
        if dlg.exec() == ConfirmDialog.Accepted:
            self._reset_callback()
            self._feedback_callback(tr("settings.life.reset.success"), "success")

