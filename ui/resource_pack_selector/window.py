from pathlib import Path
import base64
import json
import shutil

from PySide6.QtCore import Qt, QTimer, QEvent, QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QDialog,
)
from resources.image_resources import get_available_resource_packs, get_resource_pack_display_name
from util.log import _log
from ui.ConfirmDialog import ConfirmDialog
from ui.resource_pack_selector.css import LIST_CONTAINER_DRAG_STYLE, RESOURCE_PACK_SELECTOR_STYLE
from ui.resource_pack_selector.list_item import ResourcePackListItem
from util.i18n import tr


class ResourcePackSelector(QDialog):
    def __init__(self, resource_packs, parent=None):
        super().__init__(parent)
        self.resource_packs = list(resource_packs)
        self.selected_pack = None
        self._known_pack_files = []
        self.remember_as_default = False

        self.setWindowTitle(tr("resource_selector.title"))
        self.setModal(True)
        self.resize(920, 620)
        self.setMinimumSize(920, 620)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        self._init_ui()
        self._load_resource_pack_items()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self._refresh_resource_packs)
        self.refresh_timer.start()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        root_layout.addWidget(self.window_shell)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(62)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 72))
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(
            "QFrame#windowShell { background-color: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 16px; }"
        )

        shell_layout = QHBoxLayout(self.window_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(28, 32, 28, 32)
        left_layout.setSpacing(14)

        brand_label = QLabel("DesktopFriend")
        brand_label.setObjectName("brandTitle")
        left_layout.addWidget(brand_label)

        subtitle_label = QLabel("Particles Furry")
        subtitle_label.setObjectName("brandSubtitle")
        left_layout.addWidget(subtitle_label)

        desc_label = QLabel(tr("resource_selector.desc"))
        desc_label.setWordWrap(True)
        desc_label.setObjectName("brandDescription")
        left_layout.addWidget(desc_label)

        left_layout.addStretch()

        hint_label = QLabel(tr("resource_selector.tip"))
        hint_label.setObjectName("brandHint")
        left_layout.addWidget(hint_label)

        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(26, 28, 26, 24)
        right_layout.setSpacing(12)

        title_label = QLabel(tr("resource_selector.title"))
        title_label.setObjectName("title")
        right_layout.addWidget(title_label)

        # ── 标签切换栏 ──────────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(6)
        self.tab_resource_btn = QPushButton(tr("resource_selector.tab.resource_pack"))
        self.tab_resource_btn.clicked.connect(lambda: self._switch_tab(0))
        self.tab_mod_btn = QPushButton(tr("resource_selector.tab.mod_manager"))
        self.tab_mod_btn.clicked.connect(lambda: self._switch_tab(1))
        tab_row.addWidget(self.tab_resource_btn)
        tab_row.addWidget(self.tab_mod_btn)
        tab_row.addStretch()
        right_layout.addLayout(tab_row)

        # ── 资源包选择页 ────────────────────────────────────────────────
        self.resource_pack_page = QFrame()
        rp_layout = QVBoxLayout(self.resource_pack_page)
        rp_layout.setContentsMargins(0, 0, 0, 0)
        rp_layout.setSpacing(12)

        self.info_label = QLabel("")
        self.info_label.setObjectName("info")
        rp_layout.addWidget(self.info_label)

        self.preview_label = QLabel(tr("resource_selector.preview.none"))
        self.preview_label.setObjectName("previewBox")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(156)
        rp_layout.addWidget(self.preview_label)

        self.pack_list = QListWidget()
        self.pack_list.setObjectName("packList")
        self.pack_list.setMinimumHeight(160)
        self.pack_list.setAcceptDrops(True)
        self.pack_list.itemSelectionChanged.connect(self._on_pack_selected)
        self.pack_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.list_container = QFrame()
        self.list_container.setObjectName("listContainer")
        list_container_layout = QVBoxLayout(self.list_container)
        list_container_layout.setContentsMargins(0, 0, 0, 0)
        list_container_layout.setSpacing(0)
        list_container_layout.addWidget(self.pack_list, 1)

        rp_layout.addWidget(self.list_container, 1)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        self.default_check = QCheckBox(tr("resource_selector.checkbox.default"))
        self.default_check.setObjectName("rememberCheck")
        footer_row.addWidget(self.default_check)
        footer_row.addStretch()

        cancel_button = QPushButton(tr("resource_selector.exit"))
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        footer_row.addWidget(cancel_button)

        self.start_button = QPushButton(tr("resource_selector.start"))
        self.start_button.setObjectName("primaryButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._accept_selection)
        footer_row.addWidget(self.start_button)

        rp_layout.addLayout(footer_row)

        right_layout.addWidget(self.resource_pack_page, 1)

        # ── Mod 管理页 ──────────────────────────────────────────────────
        from ui.resource_pack_selector.mod_tab import ModManagerTab
        self.mod_manager_page = ModManagerTab()
        self.mod_manager_page.setVisible(False)
        self.mod_manager_page.exit_requested.connect(self.reject)
        self.mod_manager_page.start_requested.connect(self._accept_selection)
        right_layout.addWidget(self.mod_manager_page, 1)

        # 初始化标签样式
        self._switch_tab(0)

        shell_layout.addWidget(left_panel, 10)
        shell_layout.addWidget(right_panel, 14)

        self._drag_widgets = [
            left_panel,
            brand_label,
            subtitle_label,
            desc_label,
            hint_label,
            title_label,
        ]
        for widget in self._drag_widgets:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

        self.setStyleSheet(RESOURCE_PACK_SELECTOR_STYLE)

    # ── 标签切换 ──────────────────────────────────────────────────────────

    _TAB_ACTIVE_STYLE = (
        "QPushButton { background-color: #0078d4; color: #ffffff; "
        "border: none; border-radius: 6px; padding: 4px 14px; "
        "font-size: 12px; font-weight: 600; }"
        "QPushButton:hover { background-color: #1a86d9; }"
    )
    _TAB_INACTIVE_STYLE = (
        "QPushButton { background-color: #2d2d2d; color: #cccccc; "
        "border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 14px; "
        "font-size: 12px; }"
        "QPushButton:hover { background-color: #383838; }"
    )

    def _switch_tab(self, index: int) -> None:
        is_resource = (index == 0)
        self.resource_pack_page.setVisible(is_resource)
        self.mod_manager_page.setVisible(not is_resource)
        self.tab_resource_btn.setStyleSheet(
            self._TAB_ACTIVE_STYLE if is_resource else self._TAB_INACTIVE_STYLE
        )
        self.tab_mod_btn.setStyleSheet(
            self._TAB_ACTIVE_STYLE if not is_resource else self._TAB_INACTIVE_STYLE
        )

    def _load_resource_pack_items(self):
        pack_items = []
        for pack_name in self.resource_packs:
            if isinstance(pack_name, dict):
                pack_file = str(pack_name.get("file", "")).strip()
                display_name = str(pack_name.get("display", "")).strip() or Path(pack_file).stem
            else:
                pack_file = str(pack_name)
                display_name = Path(pack_file).stem

            if pack_file:
                pack_items.append({"file": pack_file, "display": display_name})

        self._render_pack_items(pack_items)

    def _render_pack_items(self, pack_items):
        current_selected = self.selected_pack
        if not current_selected and self.pack_list.currentItem():
            widget = self.pack_list.itemWidget(self.pack_list.currentItem())
            if widget and isinstance(widget, ResourcePackListItem):
                current_selected = widget.file_name

        self.pack_list.clear()
        self.selected_pack = None
        self.start_button.setEnabled(False)

        if not pack_items:
            self.info_label.setText(tr("resource_selector.info.empty"))
            return

        self.info_label.setText(tr("resource_selector.info.count", count=len(pack_items)))

        for item_data in pack_items:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, item_data["file"])
            item.setSizeHint(QSize(0, 40))

            widget = ResourcePackListItem(item_data["display"], item_data["file"], self)

            self.pack_list.addItem(item)
            self.pack_list.setItemWidget(item, widget)

        select_index = -1
        if current_selected:
            for idx in range(self.pack_list.count()):
                list_item = self.pack_list.item(idx)
                if list_item:
                    widget = self.pack_list.itemWidget(list_item)
                    if widget and isinstance(widget, ResourcePackListItem):
                        if widget.file_name == current_selected:
                            select_index = idx
                            break

        if select_index < 0:
            for idx in range(self.pack_list.count()):
                list_item = self.pack_list.item(idx)
                if list_item:
                    widget = self.pack_list.itemWidget(list_item)
                    if widget and isinstance(widget, ResourcePackListItem):
                        if widget.file_name == "image.json":
                            select_index = idx
                            break

        if select_index < 0 and self.pack_list.count() > 0:
            select_index = 0

        if select_index >= 0:
            self.pack_list.setCurrentRow(select_index)

        # 常驻导入项作为最后一个列表项
        import_item = QListWidgetItem()
        import_item.setData(Qt.UserRole, "__import__")
        import_item.setSizeHint(QSize(0, 38))
        import_item.setFlags(Qt.ItemIsEnabled)
        import_btn = QPushButton(tr("resource_selector.import_hint"))
        import_btn.setObjectName("importHintBtn")
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setFocusPolicy(Qt.NoFocus)
        import_btn.setFlat(True)
        import_btn.clicked.connect(self._open_file_import)
        self.pack_list.addItem(import_item)
        self.pack_list.setItemWidget(import_item, import_btn)

    def _restore_selected_item(self):
        if not self.selected_pack:
            return

        for idx in range(self.pack_list.count()):
            list_item = self.pack_list.item(idx)
            if not list_item:
                continue
            if list_item.data(Qt.UserRole) == "__import__":
                continue

            widget = self.pack_list.itemWidget(list_item)
            file_name = widget.file_name if isinstance(widget, ResourcePackListItem) else list_item.data(Qt.UserRole)
            if file_name == self.selected_pack:
                old_state = self.pack_list.blockSignals(True)
                self.pack_list.setCurrentRow(idx)
                self.pack_list.blockSignals(old_state)
                return

    def _refresh_resource_packs(self):
        pack_files = get_available_resource_packs()
        if pack_files == self._known_pack_files:
            return

        self._known_pack_files = list(pack_files)
        pack_items = [
            {
                "file": file_name,
                "display": get_resource_pack_display_name(file_name),
            }
            for file_name in pack_files
        ]
        self._render_pack_items(pack_items)

    def _on_item_double_clicked(self, item):
        if item and item.data(Qt.UserRole) != "__import__":
            self._accept_selection()

    def _on_pack_selected(self):
        current_item = self.pack_list.currentItem()
        if not current_item or current_item.data(Qt.UserRole) == "__import__":
            self._restore_selected_item()
            return

        widget = self.pack_list.itemWidget(current_item)
        if widget and isinstance(widget, ResourcePackListItem):
            self.selected_pack = widget.file_name
        else:
            self.selected_pack = current_item.data(Qt.UserRole)
        self.start_button.setEnabled(True)
        self._update_preview(self.selected_pack)

    def done(self, result: int) -> None:
        self.refresh_timer.stop()
        self.mod_manager_page.stop_timers()
        super().done(result)

    def _accept_selection(self):
        if not self.selected_pack:
            return
        self.remember_as_default = self.default_check.isChecked()
        self.accept()

    def _on_pack_deleted(self, file_name: str):
        """资源包被删除时刷新列表"""
        if self.selected_pack == file_name:
            self.selected_pack = None
            self.start_button.setEnabled(False)
            self._set_preview_text(tr("resource_selector.preview.deleted"))
        self._refresh_resource_packs()

    def _open_file_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("resource_selector.dialog.select_pack"),
            "",
            tr("resource_selector.dialog.pack_filter"),
        )
        if files:
            self._import_files([Path(f) for f in files])

    def _validate_resource_pack(self, file_path: Path) -> bool:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            has_pack_name = "PACK_NAME" in data and data["PACK_NAME"]
            has_default_png = "DEFAULT_PNG" in data and data["DEFAULT_PNG"]
            return has_pack_name and has_default_png
        except Exception:
            return False

    def _import_files(self, file_paths: list):
        imported_count = 0
        failed_files = []
        needs_overwrite = []

        for file_path in file_paths:
            if not file_path.is_file() or file_path.suffix.lower() != ".json":
                continue
            if not self._validate_resource_pack(file_path):
                failed_files.append(tr("resource_selector.dialog.invalid_pack", name=file_path.name))
                _log.WARN(f"资源包格式不匹配: {file_path.name}")
                continue
            dest_path = Path("resources") / file_path.name
            if dest_path.exists():
                needs_overwrite.append((file_path, dest_path))
            else:
                try:
                    shutil.copy2(file_path, dest_path)
                    imported_count += 1
                    _log.INFO(f"导入资源包成功: {file_path.name}")
                except Exception as e:
                    failed_files.append(f"{file_path.name}: {str(e)}")
                    _log.ERROR(f"导入资源包失败 {file_path.name}: {e}")

        for file_path, dest_path in needs_overwrite:
            dialog = ConfirmDialog(
                tr("resource_selector.dialog.file_exists_title"),
                tr("resource_selector.dialog.file_exists_msg", name=file_path.name),
            )
            if dialog.exec() == QDialog.Accepted:
                try:
                    shutil.copy2(file_path, dest_path)
                    imported_count += 1
                    _log.INFO(f"导入资源包成功（覆盖）: {file_path.name}")
                except Exception as e:
                    failed_files.append(f"{file_path.name}: {str(e)}")
                    _log.ERROR(f"导入资源包失败 {file_path.name}: {e}")

        if imported_count > 0:
            success_dialog = ConfirmDialog(
                tr("resource_selector.dialog.import_success_title"),
                tr("resource_selector.dialog.import_success_msg", count=imported_count),
            )
            success_dialog.confirm_button.setVisible(False)
            success_dialog.exec()
            self._refresh_resource_packs()

        if failed_files:
            error_dialog = ConfirmDialog(
                tr("resource_selector.dialog.import_failed_title"),
                tr("resource_selector.dialog.import_failed_msg", detail="\n".join(failed_files)),
            )
            error_dialog.confirm_button.setVisible(False)
            error_dialog.exec()

    def _set_drag_style(self):
        # 只改容器边框颜色，不改宽度避免分层窗口重算布局导致卡死
        self.list_container.setStyleSheet(LIST_CONTAINER_DRAG_STYLE)

    def _reset_drag_style(self):
        self.list_container.setStyleSheet("")

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            for url in mime_data.urls():
                if url.toLocalFile().lower().endswith(".json"):
                    self._set_drag_style()
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._reset_drag_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._reset_drag_style()
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            event.ignore()
            return
        file_paths = [Path(url.toLocalFile()) for url in mime_data.urls()]
        event.acceptProposedAction()
        self._import_files(file_paths)

    def _set_preview_text(self, text: str):
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(text)

    def _update_preview(self, pack_file: str):
        pack_path = Path("resources") / str(pack_file)
        try:
            with open(pack_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_png = data.get("DEFAULT_PNG") if isinstance(data, dict) else None
            if not default_png:
                self._set_preview_text(tr("resource_selector.preview.missing_default_png"))
                return

            image_data = base64.b64decode(default_png)
            pixmap = QPixmap()
            if not pixmap.loadFromData(image_data):
                self._set_preview_text(tr("resource_selector.preview.load_failed"))
                return

            scaled = pixmap.scaled(148, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)
        except Exception:
            self._set_preview_text(tr("resource_selector.preview.load_failed"))

    def eventFilter(self, watched, event):
        if watched in getattr(self, "_drag_widgets", []):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                window_handle = self.windowHandle()
                if window_handle is not None:
                    try:
                        if window_handle.startSystemMove():
                            return True
                    except Exception:
                        pass

        return super().eventFilter(watched, event)
