from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from ui.setting.common import create_section_card
from util.i18n import tr


ATTR_KEYS = ("vit", "str", "spd", "agi", "spi", "int", "ill")

_ATTR_ACCENT = {
    "vit": "#d95f5f",
    "str": "#d4834a",
    "spd": "#c8b840",
    "agi": "#5ab86c",
    "spi": "#4ea8d8",
    "int": "#8b6fd6",
    "ill": "#888888",
}


class AttrHoverPopup(QFrame):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("attrHoverPopupRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.panel = QFrame(self)
        self.panel.setObjectName("attrHoverPopup")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(4)
        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        panel_layout.addWidget(self.title_label)
        self.value_label = QLabel()
        self.value_label.setObjectName("valueLabel")
        panel_layout.addWidget(self.value_label)
        self.base_label = QLabel()
        self.base_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.base_label)
        self.permanent_label = QLabel()
        self.permanent_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.permanent_label)
        self.effect_label = QLabel()
        self.effect_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.effect_label)
        outer.addWidget(self.panel)
        self.setStyleSheet(
            "QFrame#attrHoverPopupRoot { background: transparent; border: none; }"
            "QFrame#attrHoverPopup { background-color: #111820; border: 1px solid #2e4d6b; border-radius: 10px; }"
            "QLabel#titleLabel { color: #8ec8ff; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; background: transparent; border: none; }"
            "QLabel#valueLabel { color: #f7fbff; font-size: 13px; font-weight: 700; background: transparent; border: none; }"
            "QLabel#detailLabel { color: #b9d7ee; font-size: 11px; background: transparent; border: none; }"
        )

    def show_for(self, *, name, value, base, permanent_delta, effect_delta, global_pos):
        self.title_label.setText(name.upper())
        self.value_label.setText(tr("life.attrs.popup.total", value=f"{value:.0f}"))
        self.base_label.setText(tr("life.attrs.popup.base", value=f"{base:.0f}"))
        self.permanent_label.setText(tr("life.attrs.popup.permanent_delta", delta=f"{permanent_delta:+.0f}"))
        self.effect_label.setText(tr("life.attrs.popup.effect_delta", delta=f"{effect_delta:+.0f}"))
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


class AttrValueLabel(QLabel):
    def __init__(self, popup, parent=None):
        super().__init__(parent)
        self._popup = popup
        self._data = None
        self.setMouseTracking(True)

    def bind_data(self, data):
        self._data = data

    def _show_popup(self, global_pos):
        if not self._data:
            return
        self._popup.show_for(
            name=str(self._data.get("name", "")),
            value=float(self._data.get("value", 0.0)),
            base=float(self._data.get("base", 10.0)),
            permanent_delta=float(self._data.get("permanent_delta", 0.0)),
            effect_delta=float(self._data.get("effect_delta", 0.0)),
            global_pos=global_pos,
        )

    def enterEvent(self, event):
        self._show_popup(self.mapToGlobal(event.position().toPoint()))
        return super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._show_popup(event.globalPosition().toPoint())
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._popup.hide()
        return super().leaveEvent(event)


class LifeAttrsTab(QFrame):
    tab_name = tr("life.tabs.attrs")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup = AttrHoverPopup()
        self.attr_value_labels = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        attrs_card = create_section_card(tr("life.attrs.card.title"), tr("life.attrs.card.desc"))
        card_layout = attrs_card.layout()
        tile_grid = QGridLayout()
        tile_grid.setHorizontalSpacing(10)
        tile_grid.setVerticalSpacing(10)
        tile_grid.setColumnStretch(0, 1)
        tile_grid.setColumnStretch(1, 1)
        total = len(ATTR_KEYS)
        for index, key in enumerate(ATTR_KEYS):
            grid_row = index // 2
            grid_col = index % 2
            accent = _ATTR_ACCENT.get(key, "#666666")
            tile = QFrame()
            tile.setObjectName("attrTile")
            tile.setStyleSheet(
                "QFrame#attrTile { background-color: #161616; border: 1px solid #2e2e2e;"
                " border-left: 3px solid " + accent + "; border-radius: 8px; }"
            )
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(14, 10, 14, 10)
            tile_layout.setSpacing(3)
            name_lbl = QLabel(tr(f"life.attr.{key}"))
            name_lbl.setStyleSheet("color: #888888; font-size: 11px; background: transparent; border: none;")
            tile_layout.addWidget(name_lbl)
            value_lbl = AttrValueLabel(self._popup)
            value_lbl.setText("0")
            value_lbl.setStyleSheet(
                "font-weight: 700; font-size: 20px; color: " + accent + "; background: transparent; border: none;"
            )
            tile_layout.addWidget(value_lbl)
            if index == total - 1 and total % 2 == 1:
                tile_grid.addWidget(tile, grid_row, 0, 1, 2)
            else:
                tile_grid.addWidget(tile, grid_row, grid_col)
            self.attr_value_labels[key] = value_lbl
        card_layout.addLayout(tile_grid)
        layout.addWidget(attrs_card)
        layout.addStretch()

    def update_data(self, snapshot):
        for entry in snapshot:
            attr_id = str(entry.get("id", ""))
            label = self.attr_value_labels.get(attr_id)
            if label is None:
                continue
            value = int(round(float(entry.get("value", 0.0))))
            label.setText(str(value))
            label.bind_data(entry)
