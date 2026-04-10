from pathlib import Path
import base64
import json
import shutil

from PySide6.QtCore import Qt, QTimer, QEvent, QSize
from PySide6.QtGui import QColor, QPixmap, QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from resources.image_resources import get_available_resource_packs, get_resource_pack_display_name
from util.log import _log
from ui.ConfirmDialog import ConfirmDialog


class ResourcePackListItem(QWidget):
    """自定义资源包列表项，鼠标悬停时显示删除图标"""
    def __init__(self, display_name: str, file_name: str, parent_selector=None, parent=None):
        super().__init__(parent)
        self.display_name = display_name
        self.file_name = file_name
        self.parent_selector = parent_selector
        self.setMouseTracking(True)
        self._is_hovered = False
        
        # 设置widget背景透明，禁用默认hover样式
        self.setStyleSheet("""
            ResourcePackListItem {
                background-color: transparent;
                border: none;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(10)
        
        label = QLabel(f"{display_name}    ({file_name})")
        label.setStyleSheet("color: #f0f0f0; font-size: 13px;")
        label.setCursor(Qt.ArrowCursor)
        layout.addWidget(label, 1)
        
        self.delete_button = QPushButton("✕")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.setFixedSize(10, 10)
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setToolTip("删除资源包")
        self.delete_button.setVisible(False)
        self.delete_button.setStyleSheet("""
            #deleteButton {
                color: #e05050;
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                font-size: 12px;
                padding: 0px;
                margin: 0px;
            }
        """)
        self.delete_button.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_button, 0, Qt.AlignRight | Qt.AlignVCenter)
    
    def enterEvent(self, event):
        self._is_hovered = True
        self.delete_button.setVisible(True)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._is_hovered = False
        self.delete_button.setVisible(False)
        super().leaveEvent(event)
    
    def _on_delete(self):
        if self.file_name == "image.json":
            dialog = ConfirmDialog("无法删除", "不能删除默认资源包 image.json")
            dialog.confirm_button.setVisible(False)
            dialog.exec()
            return
        
        dialog = ConfirmDialog(
            "确认删除",
            f"确定删除资源包\"{self.display_name}\"吗？\n\n文件: {self.file_name}"
        )
        if dialog.exec() != QDialog.Accepted:
            return
        
        try:
            pack_path = Path("resources") / self.file_name
            if pack_path.exists():
                pack_path.unlink()
                _log.INFO(f"已删除资源包: {self.file_name}")
                if self.parent_selector:
                    self.parent_selector._on_pack_deleted(self.file_name)
            else:
                error_dialog = ConfirmDialog("删除失败", f"资源包文件不存在: {self.file_name}")
                error_dialog.confirm_button.setVisible(False)
                error_dialog.exec()
        except Exception as e:
            error_dialog = ConfirmDialog("删除失败", f"删除资源包失败:\n{str(e)}")
            error_dialog.confirm_button.setVisible(False)
            error_dialog.exec()
            _log.ERROR(f"删除资源包失败 {self.file_name}: {e}")


class ResourcePackSelector(QDialog):
    def __init__(self, resource_packs, parent=None):
        super().__init__(parent)
        self.resource_packs = list(resource_packs)
        self.selected_pack = None
        self._known_pack_files = []
        self.remember_as_default = False

        self.setWindowTitle("选择资源包")
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

        subtitle_label = QLabel("Creative Companion")
        subtitle_label.setObjectName("brandSubtitle")
        left_layout.addWidget(subtitle_label)

        desc_label = QLabel("在启动前选择资源包。\n你可以用自定义资源包启动桌宠。")
        desc_label.setWordWrap(True)
        desc_label.setObjectName("brandDescription")
        left_layout.addWidget(desc_label)

        left_layout.addStretch()

        hint_label = QLabel("Tip: 双击资源包可直接进入")
        hint_label.setObjectName("brandHint")
        left_layout.addWidget(hint_label)

        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(26, 28, 26, 24)
        right_layout.setSpacing(14)

        title_label = QLabel("选择资源包")
        title_label.setObjectName("title")
        right_layout.addWidget(title_label)

        self.info_label = QLabel("")
        self.info_label.setObjectName("info")
        right_layout.addWidget(self.info_label)

        self.preview_label = QLabel("未选择资源包")
        self.preview_label.setObjectName("previewBox")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(156)
        right_layout.addWidget(self.preview_label)

        self.pack_list = QListWidget()
        self.pack_list.setObjectName("packList")
        self.pack_list.setMinimumHeight(260)
        self.pack_list.setAcceptDrops(True)
        self.pack_list.itemSelectionChanged.connect(self._on_pack_selected)
        self.pack_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.list_container = QFrame()
        self.list_container.setObjectName("listContainer")
        list_container_layout = QVBoxLayout(self.list_container)
        list_container_layout.setContentsMargins(0, 0, 0, 0)
        list_container_layout.setSpacing(0)
        list_container_layout.addWidget(self.pack_list, 1)

        right_layout.addWidget(self.list_container, 1)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        self.default_check = QCheckBox("默认选择该资源")
        self.default_check.setObjectName("rememberCheck")
        footer_row.addWidget(self.default_check)
        footer_row.addStretch()

        cancel_button = QPushButton("退出")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        footer_row.addWidget(cancel_button)

        self.start_button = QPushButton("启动")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._accept_selection)
        footer_row.addWidget(self.start_button)

        right_layout.addLayout(footer_row)

        shell_layout.addWidget(left_panel, 10)
        shell_layout.addWidget(right_panel, 14)

        self._drag_widgets = [
            left_panel,
            brand_label,
            subtitle_label,
            desc_label,
            hint_label,
            title_label,
            self.info_label,
        ]
        for widget in self._drag_widgets:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

        self.setStyleSheet(
            """
            QDialog {
                background: transparent;
            }
            #windowShell {
                background-color: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 16px;
            }
            #leftPanel {
                background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2c2c2c,
                    stop:1 #1f1f1f);
                border-right: 1px solid #3a3a3a;
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
            }
            #rightPanel {
                background-color: #262626;
                border-top-right-radius: 16px;
                border-bottom-right-radius: 16px;
            }
            #brandTitle {
                color: #f3f3f3;
                font-size: 30px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            #brandSubtitle {
                color: #f95f53;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1.4px;
                text-transform: uppercase;
            }
            #brandDescription {
                color: #d0d0d0;
                font-size: 13px;
                line-height: 1.4em;
            }
            #brandHint {
                color: #9a9a9a;
                font-size: 11px;
            }
            #title {
                color: #f5f5f5;
                font-size: 22px;
                font-weight: 650;
            }
            #previewTitle {
                color: #d7d7d7;
                font-size: 12px;
                font-weight: 600;
                padding-top: 2px;
            }
            #previewBox {
                background-color: #1d1d1d;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
                color: #9a9a9a;
                font-size: 12px;
            }
            #info {
                color: #b8b8b8;
                font-size: 12px;
                padding-bottom: 2px;
            }
            #packList {
                background-color: transparent;
                border: none;
                border-radius: 0;
                color: #f0f0f0;
                outline: none;
                font-size: 13px;
                padding: 6px;
            }
            #listContainer {
                background-color: #1f1f1f;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            #packList::item {
                height: 40px;
                margin: 2px 4px;
                padding: 0px;
                border-radius: 6px;
            }
            #packList::item:hover {
                background-color: transparent;
                border: none;
            }
            #packList::item:selected {
                background-color: #4a2220;
                border: 1px solid #f95f53;
            }
            QPushButton {
                min-width: 88px;
                min-height: 34px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            #secondaryButton {
                color: #d7d7d7;
                background-color: #353535;
                border: 1px solid #4a4a4a;
            }
            #secondaryButton:hover {
                background-color: #3d3d3d;
            }
            #primaryButton {
                color: white;
                background-color: #e6453a;
                border: 1px solid #ff776d;
            }
            #primaryButton:hover {
                background-color: #f6574b;
            }
            #primaryButton:disabled {
                color: #8a8a8a;
                background-color: #343434;
                border: 1px solid #434343;
            }
            #rememberCheck {
                color: #d0d0d0;
                font-size: 12px;
                padding-top: 4px;
            }
            #importHintBtn {
                color: #454545;
                font-size: 12px;
                font-weight: 400;
                border: none;
                border-radius: 0;
                min-width: 0;
                min-height: 0;
                background-color: transparent;
                text-align: center;
            }
            #importHintBtn:hover {
                color: #888888;
                background-color: #1e1e1e;
            }
            """
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
            self.info_label.setText("未找到可用资源包 (resources/*.json)，请添加资源包")
            return

        self.info_label.setText(f"发现 {len(pack_items)} 个资源包")

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
        import_btn = QPushButton("＋  选择资源包，或拖入资源包导入")
        import_btn.setObjectName("importHintBtn")
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setFlat(True)
        import_btn.clicked.connect(self._open_file_import)
        self.pack_list.addItem(import_item)
        self.pack_list.setItemWidget(import_item, import_btn)

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
            return

        widget = self.pack_list.itemWidget(current_item)
        if widget and isinstance(widget, ResourcePackListItem):
            self.selected_pack = widget.file_name
        else:
            self.selected_pack = current_item.data(Qt.UserRole)
        self.start_button.setEnabled(True)
        self._update_preview(self.selected_pack)

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
            self._set_preview_text("已删除该资源包")
        self._refresh_resource_packs()

    def _open_file_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择资源包", "", "资源包文件 (*.json);;所有文件 (*)"
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
                failed_files.append(f"{file_path.name}: 资源包格式不匹配，缺少 PACK_NAME 或 DEFAULT_PNG")
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
            dialog = ConfirmDialog("文件已存在", f"资源包 {file_path.name} 已存在，是否覆盖？")
            if dialog.exec() == QDialog.Accepted:
                try:
                    shutil.copy2(file_path, dest_path)
                    imported_count += 1
                    _log.INFO(f"导入资源包成功（覆盖）: {file_path.name}")
                except Exception as e:
                    failed_files.append(f"{file_path.name}: {str(e)}")
                    _log.ERROR(f"导入资源包失败 {file_path.name}: {e}")

        if imported_count > 0:
            success_dialog = ConfirmDialog("导入成功", f"已导入 {imported_count} 个资源包")
            success_dialog.confirm_button.setVisible(False)
            success_dialog.exec()
            self._refresh_resource_packs()

        if failed_files:
            error_dialog = ConfirmDialog("导入失败", "以下资源包导入失败:\n" + "\n".join(failed_files))
            error_dialog.confirm_button.setVisible(False)
            error_dialog.exec()

    def _set_drag_style(self):
        # 只改容器边框颜色，不改宽度避免分层窗口重算布局导致卡死
        self.list_container.setStyleSheet(
            "#listContainer { background-color: #1a2620; border: 1px solid #5aaa88; border-radius: 8px; }"
        )

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
                self._set_preview_text("该资源包缺少 DEFAULT_PNG")
                return

            image_data = base64.b64decode(default_png)
            pixmap = QPixmap()
            if not pixmap.loadFromData(image_data):
                self._set_preview_text("预览加载失败")
                return

            scaled = pixmap.scaled(148, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)
        except Exception:
            self._set_preview_text("预览加载失败")

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
