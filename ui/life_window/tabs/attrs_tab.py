from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ui.setting.common import create_section_card
from util.i18n import tr


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
        self.level_bonus_label = QLabel()
        self.level_bonus_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.level_bonus_label)
        self.item_permanent_label = QLabel()
        self.item_permanent_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.item_permanent_label)
        self.effect_label = QLabel()
        self.effect_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.effect_label)
        self.inventory_bonus_label = QLabel()
        self.inventory_bonus_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.inventory_bonus_label)
        self.exp_label = QLabel()
        self.exp_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.exp_label)
        outer.addWidget(self.panel)
        self.setStyleSheet(
            "QFrame#attrHoverPopupRoot { background: transparent; border: none; }"
            "QFrame#attrHoverPopup { background-color: #111820; border: 1px solid #2e4d6b; border-radius: 10px; }"
            "QLabel#titleLabel { color: #8ec8ff; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; background: transparent; border: none; }"
            "QLabel#valueLabel { color: #f7fbff; font-size: 13px; font-weight: 700; background: transparent; border: none; }"
            "QLabel#detailLabel { color: #b9d7ee; font-size: 11px; background: transparent; border: none; }"
        )

    def show_for(self, *, name, value, base, permanent_delta, level_bonus=0.0, item_permanent_delta=0.0,
                 effect_delta, inventory_bonus, exp, level, next_exp_required, global_pos):
        self.title_label.setText(name.upper())
        self.value_label.setText(tr("life.attrs.popup.total", value=f"{value:.0f}"))
        self.base_label.setText(tr("life.attrs.popup.base", value=f"{base:.0f}"))
        self.permanent_label.setText(tr("life.attrs.popup.permanent_delta", delta=f"{permanent_delta:+.0f}"))
        if level_bonus != 0.0:
            self.level_bonus_label.setText(tr("life.attrs.popup.level_bonus", delta=f"{level_bonus:+.0f}"))
            self.level_bonus_label.setVisible(True)
        else:
            self.level_bonus_label.setVisible(False)
        if item_permanent_delta != 0.0:
            self.item_permanent_label.setText(tr("life.attrs.popup.item_permanent", delta=f"{item_permanent_delta:+.0f}"))
            self.item_permanent_label.setVisible(True)
        else:
            self.item_permanent_label.setVisible(False)
        self.effect_label.setText(tr("life.attrs.popup.effect_delta", delta=f"{effect_delta:+.0f}"))
        if inventory_bonus != 0.0:
            self.inventory_bonus_label.setText(tr("life.attrs.popup.inventory_bonus", delta=f"{inventory_bonus:+.2f}"))
            self.inventory_bonus_label.setVisible(True)
        else:
            self.inventory_bonus_label.setVisible(False)
        if next_exp_required is not None:
            self.exp_label.setText(
                tr("life.attrs.popup.exp_level", level=level, exp=f"{exp:.0f}", required=f"{next_exp_required:.0f}")
            )
            self.exp_label.setVisible(True)
        else:
            if level > 0:
                self.exp_label.setText(tr("life.attrs.popup.max_level", level=level))
                self.exp_label.setVisible(True)
            else:
                self.exp_label.setVisible(False)
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


class LevelHoverPopup(QFrame):
    """等级进度条悬浮弹窗。"""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("levelHoverPopupRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.panel = QFrame(self)
        self.panel.setObjectName("levelHoverPopup")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(4)
        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        panel_layout.addWidget(self.title_label)
        self.current_exp_label = QLabel()
        self.current_exp_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.current_exp_label)
        self.required_exp_label = QLabel()
        self.required_exp_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.required_exp_label)
        self.passive_exp_label = QLabel()
        self.passive_exp_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.passive_exp_label)
        outer.addWidget(self.panel)
        self.setStyleSheet(
            "QFrame#levelHoverPopupRoot { background: transparent; border: none; }"
            "QFrame#levelHoverPopup { background-color: #111820; border: 1px solid #2e5c33; border-radius: 10px; }"
            "QLabel#titleLabel { color: #6fc986; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; background: transparent; border: none; }"
            "QLabel#detailLabel { color: #b9d7ee; font-size: 11px; background: transparent; border: none; }"
        )

    def show_for(self, *, level, max_level, exp, exp_required, passive_exp_per_tick, global_pos):
        self.title_label.setText(tr("life.level.card.title").upper() + f"  Lv.{level}")
        self.current_exp_label.setText(
            tr("life.level.tooltip.current_exp") + f": {exp:.1f}"
        )
        if exp_required is not None:
            self.required_exp_label.setText(
                tr("life.level.tooltip.required_exp") + f": {exp_required:.1f}"
            )
        else:
            self.required_exp_label.setText(
                tr("life.level.tooltip.required_exp") + f": {tr('life.level.tooltip.max_reached')}"
            )
        self.passive_exp_label.setText(
            tr("life.level.tooltip.passive_exp") + f": +{passive_exp_per_tick:.2f}"
        )
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


class LevelProgressBar(QProgressBar):
    """等级专用进度条，用路径裁切保证圆角在低值时不变形。"""
    _RADIUS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = self._RADIUS
        bg_path = QPainterPath()
        bg_path.addRoundedRect(r, rad, rad)
        painter.fillPath(bg_path, QColor("#2e2e2e"))
        span = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / span
        if ratio > 0.0:
            painter.setClipPath(bg_path)
            fill_rect = QRectF(r.x(), r.y(), r.width() * ratio, r.height())
            painter.fillRect(fill_rect, QColor("#4caf50"))
        painter.end()


class LevelCardWidget(QFrame):
    """等级卡片主体，负责显示等级/进度条并触发悬浮弹窗。"""

    def __init__(self, popup: LevelHoverPopup, parent=None):
        super().__init__(parent)
        self._popup = popup
        self._snapshot: dict = {}
        self._last_global_pos: QPoint = QPoint()
        self.setMouseTracking(True)
        self.setObjectName("levelCardWidget")
        self.setStyleSheet(
            "QFrame#levelCardWidget { background-color: #161616; border: 1px solid #2e2e2e;"
            " border-left: 3px solid #4caf50; border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        title_lbl = QLabel(tr("life.level.card.title"))
        title_lbl.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none;")
        title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_row.addWidget(title_lbl)

        self._level_lbl = QLabel("Lv.1")
        self._level_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._level_lbl.setStyleSheet(
            "font-weight: 700; font-size: 20px; color: #4caf50; background: transparent; border: none;"
        )
        top_row.addWidget(self._level_lbl)

        self._max_lbl = QLabel("/1")
        self._max_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._max_lbl.setStyleSheet("color: #666666; font-size: 12px; background: transparent; border: none;")
        top_row.addWidget(self._max_lbl)

        layout.addLayout(top_row)

        self._bar = LevelProgressBar()
        self._bar.setFixedHeight(8)
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setMouseTracking(True)
        layout.addWidget(self._bar)

    def update_snapshot(self, snapshot: dict) -> None:
        self._snapshot = snapshot
        level = int(snapshot.get("level", 1))
        max_level = int(snapshot.get("max_level", 1))
        exp = float(snapshot.get("exp", 0.0))
        exp_required = snapshot.get("exp_required")

        self._level_lbl.setText(f"Lv.{level}")
        self._max_lbl.setText(f"/ {max_level}")

        if exp_required is not None and float(exp_required) > 0:
            ratio = min(1.0, exp / float(exp_required))
            self._bar.setValue(int(ratio * 1000))
        else:
            # 满级或无配置时满格显示
            self._bar.setValue(1000)

        # 悬浮窗可见时同步刷新内容
        if self._popup.isVisible() and not self._last_global_pos.isNull():
            self._show_popup(self._last_global_pos)

    def _show_popup(self, global_pos):
        if not self._snapshot:
            return
        self._popup.show_for(
            level=self._snapshot.get("level", 1),
            max_level=self._snapshot.get("max_level", 1),
            exp=float(self._snapshot.get("exp", 0.0)),
            exp_required=self._snapshot.get("exp_required"),
            passive_exp_per_tick=float(self._snapshot.get("passive_exp_per_tick", 0.0)),
            global_pos=global_pos,
        )

    def enterEvent(self, event):
        self._last_global_pos = self.mapToGlobal(event.position().toPoint())
        self._show_popup(self._last_global_pos)
        return super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._last_global_pos = event.globalPosition().toPoint()
        self._show_popup(self._last_global_pos)
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._popup.hide()
        return super().leaveEvent(event)


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
            level_bonus=float(self._data.get("level_bonus", 0.0)),
            item_permanent_delta=float(self._data.get("item_permanent_delta", 0.0)),
            effect_delta=float(self._data.get("effect_delta", 0.0)),
            inventory_bonus=float(self._data.get("inventory_bonus", 0.0)),
            exp=float(self._data.get("exp", 0.0)),
            level=int(self._data.get("level", 0)),
            next_exp_required=self._data.get("next_exp_required"),
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
        self._level_popup = LevelHoverPopup()
        self._attr_rows: dict = {}
        self._current_attr_ids: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        # --- 等级卡片（额外加 18px 左右边距，与 section card 内属性 tile 对齐）---
        self._level_card = LevelCardWidget(self._level_popup)
        level_card_wrapper = QHBoxLayout()
        level_card_wrapper.setContentsMargins(18, 0, 18, 0)
        level_card_wrapper.addWidget(self._level_card)
        outer.addLayout(level_card_wrapper)

        # --- 属性列表卡片 ---
        self._attrs_card = create_section_card(tr("life.attrs.card.title"), tr("life.attrs.card.desc"))
        self._card_layout = self._attrs_card.layout()

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        self._card_layout.addWidget(self._list_widget)

        outer.addWidget(self._attrs_card)

    def _build_row(self, attr_id, name, color):
        tile = QFrame()
        tile.setObjectName("attrTile")
        tile.setStyleSheet(
            "QFrame#attrTile { background-color: #161616; border: 1px solid #2e2e2e;"
            " border-left: 3px solid " + color + "; border-radius: 8px; }"
        )
        tile_outer = QVBoxLayout(tile)
        tile_outer.setContentsMargins(14, 8, 14, 8)
        tile_outer.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("color: #888888; font-size: 12px; background: transparent; border: none;")
        name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_row.addWidget(name_lbl)

        level_lbl = QLabel("")
        level_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        level_lbl.setStyleSheet("color: #aaaaaa; font-size: 10px; background: transparent; border: none;")
        level_lbl.setVisible(False)
        top_row.addWidget(level_lbl)

        value_lbl = AttrValueLabel(self._popup)
        value_lbl.setText("0")
        value_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_lbl.setStyleSheet(
            "font-weight: 700; font-size: 20px; color: " + color + "; background: transparent; border: none;"
        )
        top_row.addWidget(value_lbl)
        tile_outer.addLayout(top_row)

        exp_bar = QProgressBar()
        exp_bar.setFixedHeight(4)
        exp_bar.setTextVisible(False)
        exp_bar.setRange(0, 1000)
        exp_bar.setValue(0)
        exp_bar.setVisible(False)
        exp_bar.setStyleSheet(
            "QProgressBar { background-color: #2e2e2e; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background-color: " + color + "; border-radius: 2px; }"
        )
        tile_outer.addWidget(exp_bar)

        return tile, name_lbl, value_lbl, level_lbl, exp_bar

    def _rebuild_list(self, snapshot):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._attr_rows.clear()
        self._current_attr_ids = []

        for entry in snapshot:
            attr_id = str(entry.get("id", ""))
            if not attr_id:
                continue
            name = str(entry.get("name", attr_id))
            color = str(entry.get("color", "#666666"))
            row = self._build_row(attr_id, name, color)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row[0])
            self._attr_rows[attr_id] = row
            self._current_attr_ids.append(attr_id)

    def update_data(self, snapshot):
        new_ids = [str(e.get("id", "")) for e in snapshot if e.get("id")]
        if new_ids != self._current_attr_ids or not new_ids:
            self._rebuild_list(snapshot)

        for entry in snapshot:
            attr_id = str(entry.get("id", ""))
            row = self._attr_rows.get(attr_id)
            if row is None:
                continue
            _tile, _name_lbl, value_lbl, level_lbl, exp_bar = row

            value = int(round(float(entry.get("value", 0.0))))
            value_lbl.setText(str(value))
            value_lbl.bind_data(entry)

            level = int(entry.get("level", 0))
            next_exp = entry.get("next_exp_required")
            if level > 0:
                level_lbl.setText(f"Lv.{level}")
                level_lbl.setVisible(True)
            else:
                level_lbl.setVisible(False)

            if next_exp is not None and float(next_exp) > 0:
                exp = float(entry.get("exp", 0.0))
                ratio = min(1.0, exp / float(next_exp))
                exp_bar.setValue(int(ratio * 1000))
                exp_bar.setVisible(True)
            else:
                exp_bar.setVisible(False)

    def update_level(self, snapshot: dict) -> None:
        """使用 get_level_snapshot() 返回的快照更新等级卡片。"""
        self._level_card.update_snapshot(snapshot)
