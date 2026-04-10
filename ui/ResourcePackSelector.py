from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)
from resources.image_resources import get_available_resource_packs, get_resource_pack_display_name


class ResourcePackSelector(QDialog):
    def __init__(self, resource_packs, parent=None):
        super().__init__(parent)
        self.resource_packs = list(resource_packs)
        self.selected_pack = None
        self._known_pack_files = []
        self._dragging = False
        self._drag_start_pos = None

        self.setWindowTitle("选择资源包")
        self.setModal(True)
        self.setFixedSize(800, 470)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

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

        self.pack_list = QListWidget()
        self.pack_list.setObjectName("packList")
        self.pack_list.itemSelectionChanged.connect(self._on_pack_selected)
        self.pack_list.itemDoubleClicked.connect(lambda _: self._accept_selection())
        right_layout.addWidget(self.pack_list)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_button = QPushButton("退出")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        self.start_button = QPushButton("启动")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._accept_selection)
        button_row.addWidget(self.start_button)

        right_layout.addLayout(button_row)

        shell_layout.addWidget(left_panel, 10)
        shell_layout.addWidget(right_panel, 14)

        self._drag_widgets = [
            self,
            self.window_shell,
            left_panel,
            right_panel,
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
            #info {
                color: #b8b8b8;
                font-size: 12px;
                padding-bottom: 2px;
            }
            #packList {
                background-color: #1f1f1f;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
                color: #f0f0f0;
                outline: none;
                font-size: 13px;
                padding: 6px;
            }
            #packList::item {
                height: 38px;
                margin: 2px 4px;
                padding: 6px 10px;
                border-radius: 6px;
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
            current_selected = self.pack_list.currentItem().data(Qt.UserRole)

        self.pack_list.clear()
        self.selected_pack = None
        self.start_button.setEnabled(False)

        if not pack_items:
            self.info_label.setText("未找到可用资源包 (resources/*.json)，请添加资源包")
            return

        self.info_label.setText(f"发现 {len(pack_items)} 个资源包")

        for item_data in pack_items:
            item = QListWidgetItem(f"{item_data['display']}    ({item_data['file']})")
            item.setData(Qt.UserRole, item_data["file"])
            self.pack_list.addItem(item)

        select_index = -1
        if current_selected:
            for idx in range(self.pack_list.count()):
                list_item = self.pack_list.item(idx)
                if list_item and list_item.data(Qt.UserRole) == current_selected:
                    select_index = idx
                    break

        if select_index < 0:
            for idx in range(self.pack_list.count()):
                list_item = self.pack_list.item(idx)
                if list_item and list_item.data(Qt.UserRole) == "image.json":
                    select_index = idx
                    break

        if select_index < 0 and self.pack_list.count() > 0:
            select_index = 0

        if select_index >= 0:
            self.pack_list.setCurrentRow(select_index)

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

    def _on_pack_selected(self):
        current_item = self.pack_list.currentItem()
        if not current_item:
            self.selected_pack = None
            self.start_button.setEnabled(False)
            return

        self.selected_pack = current_item.data(Qt.UserRole)
        self.start_button.setEnabled(True)

    def _accept_selection(self):
        if not self.selected_pack:
            return
        self.accept()

    def eventFilter(self, watched, event):
        if watched in getattr(self, "_drag_widgets", []):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_start_pos = event.globalPosition().toPoint()
                return True

            if event.type() == QEvent.MouseMove and self._dragging:
                current_global = event.globalPosition().toPoint()
                delta = current_global - self._drag_start_pos
                self.move(self.pos() + delta)
                self._drag_start_pos = current_global
                return True

            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._dragging = False
                self._drag_start_pos = None

        return super().eventFilter(watched, event)
