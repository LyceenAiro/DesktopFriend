from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtWidgets import (
    QFileDialog,
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
        export_callback: Callable[[str], tuple[bool, str]] | None = None,
        import_callback: Callable[[str], tuple[bool, str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._is_enabled_getter = is_enabled_getter
        self._set_enabled_callback = set_enabled_callback
        self._reset_callback = reset_callback
        self._feedback_callback = feedback_callback
        self._is_dead_getter = is_dead_getter
        self._export_callback = export_callback
        self._import_callback = import_callback

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

        # ---- 卡片三：存档管理 ----
        archive_card = create_section_card(
            tr("settings.life.card.archive.title"),
            tr("settings.life.card.archive.desc"),
        )
        archive_layout = archive_card.layout()

        archive_row = QHBoxLayout()
        archive_row.setSpacing(ROW_SPACING)

        self._export_btn = QPushButton(tr("settings.life.export.button"))
        self._export_btn.setMinimumWidth(140)
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(export_callback is not None)
        archive_row.addWidget(self._export_btn)

        self._import_btn = QPushButton(tr("settings.life.import.button"))
        self._import_btn.setMinimumWidth(140)
        self._import_btn.clicked.connect(self._on_import_clicked)
        self._import_btn.setEnabled(import_callback is not None)
        archive_row.addWidget(self._import_btn)

        archive_row.addStretch()
        archive_layout.addLayout(archive_row)

        layout.addWidget(archive_card)
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

    def _on_export_clicked(self) -> None:
        if self._export_callback is None:
            return
        default_name = f"life_save_{date.today().strftime('%Y%m%d')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("settings.life.export.button"),
            default_name,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        ok, err = self._export_callback(file_path)
        if ok:
            self._feedback_callback(tr("settings.life.export.success"), "success")
        else:
            self._feedback_callback(f"{tr('settings.life.export.fail')}: {err}", "error")

    def _on_import_clicked(self) -> None:
        if self._import_callback is None:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.life.import.button"),
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        dlg = ConfirmDialog(
            title=tr("settings.life.import.confirm.title"),
            message=tr("settings.life.import.confirm.message"),
            parent=self,
        )
        if dlg.exec() != ConfirmDialog.Accepted:
            return
        ok, err = self._import_callback(file_path)
        if ok:
            self._feedback_callback(tr("settings.life.import.success"), "success")
        else:
            self._feedback_callback(f"{tr('settings.life.import.fail')}: {err}", "error")

