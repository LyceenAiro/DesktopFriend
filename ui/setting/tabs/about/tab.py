from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.setting.common import create_section_card
from ui.setting.constants import LABEL_WIDTH
from ui.setting.tabs.about.css import ROW_MARGINS, ROW_SPACING, TAB_MARGINS, TAB_SPACING
from util.version import APP_NAME, author, github_link, version


class AboutTab(QFrame):
    tab_name = "关于"
    can_save = False

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_MARGINS)
        layout.setSpacing(TAB_SPACING)

        app_card = create_section_card("应用信息", "版本与作者信息")
        app_info_layout = app_card.layout()
        self._add_info_row(app_info_layout, "应用名称", APP_NAME)
        self._add_info_row(app_info_layout, "当前版本", version)
        self._add_info_row(app_info_layout, "开发者", author)

        project_card = create_section_card("项目链接", "点击可在浏览器中打开仓库")
        project_layout = project_card.layout()

        link_label = QLabel(f"<a href='{github_link}'>{github_link}</a>")
        link_label.setObjectName("fieldLabel")
        link_label.setOpenExternalLinks(True)
        project_layout.addWidget(link_label)

        layout.addWidget(app_card)
        layout.addSpacing(8)
        layout.addWidget(project_card)
        layout.addStretch()

    def _add_info_row(self, parent_layout, title: str, value: str):
        row = QHBoxLayout()
        row.setSpacing(ROW_SPACING)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(LABEL_WIDTH)
        row.addWidget(label)

        value_label = QLabel(value)
        value_label.setObjectName("subtitle")
        row.addWidget(value_label)

        row.addStretch()
        row.setContentsMargins(*ROW_MARGINS)
        parent_layout.addLayout(row)
