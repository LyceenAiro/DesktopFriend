from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from ui.setting.common import create_section_card
from util.i18n import tr


ATTR_KEYS = ("vit", "str", "spd", "agi", "spi", "int", "ill")


class LifeAttrsTab(QFrame):
    tab_name = tr("life.tabs.attrs")

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        attrs_card = create_section_card(tr("life.attrs.card.title"), tr("life.attrs.card.desc"))
        card_layout = attrs_card.layout()

        self.attrs_grid = QGridLayout()
        self.attrs_grid.setHorizontalSpacing(28)
        self.attrs_grid.setVerticalSpacing(10)
        self.attr_value_labels: dict[str, QLabel] = {}

        for index, key in enumerate(ATTR_KEYS):
            row = index // 2
            col = (index % 2) * 2

            name_label = QLabel(tr(f"life.attr.{key}"))
            name_label.setObjectName("fieldLabel")
            self.attrs_grid.addWidget(name_label, row, col)

            value_label = QLabel("0")
            value_label.setStyleSheet("font-weight: 700; color: #f3f3f3;")
            self.attrs_grid.addWidget(value_label, row, col + 1)
            self.attr_value_labels[key] = value_label

        card_layout.addLayout(self.attrs_grid)

        layout.addWidget(attrs_card)
        layout.addStretch()

    def update_data(self, profile) -> None:
        for key, label in self.attr_value_labels.items():
            value = int(round(float(profile.attrs.get(key, 0.0))))
            label.setText(str(value))
