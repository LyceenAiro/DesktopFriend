from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_EXP_MAX: int = 2 ** 31 - 1  # 经验值上限，防止溢出

from util.log import _log
from util.i18n import tr
from module.life.schema import (
    ValidationIssue,
    validate_attr_record,
    validate_buff_record,
    validate_item_record,
    validate_event_trigger_record,
    validate_event_outcome_record,
    validate_level_config,
    validate_state_record,
    validate_nutrition_record,
)
from module.life.sqlite_store import LifeSqliteStore


BASE_STATES = ("hp", "happy", "psc", "energy")
BASE_ATTRS = ("vit", "str", "spd", "agi", "spi", "int", "ill")
GLOBAL_VALUE_MAX = 1000.0


@dataclass
class LifeEffect:
    effect_id: str
    effect_name: str
    effect_desc: str
    source: str
    per_tick: dict[str, float]
    remaining_ticks: int
    stack_rule: str = "add"
    cap_modifiers: list[tuple[str, str, Any]] = field(default_factory=list)
    attr_modifiers: dict[str, float] = field(default_factory=dict)
    managed: bool = False  # 由外部（如营养系统）管理生命周期，不倒计时也不自动移除
    nutrition_per_tick: dict[str, float] = field(default_factory=dict)  # 每 tick 额外消耗的营养值（正值=减少）
    apply_states: dict[str, float] = field(default_factory=dict)  # 激活时一次性状态修正，移除时还原


@dataclass
class LifeProfile:
    states: dict[str, float] = field(default_factory=dict)
    state_max: dict[str, float] = field(default_factory=dict)
    state_min: dict[str, float] = field(default_factory=dict)
    nutrition: dict[str, float] = field(default_factory=dict)
    nutrition_max: dict[str, float] = field(default_factory=dict)
    nutrition_min: dict[str, float] = field(default_factory=dict)
    attrs: dict[str, float] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    active_effects: list[LifeEffect] = field(default_factory=list)
    attr_exp: dict[str, float] = field(default_factory=dict)    # 每属性当前经验值
    attr_level: dict[str, int] = field(default_factory=dict)   # 每属性当前等级
    attr_base: dict[str, float] = field(default_factory=dict)  # 上次使用的 initial 基础值（用于检测外部改动）
    # 全局等级系统
    level: int = 1                                              # 全局角色等级（最低 1）
    exp: float = 0.0                                            # 当前等级已累计经验（始终 ≥ 0）
    permanent_attr_delta: dict[str, float] = field(default_factory=dict)  # 物品永久属性修正（重置前不消失）
    # 图鉴收集
    unlocked_buffs: set[str] = field(default_factory=set)       # 曾经触发过的 buff
    unlocked_triggers: set[str] = field(default_factory=set)    # 曾经完成的事件触发器
    unlocked_outcomes: set[str] = field(default_factory=set)    # 曾经触发的事件结果

class LifeSystem:
    """0.3 draft implementation for life architecture.

    - Passive json registration for buff and item.
    - Runtime states/attrs with tick updates.
    - SQLite profile save/load.
    """

    _RECENT_EVENT_LOG_MAX = 200

    def __init__(
        self,
        buff_dir: str | Path = "module/life/buff",
        item_dir: str | Path = "module/life/item",
        status_dir: str | Path = "module/life/status",
        nutrition_dir: str | Path = "module/life/nutrition",
        event_trigger_dir: str | Path = "module/life/event_trigger",
        event_outcome_dir: str | Path = "module/life/event_outcome",
        passive_buff_dir: str | Path = "module/life/passive_buff",
        attr_dir: str | Path = "module/life/attrs",
        tag_dir: str | Path = "module/life/tags",
        store: LifeSqliteStore | None = None,
    ):
        # PyInstaller 打包后资源文件在 sys._MEIPASS 下
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            _base = Path(sys._MEIPASS)
        else:
            _base = Path(".")

        self.buff_dir = _base / Path(buff_dir)
        self.item_dir = _base / Path(item_dir)
        self.status_dir = _base / Path(status_dir)
        self.nutrition_dir = _base / Path(nutrition_dir)
        self.event_trigger_dir = _base / Path(event_trigger_dir)
        self.event_outcome_dir = _base / Path(event_outcome_dir)
        self.passive_buff_dir = _base / Path(passive_buff_dir)
        self.attr_dir = _base / Path(attr_dir)
        self.tag_dir = _base / Path(tag_dir)
        self.extra_buff_dirs: list[Path] = []
        self.extra_item_dirs: list[Path] = []
        self.extra_status_dirs: list[Path] = []
        self.extra_nutrition_dirs: list[Path] = []
        self.extra_event_trigger_dirs: list[Path] = []
        self.extra_event_outcome_dirs: list[Path] = []
        self.extra_passive_buff_dirs: list[Path] = []
        self.extra_attr_dirs: list[Path] = []
        self.extra_tag_dirs: list[Path] = []
        # 全局等级系统资源目录（mod 可注入覆盖 level_setting.json）
        self.level_dir: Path = _base / Path("module/life/level")
        self.extra_level_dirs: list[Path] = []
        self.store = store or LifeSqliteStore()
        self.character_name: str = ""  # 角色名称（由外部注入，如资源包 PACK_NAME）
        self.paused: bool = False  # 暂停时 tick 和物品使用均被冻结

        self.buff_registry: dict[str, dict[str, Any]] = {}
        self.item_registry: dict[str, dict[str, Any]] = {}
        self.event_trigger_registry: dict[str, dict[str, Any]] = {}
        self.event_outcome_registry: dict[str, dict[str, Any]] = {}
        self.passive_buff_registry: dict[str, dict[str, Any]] = {}
        self.tag_registry: dict[str, dict[str, Any]] = {}  # tag_id → {id, buff_id, i18n_key, color, name}
        self.attribute_rules: dict[str, list[dict[str, Any]]] = {}
        self.validation_issues: list[ValidationIssue] = []
        self._pending_remove_ids: dict[str, set[str]] = {}  # registry_type → set of ids to remove
        self._static_cap_modifiers: list[tuple[str, str, Any]] = []
        self._item_cooldowns: dict[str, float] = {}  # item_id → 可用时间戳 (time.time())
        self._trigger_cooldowns: dict[str, float] = {}  # trigger_id → 可用时间戳
        self._trigger_executing: dict[str, float] = {}  # trigger_id → 完成时间戳 (正在执行中)
        self._completed_trigger_results: list[dict[str, Any]] = []  # 执行完成事件队列（供 UI 消费）
        self._recent_event_logs: list[dict[str, Any]] = []  # 最近事件日志（长历史，供 UI 聚合后截断）
        self._recent_event_log_seq: int = 0  # 最近事件日志序号（用于稳定检测变化）
        self._inventory_passive_attrs: dict[str, float] = {}  # 背包被动属性加成缓存（按需重算）

        # 全局等级系统运行时数据
        self._exp_table: dict[int, float] = {}        # level → 升级所需经验（满级时无此 key）
        self._max_level: int = 1                      # 最高等级
        self._passive_exp_per_tick: float = 0.0       # 基础每 tick 被动经验
        self._inventory_passive_exp_bonus: float = 0.0  # 背包带来的额外每 tick 被动经验

        # 死亡系统
        self.is_dead: bool = False
        self._death_summary: dict[str, Any] | None = None
        self._life_started_at: float = time.time()

        self.state_definitions, _state_init_issues = self._load_state_definitions()
        self.nutrition_definitions, _nutrition_init_issues = self._load_nutrition_definitions()
        self.attr_definitions: dict[str, dict[str, Any]] = self._load_attr_definitions()
        self._load_level_config()

        self._attr_cap_bonus_max: dict[str, float] = {k: 0.0 for k in self.state_keys}
        self._attr_cap_bonus_min: dict[str, float] = {k: 0.0 for k in self.state_keys}
        self._state_runtime_breakdown: dict[str, dict[str, float]] = {}

        self.profile = self._create_default_profile()
        self.reload_registries()
        _log.INFO(
            f"[Life]LifeSystem 初始化完成 states={len(self.state_definitions)} nutrition={len(self.nutrition_definitions)} "
            f"attrs={len(self.attr_definitions)} inventory={len(self.profile.inventory)}"
        )


    def _resolve_name(self, template: str) -> str:
        """将字段中的 {character_name} 占位符替换为当前角色名。"""
        if self.character_name and "{character_name}" in template:
            return template.replace("{character_name}", self.character_name)
        return template

    def _resolve_i18n_text(self, record: dict[str, Any], field: str, fallback: str = "") -> str:
        """Resolve text from json with optional `<field>_i18n_key`, then process placeholders."""
        raw_text = str(record.get(field) or fallback)
        i18n_key = str(record.get(f"{field}_i18n_key") or "").strip()
        if i18n_key:
            raw_text = tr(i18n_key, default=raw_text)
        return self._resolve_name(raw_text)

    def _resolve_record_name(self, record: dict[str, Any], fallback: str) -> str:
        return self._resolve_i18n_text(record, "name", fallback=fallback)

    def _resolve_record_desc(self, record: dict[str, Any]) -> str:
        # Prefer desc, fallback to description; both support dedicated i18n keys.
        if "desc" in record:
            return self._resolve_i18n_text(record, "desc", fallback=str(record.get("description") or "").strip())
        return self._resolve_i18n_text(record, "description", fallback="")

    @property
    def state_keys(self) -> tuple[str, ...]:
        return tuple(self.state_definitions.keys())

    @property
    def nutrition_keys(self) -> tuple[str, ...]:
        return tuple(self.nutrition_definitions.keys())

    @property
    def attr_keys(self) -> tuple[str, ...]:
        return tuple(self.attr_definitions.keys()) if self.attr_definitions else BASE_ATTRS

    def get_state_definitions(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.state_definitions.values()]

    def get_nutrition_definitions(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.nutrition_definitions.values()]

    def get_attr_definitions(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.attr_definitions.values()]

    def _create_default_profile(self) -> LifeProfile:
        states = {key: float(defn["default"]) for key, defn in self.state_definitions.items()}
        state_max = {key: float(defn["max"]) for key, defn in self.state_definitions.items()}
        state_min = {key: float(defn["min"]) for key, defn in self.state_definitions.items()}
        nutrition = {key: float(defn["default"]) for key, defn in self.nutrition_definitions.items()}
        nutrition_max = {key: float(defn.get("max", 100.0)) for key, defn in self.nutrition_definitions.items()}
        nutrition_min = {key: float(defn.get("min", 0.0)) for key, defn in self.nutrition_definitions.items()}
        attrs: dict[str, float] = {k: float(defn.get("initial", 10.0)) for k, defn in self.attr_definitions.items()} if self.attr_definitions else {}
        attr_exp: dict[str, float] = {k: 0.0 for k in self.attr_definitions.keys()}
        attr_level: dict[str, int] = {k: 0 for k in self.attr_definitions.keys()}
        attr_base: dict[str, float] = {k: float(defn.get("initial", 10.0)) for k, defn in self.attr_definitions.items()} if self.attr_definitions else {}
        inventory = self._load_starter_inventory()
        return LifeProfile(states=states, state_max=state_max, state_min=state_min, nutrition=nutrition, nutrition_max=nutrition_max, nutrition_min=nutrition_min, attrs=attrs, inventory=inventory, attr_exp=attr_exp, attr_level=attr_level, attr_base=attr_base)

    def _load_starter_inventory(self) -> dict[str, int]:
        result: dict[str, int] = {}
        loaded_files = 0
        for item_root in self._iter_item_dirs():
            for starter_file in sorted(item_root.rglob("starter_inventory.json")):
                try:
                    loaded_files += 1
                    raw = json.loads(starter_file.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict):
                        continue
                    for item_id, count in raw.items():
                        try:
                            c = int(count)
                        except Exception:
                            continue
                        if c > 0 and str(item_id) in self.item_registry:
                            result[str(item_id)] = result.get(str(item_id), 0) + c
                except Exception as exc:
                    _log.WARN(f"[Life] Failed to load starter_inventory.json from {starter_file}: {exc}")
        _log.DEBUG(f"[Life][Register][StarterInventory] files={loaded_files} loaded_items={len(result)}")
        return result

    def reload_registries(self) -> None:
        _log.INFO("[Life][Register]开始重载注册表")
        next_state_defs, state_issues = self._load_state_definitions()
        next_nutrition_defs, nutrition_issues = self._load_nutrition_definitions()
        next_attr_defs = self._load_attr_definitions()
        self._sync_profile_states(next_state_defs)
        self._sync_profile_nutrition(next_nutrition_defs)
        self._sync_profile_attrs(next_attr_defs)
        self.attr_definitions = next_attr_defs

        self.buff_registry, buff_issues = self._load_registry_dir(
            self._iter_buff_dirs(),
            "buff",
            state_keys=self.state_keys,
            attr_keys=self.attr_keys,
            nutrition_keys=self.nutrition_keys,
        )
        self.item_registry, item_issues = self._load_item_registry(
            self._iter_item_dirs(),
            state_keys=self.state_keys,
            attr_keys=self.attr_keys,
            nutrition_keys=self.nutrition_keys,
        )
        self.event_trigger_registry, trigger_issues = self._load_event_registry(
            self._iter_event_trigger_dirs(), "event_trigger"
        )
        self.event_outcome_registry, outcome_issues = self._load_event_registry(
            self._iter_event_outcome_dirs(), "event_outcome"
        )
        self.passive_buff_registry, passive_issues = self._load_passive_buff_registry(
            self._iter_passive_buff_dirs()
        )
        self.tag_registry = self._load_tag_registry(self._iter_tag_dirs())
        self.validation_issues = state_issues + nutrition_issues + buff_issues + item_issues + trigger_issues + outcome_issues + passive_issues
        self.attribute_rules = self._load_attribute_rules(self.buff_registry)
        self._refresh_attr_range_effects()
        self._sync_managed_nutrition_buffs()
        self._sync_managed_state_buffs()
        self._apply_pending_remove_ids()
        self._refresh_attr_range_effects()
        self._report_validation_issues()
        self._recompute_inventory_passive_attrs()
        _log.INFO(
            "[Life]注册完成 "
            f"status={len(self.state_definitions)} nutrition={len(self.nutrition_definitions)} "
            f"attr={len(self.attr_definitions)} "
            f"buff={len(self.buff_registry)} item={len(self.item_registry)} "
            f"trigger={len(self.event_trigger_registry)} outcome={len(self.event_outcome_registry)} "
            f"passive_buff={len(self.passive_buff_registry)} tag={len(self.tag_registry)}"
        )

    def add_remove_ids(self, remove_dict: dict[str, list[str]]) -> None:
        """从 mod 的 remove_ids 配置中累积要删除的注册表条目。"""
        if not isinstance(remove_dict, dict):
            return
        for registry_type, id_list in remove_dict.items():
            rtype = str(registry_type).strip()
            if not rtype or not isinstance(id_list, list):
                continue
            target = self._pending_remove_ids.setdefault(rtype, set())
            for rid in id_list:
                rid_str = str(rid).strip()
                if rid_str:
                    target.add(rid_str)

    def clear_remove_ids(self) -> None:
        """清空待删除列表（mod 卸载后重置时调用）。"""
        self._pending_remove_ids.clear()

    def _apply_pending_remove_ids(self) -> None:
        """在 reload_registries 末尾应用所有待删除条目。"""
        if not self._pending_remove_ids:
            return

        _REGISTRY_MAP: dict[str, dict[str, Any]] = {
            "buff": self.buff_registry,
            "item": self.item_registry,
            "event_trigger": self.event_trigger_registry,
            "event_outcome": self.event_outcome_registry,
            "passive_buff": self.passive_buff_registry,
        }

        total_removed = 0
        for registry_type, ids_to_remove in self._pending_remove_ids.items():
            registry = _REGISTRY_MAP.get(registry_type)
            if registry is not None:
                for rid in ids_to_remove:
                    if rid in registry:
                        registry.pop(rid)
                        total_removed += 1
                        _log.DEBUG(f"[Life][remove_ids]{registry_type}/{rid} 已移除")
                continue

            # status / nutrition / attrs 使用 definitions 字典
            if registry_type == "status":
                for rid in ids_to_remove:
                    if rid in self.state_definitions:
                        self.state_definitions.pop(rid)
                        # 同步清理 managed buff 中依赖该状态的效果
                        self.profile.active_effects = [
                            e for e in self.profile.active_effects
                            if not (e.managed and e.source == f"state:{rid}")
                        ]
                        total_removed += 1
                        _log.DEBUG(f"[Life][remove_ids]status/{rid} 已移除")
            elif registry_type == "nutrition":
                for rid in ids_to_remove:
                    if rid in self.nutrition_definitions:
                        self.nutrition_definitions.pop(rid)
                        self.profile.nutrition.pop(rid, None)
                        # 清理依赖该营养的 managed buff
                        self.profile.active_effects = [
                            e for e in self.profile.active_effects
                            if not (e.managed and e.source == f"nutrition:{rid}")
                        ]
                        total_removed += 1
                        _log.DEBUG(f"[Life][remove_ids]nutrition/{rid} 已移除")
            elif registry_type == "attrs":
                for rid in ids_to_remove:
                    if rid in self.attr_definitions:
                        self.attr_definitions.pop(rid)
                        total_removed += 1
                        _log.DEBUG(f"[Life][remove_ids]attrs/{rid} 已移除")

        if total_removed:
            _log.INFO(f"[Life][remove_ids]共移除 {total_removed} 个条目")

    def _append_unique_path(self, target: list[Path], path_like: str | Path) -> bool:
        path = Path(path_like)
        if path in target:
            return False
        target.append(path)
        return True

    def _remove_path(self, target: list[Path], path_like: str | Path) -> bool:
        path = Path(path_like)
        if path not in target:
            return False
        target.remove(path)
        return True

    def _iter_status_dirs(self) -> list[Path]:
        return [self.status_dir, *self.extra_status_dirs]

    def _iter_buff_dirs(self) -> list[Path]:
        return [self.buff_dir, *self.extra_buff_dirs]

    def _iter_item_dirs(self) -> list[Path]:
        return [self.item_dir, *self.extra_item_dirs]

    def _iter_nutrition_dirs(self) -> list[Path]:
        return [self.nutrition_dir, *self.extra_nutrition_dirs]

    def _iter_event_trigger_dirs(self) -> list[Path]:
        return [self.event_trigger_dir, *self.extra_event_trigger_dirs]

    def _iter_event_outcome_dirs(self) -> list[Path]:
        return [self.event_outcome_dir, *self.extra_event_outcome_dirs]

    def _iter_passive_buff_dirs(self) -> list[Path]:
        return [self.passive_buff_dir, *self.extra_passive_buff_dirs]

    def _iter_attr_dirs(self) -> list[Path]:
        return [self.attr_dir, *self.extra_attr_dirs]

    def _iter_tag_dirs(self) -> list[Path]:
        return [self.tag_dir, *self.extra_tag_dirs]

    def _iter_level_dirs(self) -> list[Path]:
        return [self.level_dir, *self.extra_level_dirs]

    # --------------------------------------------------------------------------- #
    # 全局等级系统
    # --------------------------------------------------------------------------- #

    def _load_level_config(self) -> None:
        """从 level_setting.json 加载等级配置，构建 _exp_table 和 _max_level。
        若存在多个 level 目录（mod 注入），最后一个有效的 level_setting.json 覆盖前者。
        """
        raw: dict[str, Any] | None = None
        for directory in self._iter_level_dirs():
            cfg_path = directory / "level_setting.json"
            if cfg_path.exists():
                try:
                    candidate = json.loads(cfg_path.read_text(encoding="utf-8"))
                    if isinstance(candidate, dict):
                        raw = candidate
                except Exception as exc:
                    _log.WARN(f"[Life][Level]读取 level_setting.json 失败: {exc}")

        if raw is None:
            _log.WARN("[Life][Level]未找到 level_setting.json，等级系统使用默认配置（最高1级）")
            self._exp_table = {}
            self._max_level = 1
            self._passive_exp_per_tick = 0.0
            return

        issues = validate_level_config(raw)
        for issue in issues:
            if issue.level == "error":
                _log.WARN(f"[Life][Level]level_setting.json 校验错误: {issue.message} ({issue.field})")

        init_exp = float(raw.get("initial_exp_required", 100.0))
        self._passive_exp_per_tick = float(raw.get("passive_exp_per_tick", 0.0))

        growth_ranges: list[dict[str, Any]] = raw.get("growth_ranges", [])
        if not isinstance(growth_ranges, list):
            growth_ranges = []

        # 按 from_level 升序排列，找到第一个断层截断
        try:
            growth_ranges_sorted = sorted(
                [r for r in growth_ranges if isinstance(r, dict)],
                key=lambda r: int(r.get("from_level", 0))
            )
        except Exception:
            growth_ranges_sorted = []

        # 构建各等级升级所需经验
        exp_table: dict[int, float] = {}
        current_required = init_exp
        max_to_level = 0

        prev_to = 0  # 用于检测断层
        for rng in growth_ranges_sorted:
            try:
                fl = int(rng["from_level"])
                tl = int(rng["to_level"])
                eg = float(rng["exp_growth"])
            except (KeyError, TypeError, ValueError):
                continue

            # 检测断层
            if prev_to > 0 and fl != prev_to + 1:
                _log.DEBUG(f"[Life][Level]等级区间断层，截断于 {prev_to} 级")
                break

            for level in range(fl, tl + 1):
                if level > fl:
                    current_required = max(0.01, current_required + eg)
                # 升级经验超出 INT_MAX 则截断，不再注册更高等级
                if current_required > _EXP_MAX:
                    _log.DEBUG(f"[Life][Level]等级 {level} 升级经验 {current_required:.0f} 超出上限，截断于 {max_to_level} 级")
                    break
                exp_table[level] = current_required
                max_to_level = level
            else:
                # 为下一个区间更新当前 required（累加一次 growth 以便衔接）
                current_required = max(0.01, current_required + eg)
                prev_to = tl
                continue
            break  # 内层 break 触发，跳出外层循环

        self._exp_table = exp_table
        self._max_level = max_to_level if max_to_level > 0 else 1
        # 满级本身没有"升到下一级"的需求，移除该表项（避免满级仍提示还需经验）
        self._exp_table.pop(self._max_level, None)
        _log.INFO(f"[Life][Level]等级系统已加载: max_level={self._max_level} passive_exp={self._passive_exp_per_tick}")

    def reload_level_config(self) -> None:
        """重新加载等级配置（mod 加载/卸载后调用）。满级 clamp 当前等级。"""
        self._load_level_config()
        if self.profile.level > self._max_level:
            _log.INFO(f"[Life][Level]当前等级 {self.profile.level} 超出新最高等级 {self._max_level}，已 clamp")
            self.profile.level = self._max_level

    @property
    def max_level(self) -> int:
        return self._max_level

    def get_exp_required(self, level: int) -> float | None:
        """返回从 level 升到 level+1 所需经验值；满级时返回 None。"""
        return self._exp_table.get(level)

    def get_passive_exp_per_tick(self) -> float:
        """返回当前每 tick 总被动经验（基础 + 背包加成）。"""
        return self._passive_exp_per_tick + self._inventory_passive_exp_bonus

    def get_level_snapshot(self) -> dict[str, Any]:
        """返回全局等级快照供 UI 使用。"""
        return {
            "level": self.profile.level,
            "max_level": self._max_level,
            "exp": self.profile.exp,
            "exp_required": self._exp_table.get(self.profile.level),
            "passive_exp_per_tick": self.get_passive_exp_per_tick(),
        }

    def set_level(self, level: int) -> bool:
        """调试专用：直接设置等级并同步属性加成，经验重置为 0。"""
        level = max(1, min(int(level), self._max_level))
        current = self.profile.level
        if level > current:
            for lv in range(current + 1, level + 1):
                self._apply_char_level_attr_bonus(lv)
        elif level < current:
            for attr_id in list(self.profile.attrs):
                self.profile.attrs[attr_id] = self.profile.attr_base.get(attr_id, 10.0)
            for lv in range(2, level + 1):
                self._apply_char_level_attr_bonus(lv)
        self.profile.level = level
        self.profile.exp = 0.0
        return True

    def set_exp(self, exp: float) -> bool:
        """调试专用：直接设置经验值并处理升级。"""
        self.profile.exp = min(_EXP_MAX, max(0.0, float(exp)))
        self._process_char_levelup()
        return True

    def attach_mod_resource_dirs(
        self,
        *,
        status_dir: str | Path | None = None,
        buff_dir: str | Path | None = None,
        item_dir: str | Path | None = None,
        nutrition_dir: str | Path | None = None,
        event_trigger_dir: str | Path | None = None,
        event_outcome_dir: str | Path | None = None,
        passive_buff_dir: str | Path | None = None,
        attr_dir: str | Path | None = None,
        level_dir: str | Path | None = None,
        tag_dir: str | Path | None = None,
        reload: bool = True,
    ) -> None:
        changed = False
        if status_dir is not None:
            changed = self._append_unique_path(self.extra_status_dirs, status_dir) or changed
        if buff_dir is not None:
            changed = self._append_unique_path(self.extra_buff_dirs, buff_dir) or changed
        if item_dir is not None:
            changed = self._append_unique_path(self.extra_item_dirs, item_dir) or changed
        if nutrition_dir is not None:
            changed = self._append_unique_path(self.extra_nutrition_dirs, nutrition_dir) or changed
        if event_trigger_dir is not None:
            changed = self._append_unique_path(self.extra_event_trigger_dirs, event_trigger_dir) or changed
        if event_outcome_dir is not None:
            changed = self._append_unique_path(self.extra_event_outcome_dirs, event_outcome_dir) or changed
        if passive_buff_dir is not None:
            changed = self._append_unique_path(self.extra_passive_buff_dirs, passive_buff_dir) or changed
        if attr_dir is not None:
            changed = self._append_unique_path(self.extra_attr_dirs, attr_dir) or changed
        if level_dir is not None:
            if self._append_unique_path(self.extra_level_dirs, level_dir):
                self.reload_level_config()
        if tag_dir is not None:
            changed = self._append_unique_path(self.extra_tag_dirs, tag_dir) or changed
        if changed and reload:
            self.reload_registries()

    def detach_mod_resource_dirs(
        self,
        *,
        status_dir: str | Path | None = None,
        buff_dir: str | Path | None = None,
        item_dir: str | Path | None = None,
        nutrition_dir: str | Path | None = None,
        event_trigger_dir: str | Path | None = None,
        event_outcome_dir: str | Path | None = None,
        passive_buff_dir: str | Path | None = None,
        attr_dir: str | Path | None = None,
        level_dir: str | Path | None = None,
        tag_dir: str | Path | None = None,
        reload: bool = True,
    ) -> None:
        changed = False
        if status_dir is not None:
            changed = self._remove_path(self.extra_status_dirs, status_dir) or changed
        if buff_dir is not None:
            changed = self._remove_path(self.extra_buff_dirs, buff_dir) or changed
        if item_dir is not None:
            changed = self._remove_path(self.extra_item_dirs, item_dir) or changed
        if nutrition_dir is not None:
            changed = self._remove_path(self.extra_nutrition_dirs, nutrition_dir) or changed
        if event_trigger_dir is not None:
            changed = self._remove_path(self.extra_event_trigger_dirs, event_trigger_dir) or changed
        if event_outcome_dir is not None:
            changed = self._remove_path(self.extra_event_outcome_dirs, event_outcome_dir) or changed
        if passive_buff_dir is not None:
            changed = self._remove_path(self.extra_passive_buff_dirs, passive_buff_dir) or changed
        if attr_dir is not None:
            changed = self._remove_path(self.extra_attr_dirs, attr_dir) or changed
        if level_dir is not None:
            if self._remove_path(self.extra_level_dirs, level_dir):
                self.reload_level_config()
        if tag_dir is not None:
            changed = self._remove_path(self.extra_tag_dirs, tag_dir) or changed
        if changed and reload:
            self.reload_registries()

    def _build_default_state_definitions(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for index, state_id in enumerate(BASE_STATES):
            result[state_id] = {
                "id": state_id,
                "name": state_id,
                "i18n_key": f"life.state.{state_id}",
                "default": 100.0,
                "min": 0.0,
                "max": GLOBAL_VALUE_MAX,
                "order": index,
            }
        return result

    def _build_default_attr_definitions(self) -> dict[str, dict[str, Any]]:
        _FALLBACK_COLORS = {
            "vit": "#e06c75", "str": "#d4834a", "spd": "#c8b840",
            "agi": "#5ab86c", "spi": "#4ea8d8", "int": "#8b6fd6", "ill": "#888888",
        }
        result: dict[str, dict[str, Any]] = {}
        for index, attr_id in enumerate(BASE_ATTRS):
            result[attr_id] = {
                "id": attr_id,
                "name": attr_id,
                "i18n_key": f"life.attr.{attr_id}",
                "color": _FALLBACK_COLORS.get(attr_id, "#666666"),
                "initial": 10.0,
                "order": (index + 1) * 10,
            }
        return result

    def _load_attr_definitions(self) -> dict[str, dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        scanned_dirs = 0
        scanned_files = 0
        for directory in self._iter_attr_dirs():
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                scanned_files += 1
                payload = self._read_json(file_path)
                if isinstance(payload, dict) and "id" in payload:
                    loaded.append(payload)
                elif isinstance(payload, list):
                    loaded.extend([r for r in payload if isinstance(r, dict)])

        if not loaded:
            _log.WARN(
                f"[Life][Register][Attr]未发现属性定义，使用默认属性。"
                f"dirs={scanned_dirs} files={scanned_files} default={len(BASE_ATTRS)}"
            )
            return self._build_default_attr_definitions()

        issues: list[ValidationIssue] = []
        normalized: list[dict[str, Any]] = []
        _FALLBACK_COLORS = {
            "vit": "#e06c75", "str": "#d4834a", "spd": "#c8b840",
            "agi": "#5ab86c", "spi": "#4ea8d8", "int": "#8b6fd6", "ill": "#888888",
        }
        for index, record in enumerate(loaded):
            issues.extend(validate_attr_record(record, "attrs_dir"))
            attr_id = str(record.get("id") or "").strip()
            if not attr_id:
                continue
            initial = self._to_float_safe(record.get("initial", 10.0), 10.0)
            color = str(record.get("color") or _FALLBACK_COLORS.get(attr_id, "#666666"))
            name = str(record.get("name") or attr_id)
            i18n_key = str(record.get("i18n_key") or f"life.attr.{attr_id}")
            order_raw = record.get("order", index)
            try:
                order = int(order_raw)
            except Exception:
                order = index
            # level_table 经验/等级表（可选）
            level_table_raw = record.get("level_table")
            level_table: list[dict[str, Any]] = []
            if isinstance(level_table_raw, list):
                for lt_entry in level_table_raw:
                    if not isinstance(lt_entry, dict):
                        continue
                    try:
                        lv = int(lt_entry["level"])
                        exp_req = float(lt_entry["exp_required"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    bonus = dict(lt_entry["permanent_bonus"]) if isinstance(lt_entry.get("permanent_bonus"), dict) else {}
                    level_table.append({"level": lv, "exp_required": exp_req, "permanent_bonus": bonus})
                level_table.sort(key=lambda e: e["level"])
            # char_level_bonuses 全局等级驱动的属性加成（可选）
            char_level_bonuses_raw = record.get("char_level_bonuses")
            char_level_bonuses: list[dict[str, Any]] = []
            if isinstance(char_level_bonuses_raw, list):
                for clb in char_level_bonuses_raw:
                    if isinstance(clb, dict):
                        char_level_bonuses.append(clb)
            normalized.append({"id": attr_id, "name": name, "i18n_key": i18n_key,
                                "color": color, "initial": initial, "order": order,
                                "level_table": level_table,
                                "char_level_bonuses": char_level_bonuses})

        if not normalized:
            return self._build_default_attr_definitions()

        normalized.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("id", ""))))
        result: dict[str, dict[str, Any]] = {}
        for item in normalized:
            attr_id = str(item["id"])
            if attr_id in result:
                _log.WARN(f"[Life][Register][Attr]重复属性ID，后者覆盖前者: {attr_id}")
            result[attr_id] = item
        _log.INFO(
            f"[Life][Register][Attr]dirs={scanned_dirs} files={scanned_files} records={len(result)}"
        )
        return result

    def _sync_profile_attrs(self, next_defs: dict[str, dict[str, Any]]) -> None:
        """新增属性添加默认值；已有属性检测 initial 变化并同步差值；已废弃属性保留。"""
        for attr_id, defn in next_defs.items():
            new_initial = float(defn.get("initial", 10.0))
            if attr_id not in self.profile.attrs:
                # 全新属性
                self.profile.attrs[attr_id] = new_initial
                self.profile.attr_base[attr_id] = new_initial
            else:
                # 已有属性：检测 initial 变化
                old_initial = self.profile.attr_base.get(attr_id, new_initial)
                if abs(new_initial - old_initial) > 1e-9:
                    delta = new_initial - old_initial
                    self.profile.attrs[attr_id] += delta
                    self.profile.attr_base[attr_id] = new_initial
                elif attr_id not in self.profile.attr_base:
                    self.profile.attr_base[attr_id] = new_initial
            if attr_id not in self.profile.attr_exp:
                self.profile.attr_exp[attr_id] = 0.0
            if attr_id not in self.profile.attr_level:
                self.profile.attr_level[attr_id] = 0
    def _load_state_definitions(self) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        loaded: list[dict[str, Any]] = []
        scanned_dirs = 0
        scanned_files = 0
        issues: list[ValidationIssue] = []
        for directory in self._iter_status_dirs():
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                scanned_files += 1
                payload = self._read_json(file_path)
                if isinstance(payload, dict) and "id" in payload:
                    issues.extend(validate_state_record(payload, str(file_path)))
                    loaded.append(payload)
                elif isinstance(payload, list):
                    for r in payload:
                        if isinstance(r, dict):
                            issues.extend(validate_state_record(r, str(file_path)))
                            loaded.append(r)

        if not loaded:
            _log.WARN(
                f"[Life][Register][Status]未发现状态定义，使用默认状态。"
                f"dirs={scanned_dirs} files={scanned_files} default={len(BASE_STATES)}"
            )
            return self._build_default_state_definitions(), issues

        normalized: list[dict[str, Any]] = []
        for index, record in enumerate(loaded):
            state_id = str(record.get("id") or "").strip()
            if not state_id:
                continue

            default_value = self._to_float_safe(record.get("default", 100.0), 100.0)
            min_value = self._to_float_safe(record.get("min", 0.0), 0.0)
            max_value = self._to_float_safe(record.get("max", 100.0), 100.0)
            if min_value > max_value:
                min_value, max_value = max_value, min_value

            name = str(record.get("name") or state_id)
            i18n_key = str(record.get("i18n_key") or f"life.state.{state_id}")
            order_raw = record.get("order", index)
            try:
                order = int(order_raw)
            except Exception:
                order = index

            effects_payload = record.get("effects", [])
            effects: list[dict[str, Any]] = []
            if isinstance(effects_payload, list):
                for effect in effects_payload:
                    if not isinstance(effect, dict):
                        continue
                    states = effect.get("states", {})
                    attrs = effect.get("attrs", {})
                    buff_id = effect.get("buff_id")
                    entry: dict[str, Any] = {
                        "min": self._to_float_safe(effect.get("min", float("-inf")), float("-inf")),
                        "max": self._to_float_safe(effect.get("max", float("inf")), float("inf")),
                        "percent_min": self._to_float_safe(effect.get("percent_min", float("-inf")), float("-inf")),
                        "percent_max": self._to_float_safe(effect.get("percent_max", float("inf")), float("inf")),
                        "states": dict(states) if isinstance(states, dict) else {},
                        "attrs": dict(attrs) if isinstance(attrs, dict) else {},
                    }
                    if buff_id is not None:
                        entry["buff_id"] = str(buff_id)
                    # 保留条件字段（requires_buff / requires_no_buff）
                    for cond_key in ("requires_buff", "requires_no_buff"):
                        if cond_key in effect:
                            entry[cond_key] = effect[cond_key]
                    effects.append(entry)

            normalized.append(
                {
                    "id": state_id,
                    "name": name,
                    "i18n_key": i18n_key,
                    "default": default_value,
                    "min": min_value,
                    "max": max_value,
                    "order": order,
                    "effects": effects,
                }
            )

        if not normalized:
            return self._build_default_state_definitions(), issues

        normalized.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("id", ""))))
        result: dict[str, dict[str, Any]] = {}
        duplicate_count = 0
        for item in normalized:
            state_id = str(item["id"])
            if state_id in result:
                duplicate_count += 1
                _log.WARN(f"[Life][Register][Status]重复状态ID，后者覆盖前者: {state_id}")
            result[state_id] = item
        _log.INFO(
            f"[Life][Register][Status]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(result)} duplicates={duplicate_count}"
        )
        return result, issues

    def _load_nutrition_definitions(self) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        loaded: list[dict[str, Any]] = []
        scanned_dirs = 0
        scanned_files = 0
        issues: list[ValidationIssue] = []
        for directory in self._iter_nutrition_dirs():
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                scanned_files += 1
                payload = self._read_json(file_path)
                if isinstance(payload, dict) and "id" in payload:
                    issues.extend(validate_nutrition_record(payload, str(file_path)))
                    loaded.append(payload)
                elif isinstance(payload, list):
                    for r in payload:
                        if isinstance(r, dict):
                            issues.extend(validate_nutrition_record(r, str(file_path)))
                            loaded.append(r)

        normalized: list[dict[str, Any]] = []
        for index, record in enumerate(loaded):
            nutrition_id = str(record.get("id") or "").strip()
            if not nutrition_id:
                continue

            default_value = self._to_float_safe(record.get("default", 0.0), 0.0)
            min_value = self._to_float_safe(record.get("min", 0.0), 0.0)
            max_value = self._to_float_safe(record.get("max", 100.0), 100.0)
            if min_value > max_value:
                min_value, max_value = max_value, min_value

            decay_value = max(0.0, self._to_float_safe(record.get("decay", 0.0), 0.0))
            name = str(record.get("name") or nutrition_id)
            i18n_key = str(record.get("i18n_key") or f"life.nutrition.{nutrition_id}")
            order_raw = record.get("order", index)
            try:
                order = int(order_raw)
            except Exception:
                order = index

            effects_payload = record.get("effects", [])
            effects: list[dict[str, Any]] = []
            if isinstance(effects_payload, list):
                for effect in effects_payload:
                    if not isinstance(effect, dict):
                        continue
                    states = effect.get("states", {})
                    attrs = effect.get("attrs", {})
                    buff_id = effect.get("buff_id")
                    entry: dict[str, Any] = {
                        "min": self._to_float_safe(effect.get("min", float("-inf")), float("-inf")),
                        "max": self._to_float_safe(effect.get("max", float("inf")), float("inf")),
                        "percent_min": self._to_float_safe(effect.get("percent_min", float("-inf")), float("-inf")),
                        "percent_max": self._to_float_safe(effect.get("percent_max", float("inf")), float("inf")),
                        "states": dict(states) if isinstance(states, dict) else {},
                        "attrs": dict(attrs) if isinstance(attrs, dict) else {},
                    }
                    if buff_id is not None:
                        entry["buff_id"] = str(buff_id)
                    # 保留条件字段（requires_buff / requires_no_buff）
                    for cond_key in ("requires_buff", "requires_no_buff"):
                        if cond_key in effect:
                            entry[cond_key] = effect[cond_key]
                    effects.append(entry)

            normalized.append(
                {
                    "id": nutrition_id,
                    "name": name,
                    "i18n_key": i18n_key,
                    "default": max(min_value, min(max_value, default_value)),
                    "min": min_value,
                    "max": max_value,
                    "order": order,
                    "decay": decay_value,
                    "effects": effects,
                }
            )

        normalized.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("id", ""))))
        result: dict[str, dict[str, Any]] = {}
        duplicate_count = 0
        for item in normalized:
            nutrition_id = str(item["id"])
            if nutrition_id in result:
                duplicate_count += 1
                _log.WARN(f"[Life][Register][Nutrition]重复营养ID，后者覆盖前者: {nutrition_id}")
            result[nutrition_id] = item
        _log.INFO(
            f"[Life][Register][Nutrition]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(result)} duplicates={duplicate_count}"
        )
        return result, issues

    def _sync_profile_states(self, next_state_defs: dict[str, dict[str, Any]]) -> None:
        old_states = dict(self.profile.states)
        old_max = dict(self.profile.state_max)
        old_min = dict(self.profile.state_min)

        self.state_definitions = next_state_defs

        new_states: dict[str, float] = {}
        new_max: dict[str, float] = {}
        new_min: dict[str, float] = {}
        for state_key, defn in self.state_definitions.items():
            min_v = float(old_min.get(state_key, defn["min"]))
            max_v = float(old_max.get(state_key, defn["max"]))
            if min_v > max_v:
                min_v, max_v = max_v, min_v

            current = float(old_states.get(state_key, defn["default"]))
            current = max(min_v, min(max_v, current))
            new_states[state_key] = current
            new_min[state_key] = min_v
            new_max[state_key] = max_v

        self.profile.states = new_states
        self.profile.state_min = new_min
        self.profile.state_max = new_max

        self._attr_cap_bonus_max = {k: float(self._attr_cap_bonus_max.get(k, 0.0)) for k in self.state_keys}
        self._attr_cap_bonus_min = {k: float(self._attr_cap_bonus_min.get(k, 0.0)) for k in self.state_keys}

    def _sync_profile_nutrition(self, next_nutrition_defs: dict[str, dict[str, Any]]) -> None:
        old_nutrition = dict(self.profile.nutrition)

        self.nutrition_definitions = next_nutrition_defs

        new_nutrition: dict[str, float] = {}
        for nutrition_key, defn in self.nutrition_definitions.items():
            min_v = float(defn["min"])
            max_v = float(defn["max"])
            current = float(old_nutrition.get(nutrition_key, defn["default"]))
            new_nutrition[nutrition_key] = max(min_v, min(max_v, current))

        self.profile.nutrition = new_nutrition

    def _report_validation_issues(self) -> None:
        if not self.validation_issues:
            _log.DEBUG("[Life]schema校验通过")
            return

        error_count = 0
        warn_count = 0
        for issue in self.validation_issues:
            text = (
                f"[Life][schema][{issue.level}] {issue.source} "
                f"record={issue.record_id} field={issue.field} msg={issue.message}"
            )
            if issue.level == "error":
                error_count += 1
                _log.ERROR(text)
            else:
                warn_count += 1
                _log.WARN(text)

        _log.DEBUG(f"[Life]schema校验完成 error={error_count} warn={warn_count}")

    def _load_attribute_rules(self, buff_registry: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        rules: dict[str, list[dict[str, Any]]] = {}
        for record in buff_registry.values():
            attr_name = str(record.get("attribute", "")).strip()
            status_rules = record.get("status")
            if not attr_name or not isinstance(status_rules, list):
                continue

            parsed: list[dict[str, Any]] = []
            for rule in status_rules:
                if isinstance(rule, dict):
                    min_v = float(rule.get("min", float("-inf")))
                    max_v = float(rule.get("max", float("inf")))
                    effects = rule.get("effects", {})
                    if isinstance(effects, dict):
                        parsed.append({"min": min_v, "max": max_v, "effects": effects})
                elif isinstance(rule, list) and len(rule) >= 3:
                    # Support draft style: [min, max, {...effects...}]
                    try:
                        min_v = float(rule[0])
                        max_v = float(rule[1])
                        effects = rule[2] if isinstance(rule[2], dict) else {}
                        parsed.append({"min": min_v, "max": max_v, "effects": effects})
                    except Exception:
                        continue

            if parsed:
                rules[attr_name] = parsed

        return rules

    def _load_registry_dir(
        self,
        directories: list[Path],
        kind: str,
        state_keys: tuple[str, ...],
        attr_keys: tuple[str, ...],
        nutrition_keys: tuple[str, ...] = (),
    ) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        result: dict[str, dict[str, Any]] = {}
        issues: list[ValidationIssue] = []
        scanned_dirs = 0
        scanned_files = 0
        duplicate_count = 0
        for directory in directories:
            if not directory.exists():
                continue
            scanned_dirs += 1

            for file_path in sorted(directory.rglob("*.json")):
                if file_path.name == "class.json":
                    continue
                scanned_files += 1
                payload = self._read_json(file_path)
                if not payload:
                    continue

                # 查找最近的 class.json（仅 buff 使用）
                classes: list[str] = []
                if kind == "buff":
                    classes = self._resolve_buff_classes(file_path, directory)

                records: list[dict[str, Any]]
                if isinstance(payload, list):
                    records = [r for r in payload if isinstance(r, dict)]
                elif isinstance(payload, dict):
                    if "id" in payload:
                        records = [payload]
                    else:
                        records = [v for v in payload.values() if isinstance(v, dict)]
                else:
                    continue

                for record in records:
                    record_id = str(record.get("id") or record.get("name") or "").strip()
                    if not record_id:
                        continue
                    if kind == "buff":
                        issues.extend(validate_buff_record(record, str(file_path), state_keys=state_keys, attr_keys=attr_keys, nutrition_keys=nutrition_keys))
                        if classes:
                            record["_classes"] = classes
                    if record_id in result:
                        duplicate_count += 1
                        _log.INFO(f"[Life][Register][{kind}]已存在，mod 覆写字段: {record_id} file={file_path}")
                        existing = result[record_id]
                        existing.update(record)
                        record = existing
                    result[record_id] = record

        _log.INFO(
            f"[Life][Register][{kind}]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(result)} issues={len(issues)} duplicates={duplicate_count}"
        )
        return result, issues

    def _resolve_buff_classes(self, file_path: Path, root: Path) -> list[str]:
        """从 buff 文件所在目录向上查找最近的 class.json。"""
        current = file_path.parent
        while True:
            class_file = current / "class.json"
            if class_file.exists():
                data = self._read_json(class_file)
                if isinstance(data, dict):
                    classes = data.get("classes", [])
                    if isinstance(classes, list):
                        return [str(c).strip() for c in classes if str(c).strip()]
                elif isinstance(data, list):
                    return [str(c).strip() for c in data if str(c).strip()]
            if current == root or current.parent == current:
                break
            current = current.parent
        return []

    def get_buff_class_registry(self) -> dict[str, dict[str, Any]]:
        """返回从所有 buff class.json 收集的分类注册表。"""
        registry: dict[str, dict[str, Any]] = {}
        for root in self._iter_buff_dirs():
            if not root.exists():
                continue
            for class_file in sorted(root.rglob("class.json")):
                data = self._read_json(class_file)
                if not isinstance(data, dict):
                    continue
                classes = data.get("classes", [])
                if not isinstance(classes, list):
                    continue
                class_defs = data.get("class_definitions", {})
                for cls_id_raw in classes:
                    cls_id = str(cls_id_raw).strip()
                    if not cls_id or cls_id in registry:
                        continue
                    cls_def = class_defs.get(cls_id, {}) if isinstance(class_defs, dict) else {}
                    if not isinstance(cls_def, dict):
                        cls_def = {}
                    registry[cls_id] = {
                        "name": cls_def.get("name", cls_id),
                        "name_i18n_key": cls_def.get("name_i18n_key", f"life.buff_class.{cls_id}"),
                    }
        return registry

    def get_buff_classes(self, buff_id: str) -> list[str]:
        """返回指定 buff 的分类列表。"""
        record = self.buff_registry.get(buff_id)
        if not record:
            return []
        return list(record.get("_classes", []))

    def _load_item_registry(
        self,
        roots: list[Path],
        state_keys: tuple[str, ...],
        attr_keys: tuple[str, ...],
        nutrition_keys: tuple[str, ...],
    ) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        registry: dict[str, dict[str, Any]] = {}
        issues: list[ValidationIssue] = []
        scanned_dirs = 0
        scanned_files = 0
        duplicate_count = 0
        for root in roots:
            if not root.exists():
                continue
            scanned_dirs += 1

            for file_path in sorted(root.rglob("*.json")):
                if file_path.name in ("starter_inventory.json", "class.json"):
                    continue
                scanned_files += 1
                payload = self._read_json(file_path)
                # 查找最近的 class.json 以确定分类
                classes = self._resolve_item_classes(file_path, root)
                if isinstance(payload, dict) and "id" in payload:
                    category = file_path.parent.name
                    item_id = str(payload["id"])
                    payload["category"] = category
                    if classes:
                        payload["_classes"] = classes
                    issues.extend(
                        validate_item_record(
                            payload,
                            str(file_path),
                            state_keys=state_keys,
                            attr_keys=attr_keys,
                            nutrition_keys=nutrition_keys,
                        )
                    )
                    if item_id in registry:
                        duplicate_count += 1
                        _log.INFO(f"[Life][Register][item]已存在，mod 覆写字段: {item_id} file={file_path}")
                    registry[item_id] = payload
                elif isinstance(payload, list):
                    category = file_path.parent.name
                    for item in payload:
                        if isinstance(item, dict) and "id" in item:
                            item_id = str(item["id"])
                            item["category"] = category
                            if classes:
                                item["_classes"] = classes
                            issues.extend(
                                validate_item_record(
                                    item,
                                    str(file_path),
                                    state_keys=state_keys,
                                    attr_keys=attr_keys,
                                    nutrition_keys=nutrition_keys,
                                )
                            )
                            if item_id in registry:
                                duplicate_count += 1
                                _log.INFO(f"[Life][Register][item]已存在，mod 覆写字段: {item_id} file={file_path}")
                            registry[item_id] = item

        _log.INFO(
            f"[Life][Register][item]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(registry)} issues={len(issues)} duplicates={duplicate_count}"
        )
        return registry, issues

    def _resolve_item_classes(self, file_path: Path, root: Path) -> list[str]:
        """从物品文件所在目录向上查找最近的 class.json，返回分类列表。"""
        current = file_path.parent
        while True:
            class_file = current / "class.json"
            if class_file.exists():
                data = self._read_json(class_file)
                if isinstance(data, dict):
                    classes = data.get("classes", [])
                    if isinstance(classes, list):
                        return [str(c).strip() for c in classes if str(c).strip()]
                elif isinstance(data, list):
                    return [str(c).strip() for c in data if str(c).strip()]
            if current == root or current.parent == current:
                break
            current = current.parent
        return []

    def get_item_class_registry(self) -> dict[str, dict[str, Any]]:
        """返回从所有 class.json 收集的分类注册表。
        键=分类ID, 值={name, name_i18n_key}。"""
        registry: dict[str, dict[str, Any]] = {}
        for root in self._iter_item_dirs():
            if not root.exists():
                continue
            for class_file in sorted(root.rglob("class.json")):
                data = self._read_json(class_file)
                if not isinstance(data, dict):
                    continue
                classes = data.get("classes", [])
                if not isinstance(classes, list):
                    continue
                class_defs = data.get("class_definitions", {})
                for cls_id_raw in classes:
                    cls_id = str(cls_id_raw).strip()
                    if not cls_id or cls_id in registry:
                        continue
                    cls_def = class_defs.get(cls_id, {}) if isinstance(class_defs, dict) else {}
                    if not isinstance(cls_def, dict):
                        cls_def = {}
                    registry[cls_id] = {
                        "name": cls_def.get("name", cls_id),
                        "name_i18n_key": cls_def.get("name_i18n_key", f"life.item_class.{cls_id}"),
                    }
        return registry

    def _read_json(self, file_path: Path) -> Any:
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as exc:
            _log.ERROR(f"[Life]读取JSON失败 {file_path}: {exc}")
            return None

    def _load_event_registry(
        self,
        directories: list[Path],
        kind: str,
    ) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        registry: dict[str, dict[str, Any]] = {}
        issues: list[ValidationIssue] = []
        scanned_dirs = 0
        scanned_files = 0
        duplicate_count = 0
        validate_fn = validate_event_trigger_record if kind == "event_trigger" else validate_event_outcome_record
        for directory in directories:
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                if file_path.name == "class.json":
                    continue
                scanned_files += 1
                payload = self._read_json(file_path)
                if not payload:
                    continue
                # 查找最近的 class.json（仅 trigger 使用）
                classes: list[str] = []
                if kind == "event_trigger":
                    classes = self._resolve_event_classes(file_path, directory)
                records: list[dict[str, Any]]
                if isinstance(payload, list):
                    records = [r for r in payload if isinstance(r, dict)]
                elif isinstance(payload, dict):
                    if "id" in payload:
                        records = [payload]
                    else:
                        records = [v for v in payload.values() if isinstance(v, dict)]
                else:
                    continue
                for record in records:
                    record_id = str(record.get("id") or "").strip()
                    if not record_id:
                        continue
                    if classes:
                        record["_classes"] = classes
                    issues.extend(validate_fn(record, str(file_path)))
                    if record_id in registry:
                        duplicate_count += 1
                        _log.INFO(f"[Life][Register][{kind}]已存在，mod 覆写字段: {record_id} file={file_path}")
                    registry[record_id] = record
        _log.INFO(
            f"[Life][Register][{kind}]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(registry)} issues={len(issues)} duplicates={duplicate_count}"
        )
        return registry, issues

    def _load_passive_buff_registry(
        self,
        directories: list[Path],
    ) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
        from module.life.schema import validate_passive_buff_record  # 避免循环导入风险
        registry: dict[str, dict[str, Any]] = {}
        issues: list[ValidationIssue] = []
        scanned_dirs = 0
        scanned_files = 0
        duplicate_count = 0
        for directory in directories:
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                scanned_files += 1
                payload = self._read_json(file_path)
                if not payload:
                    continue
                records: list[dict[str, Any]]
                if isinstance(payload, list):
                    records = [r for r in payload if isinstance(r, dict)]
                elif isinstance(payload, dict):
                    if "id" in payload:
                        records = [payload]
                    else:
                        records = [v for v in payload.values() if isinstance(v, dict)]
                else:
                    continue
                for record in records:
                    record_id = str(record.get("id") or "").strip()
                    if not record_id:
                        continue
                    issues.extend(validate_passive_buff_record(record, str(file_path)))
                    if record_id in registry:
                        duplicate_count += 1
                        _log.INFO(f"[Life][Register][passive_buff]已存在，mod 覆写字段: {record_id} file={file_path}")
                    registry[record_id] = record
        _log.INFO(
            f"[Life][Register][passive_buff]dirs={scanned_dirs} files={scanned_files} "
            f"records={len(registry)} issues={len(issues)} duplicates={duplicate_count}"
        )
        return registry, issues

    def _load_tag_registry(self, directories: list[Path]) -> dict[str, dict[str, Any]]:
        """加载标签注册表。标签定义了 tag_id → buff_id 的映射关系。"""
        registry: dict[str, dict[str, Any]] = {}
        scanned_dirs = 0
        scanned_files = 0
        for directory in directories:
            if not directory.exists():
                continue
            scanned_dirs += 1
            for file_path in sorted(directory.rglob("*.json")):
                scanned_files += 1
                payload = self._read_json(file_path)
                if not payload:
                    continue
                records: list[dict[str, Any]]
                if isinstance(payload, list):
                    records = [r for r in payload if isinstance(r, dict)]
                elif isinstance(payload, dict):
                    if "id" in payload:
                        records = [payload]
                    else:
                        records = [v for v in payload.values() if isinstance(v, dict)]
                else:
                    continue
                for record in records:
                    tag_id = str(record.get("id") or "").strip()
                    if not tag_id:
                        continue
                    buff_id = str(record.get("buff_id") or "").strip()
                    if not buff_id:
                        _log.WARN(f"[Life][Register][tag]标签缺少 buff_id: {tag_id} file={file_path}")
                        continue
                    if tag_id in registry:
                        _log.INFO(f"[Life][Register][tag]已存在，mod 覆写字段: {tag_id} file={file_path}")
                    registry[tag_id] = record
        _log.INFO(f"[Life][Register][tag]dirs={scanned_dirs} files={scanned_files} records={len(registry)}")
        return registry

    def _resolve_event_classes(self, file_path: Path, root: Path) -> list[str]:
        """从事件触发器文件所在目录向上查找最近的 class.json。"""
        current = file_path.parent
        while True:
            class_file = current / "class.json"
            if class_file.exists():
                data = self._read_json(class_file)
                if isinstance(data, dict):
                    classes = data.get("classes", [])
                    if isinstance(classes, list):
                        return [str(c).strip() for c in classes if str(c).strip()]
                elif isinstance(data, list):
                    return [str(c).strip() for c in data if str(c).strip()]
            if current == root or current.parent == current:
                break
            current = current.parent
        return []

    def get_trigger_class_registry(self) -> dict[str, dict[str, Any]]:
        """返回从所有 event_trigger class.json 收集的分类注册表。"""
        registry: dict[str, dict[str, Any]] = {}
        for root in self._iter_event_trigger_dirs():
            if not root.exists():
                continue
            for class_file in sorted(root.rglob("class.json")):
                data = self._read_json(class_file)
                if not isinstance(data, dict):
                    continue
                classes = data.get("classes", [])
                if not isinstance(classes, list):
                    continue
                class_defs = data.get("class_definitions", {})
                for cls_id_raw in classes:
                    cls_id = str(cls_id_raw).strip()
                    if not cls_id or cls_id in registry:
                        continue
                    cls_def = class_defs.get(cls_id, {}) if isinstance(class_defs, dict) else {}
                    if not isinstance(cls_def, dict):
                        cls_def = {}
                    registry[cls_id] = {
                        "name": cls_def.get("name", cls_id),
                        "name_i18n_key": cls_def.get("name_i18n_key", f"life.trigger_class.{cls_id}"),
                    }
        return registry

    def use_item(self, item_id: str) -> bool:
        return self.use_item_with_count(item_id, count=1, consume=False)

    def use_item_with_count(self, item_id: str, count: int = 1, consume: bool = True) -> bool:
        if self.paused:
            _log.WARN("[Life]养成系统已暂停，无法使用物品")
            return False
        item = self.item_registry.get(item_id)
        if not item:
            _log.WARN(f"[Life]未知物品: {item_id}")
            return False
        if not self.can_use_item(item_id):
            _log.WARN(f"[Life]物品不可使用: {item_id}")
            return False

        # JSON 中 consumable: false 可强制不消耗
        if item.get("consumable") is False:
            consume = False

        use_count = max(1, int(count))
        if consume:
            current = self.profile.inventory.get(item_id, 0)
            if current < use_count:
                _log.WARN(f"[Life]物品数量不足: {item_id}, have={current}, need={use_count}")
                return False
            self.profile.inventory[item_id] = current - use_count
            if self.profile.inventory[item_id] <= 0:
                self.profile.inventory.pop(item_id, None)

        for _ in range(use_count):
            self._apply_record(item, source="item")

        # 使用后启动冷却
        cooldown_s = item.get("cooldown_s")
        if cooldown_s is not None:
            try:
                cd = float(cooldown_s)
                if cd > 0:
                    self._item_cooldowns[item_id] = time.time() + cd
            except Exception:
                pass

        if consume:
            self._recompute_inventory_passive_attrs()
        _log.INFO(f"[Life][Item]使用物品成功 id={item_id} count={use_count} consume={consume}")
        # 触发绑定动作（物品 loop 只播放一轮）
        self._trigger_record_action(item, is_item=True)
        return True

    def add_item(self, item_id: str, count: int = 1) -> bool:
        if item_id not in self.item_registry:
            _log.WARN(f"[Life]不能加入未知物品: {item_id}")
            return False
        item = self.item_registry[item_id]
        if item.get("unique", False):
            # 唯一物品：已持有时忽略本次获取，未持有时强制设为 1
            if self.profile.inventory.get(item_id, 0) >= 1:
                return True
            self.profile.inventory[item_id] = 1
        else:
            delta = max(1, int(count))
            self.profile.inventory[item_id] = self.profile.inventory.get(item_id, 0) + delta
        self._recompute_inventory_passive_attrs()
        _log.INFO(f"[Life][Item]获得物品 id={item_id} count={self.profile.inventory.get(item_id, 0)}")
        return True

    def set_item_count(self, item_id: str, count: int) -> bool:
        if item_id not in self.item_registry:
            _log.WARN(f"[Life]不能设置未知物品数量: {item_id}")
            return False
        normalized = max(0, int(count))
        # 唯一物品最多持有 1 个
        item = self.item_registry[item_id]
        if item.get("unique", False):
            normalized = min(normalized, 1)
        if normalized == 0:
            self.profile.inventory.pop(item_id, None)
            self._recompute_inventory_passive_attrs()
            return True
        self.profile.inventory[item_id] = normalized
        self._recompute_inventory_passive_attrs()
        return True

    def list_item_ids(self) -> list[str]:
        return sorted(self.item_registry.keys())

    def set_state_value(self, state_id: str, value: float) -> bool:
        if state_id not in self.profile.states:
            return False
        self.profile.states[state_id] = float(value)
        self._clamp_state(state_id)
        return True

    def set_nutrition_value(self, nutrition_id: str, value: float) -> bool:
        if nutrition_id not in self.profile.nutrition:
            return False
        self.profile.nutrition[nutrition_id] = float(value)
        self._clamp_nutrition(nutrition_id)
        return True

    def _recompute_inventory_passive_attrs(self) -> None:
        """遍历背包，将所有物品的 passive_attr_bonus 按递减公式汇总并缓存。"""
        result: dict[str, float] = {}
        for item_id, count in self.profile.inventory.items():
            item_info = self.item_registry.get(item_id)
            if not item_info:
                continue
            bonus_map = item_info.get("passive_attr_bonus")
            if not isinstance(bonus_map, dict):
                continue
            n = max(1, int(count))
            # n 件同类物品的衰减几何级数和：b * 2 * (1 - 0.5^n)
            decay_factor = 2.0 * (1.0 - 0.5 ** n)
            for attr_key, base_bonus in bonus_map.items():
                try:
                    b = float(base_bonus)
                except Exception:
                    continue
                result[str(attr_key)] = result.get(str(attr_key), 0.0) + b * decay_factor
        self._inventory_passive_attrs = result
        # 被动经验加成（线性叠加，不衰减）
        exp_bonus = 0.0
        for item_id, count in self.profile.inventory.items():
            item_info = self.item_registry.get(item_id)
            if not item_info:
                continue
            raw_peb = item_info.get("passive_exp_bonus")
            if raw_peb is None:
                continue
            try:
                exp_bonus += float(raw_peb) * max(1, int(count))
            except Exception:
                pass
        self._inventory_passive_exp_bonus = exp_bonus

    def _effective_attr(self, attr_key: str) -> float:
        """返回属性有效值（基础值 + 背包被动加成），用于 passive_buff / event 概率计算。"""
        return self.profile.attrs.get(attr_key, 0.0) + self._inventory_passive_attrs.get(attr_key, 0.0)

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        current = self.profile.inventory.get(item_id, 0)
        delta = max(1, int(count))
        if current < delta:
            _log.WARN(f"[Life][Item]移除物品失败 id={item_id} have={current} need={delta}")
            return False
        left = current - delta
        if left <= 0:
            self.profile.inventory.pop(item_id, None)
        else:
            self.profile.inventory[item_id] = left
        self._recompute_inventory_passive_attrs()
        _log.INFO(f"[Life][Item]移除物品 id={item_id} delta={delta} left={self.profile.inventory.get(item_id, 0)}")
        return True

    def get_inventory_snapshot(self) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for item_id, count in sorted(self.profile.inventory.items()):
            item_info = self.item_registry.get(item_id)
            if not isinstance(item_info, dict):
                # 兼容旧存档：未知物品保留在 profile.inventory，但不展示在背包列表。
                continue
            cooldown_remaining = self.get_item_cooldown_remaining(item_id)
            can, reason = self.can_use_item_with_reason(item_id)
            snapshot.append(
                {
                    "id": item_id,
                    "name": self._resolve_record_name(item_info, item_id),
                    "category": item_info.get("category", "unknown"),
                    "classes": list(item_info.get("_classes", [])),
                    "desc": self._resolve_record_desc(item_info),
                    "usable": bool(item_info.get("usable", True)),
                    "unique": bool(item_info.get("unique", False)),
                    "count": int(count),
                    "cooldown_remaining": cooldown_remaining,
                    "on_cooldown": cooldown_remaining > 0,
                    "can_use": can,
                    "block_reason": reason,
                    "tags": list(item_info.get("tags") or []),
                    "passive_attr_bonus": dict(item_info.get("passive_attr_bonus") or {}),
                    "min_level": item_info.get("min_level"),
                }
            )
        return snapshot

    def can_use_item_with_reason(self, item_id: str) -> tuple[bool, str]:
        """检查物品是否可用，返回 (可否, 原因代码)。
        原因代码：not_found | not_usable | dead | on_cooldown | missing_buff:{id} | has_buff:{id} | tag_restricted:{tag_id}
        """
        item = self.item_registry.get(item_id)
        if not item:
            return False, "not_found"
        if self.is_dead:
            classes = item.get("classes", [])
            if not isinstance(classes, list) or "emergency" not in classes:
                return False, "dead"
        if not bool(item.get("usable", True)):
            return False, "not_usable"
        ready_at = self._item_cooldowns.get(item_id)
        if ready_at is not None and time.time() < ready_at:
            return False, "on_cooldown"

        # requires_buff / requires_no_buff 条件
        active_ids = {e.effect_id for e in self.profile.active_effects}
        rb = item.get("requires_buff")
        if rb is not None:
            check_ids = [rb] if isinstance(rb, str) else list(rb)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid not in active_ids:
                    return False, f"missing_buff:{bid}"
        rnb = item.get("requires_no_buff")
        if rnb is not None:
            check_ids = [rnb] if isinstance(rnb, str) else list(rnb)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid in active_ids:
                    return False, f"has_buff:{bid}"

        # 检查标签注册表的限制：若标签关联的 buff 处于活跃状态，且标签为 global_event，物品必须拥有该标签
        item_tags: set[str] = set(item.get("tags") or [])
        active_ids = active_ids if active_ids else {e.effect_id for e in self.profile.active_effects}
        for tag_id, tag_def in self.tag_registry.items():
            if not bool(tag_def.get("global_event", False)):
                continue
            linked_buff = str(tag_def.get("buff_id") or "").strip()
            if linked_buff and linked_buff in active_ids:
                if tag_id not in item_tags:
                    return False, f"tag_restricted:{tag_id}"

        # 最低使用等级
        min_level = item.get("min_level")
        if min_level is not None:
            try:
                if self.profile.level < int(min_level):
                    return False, "level_too_low"
            except Exception:
                pass

        return True, ""

    def can_use_item(self, item_id: str) -> bool:
        can, _ = self.can_use_item_with_reason(item_id)
        return can

    def get_item_fail_message(self, item_id: str, reason: str) -> str | None:
        """从物品 json 的 fail_messages 中查找对应原因的自定义文本，支持前缀通配匹配。
        对 tag_restricted:{tag_id} 原因额外回查标签注册表的 use_restricted_i18n_key。"""
        item = self.item_registry.get(item_id)
        if item:
            fail_messages = item.get("fail_messages")
            if isinstance(fail_messages, dict):
                if reason in fail_messages:
                    return str(fail_messages[reason])
                colon_idx = reason.find(":")
                if colon_idx >= 0:
                    prefix = reason[:colon_idx]
                    if f"{prefix}:*" in fail_messages:
                        return str(fail_messages[f"{prefix}:*"])
                    if prefix in fail_messages:
                        return str(fail_messages[prefix])
        # 标签限制：从标签注册表读取 use_restricted_i18n_key
        if reason.startswith("tag_restricted:"):
            tag_id = reason[len("tag_restricted:"):]
            tag_def = self.tag_registry.get(tag_id)
            if tag_def:
                i18n_key = str(tag_def.get("use_restricted_i18n_key") or "").strip()
                if i18n_key:
                    return tr(i18n_key)
        return None

    def get_item_cooldown_remaining(self, item_id: str) -> float:
        """返回物品剩余冷却秒数（0 表示已可使用）。"""
        ready_at = self._item_cooldowns.get(item_id)
        if ready_at is None:
            return 0.0
        remaining = ready_at - time.time()
        return max(0.0, remaining)

    def get_item_detail(self, item_id: str) -> dict[str, Any] | None:
        item = self.item_registry.get(item_id)
        if not item:
            return None
        payload = dict(item)
        payload.setdefault("id", item_id)
        payload.setdefault("name", item_id)
        payload.setdefault("usable", True)
        payload["name"] = self._resolve_record_name(payload, item_id)
        payload["desc"] = self._resolve_record_desc(payload)
        return payload

    def get_item_display_name(self, item_id: str) -> str:
        item = self.item_registry.get(item_id)
        if not item:
            return str(item_id)
        return self._resolve_record_name(item, str(item_id))

    def get_item_effect_summary(self, item_id: str) -> dict[str, Any] | None:
        item = self.item_registry.get(item_id)
        if not item:
            return None

        summary: dict[str, Any] = {
            "instant_states": [],
            "instant_attrs": [],
            "nutrition": [],
            "periodic_states": [],
            "caps": [],
        }

        for state_id in self.state_keys:
            if state_id in item:
                state_def = self.state_definitions.get(state_id, {})
                summary["instant_states"].append(
                    {
                        "id": state_id,
                        "name": str(state_def.get("name") or state_id),
                        "i18n_key": str(state_def.get("i18n_key") or f"life.state.{state_id}"),
                        "delta": float(item[state_id]),
                    }
                )

            periodic_key = f"{state_id}s"
            duration_key = f"{state_id}st"
            rule_key = f"{state_id}sr"
            if periodic_key in item:
                state_def = self.state_definitions.get(state_id, {})
                summary["periodic_states"].append(
                    {
                        "id": state_id,
                        "name": str(state_def.get("name") or state_id),
                        "i18n_key": str(state_def.get("i18n_key") or f"life.state.{state_id}"),
                        "delta": float(item.get(periodic_key, 0.0)),
                        "duration": int(item.get(duration_key, 0)),
                        "rule": str(item.get(rule_key, "add")),
                    }
                )

        for attr_id in self.attr_keys:
            if attr_id in item:
                attr_def = self.attr_definitions.get(attr_id, {})
                summary["instant_attrs"].append(
                    {
                        "id": attr_id,
                        "i18n_key": str(attr_def.get("i18n_key") or f"life.attr.{attr_id}"),
                        "delta": float(item[attr_id]),
                    }
                )

        nutrition_payload = item.get("nutrition")
        if isinstance(nutrition_payload, dict):
            for nutrition_id, delta in nutrition_payload.items():
                nutrition_key = str(nutrition_id)
                nutrition_def = self.nutrition_definitions.get(nutrition_key, {})
                summary["nutrition"].append(
                    {
                        "id": nutrition_key,
                        "name": str(nutrition_def.get("name") or nutrition_key),
                        "i18n_key": str(nutrition_def.get("i18n_key") or f"life.nutrition.{nutrition_key}"),
                        "delta": float(delta),
                    }
                )

        for key, value in item.items():
            if key.endswith("_max") or key.endswith("_min") or key.endswith("_max2"):
                summary["caps"].append({"key": str(key), "value": value})

        return summary

    def get_effect_detail(self, effect_id: str) -> dict[str, Any] | None:
        buff = self.buff_registry.get(effect_id)
        if not buff:
            return None
        return {
            "id": effect_id,
            "name": self._resolve_record_name(buff, effect_id),
            "desc": self._resolve_record_desc(buff),
            "icon_base64": buff.get("icon_base64"),
            "raw": dict(buff),
        }

    def apply_buff(self, buff_id: str, duration_override: int | None = None) -> bool:
        buff = self.buff_registry.get(buff_id)
        if not buff:
            _log.WARN(f"[Life]未知buff: {buff_id}")
            return False

        self._apply_record(buff, source="buff", duration_override=duration_override)
        # 图鉴：记录已解锁 buff（系统 buff 如 death 除外）
        if buff_id != "death":
            self.profile.unlocked_buffs.add(buff_id)
        # 触发绑定动作（有动作 ID 且 auto_trigger_action 不为 false）
        if buff.get("action_id") and buff.get("auto_trigger_action", True):
            self._trigger_record_action(buff)
        return True

    def list_buff_ids(self) -> list[str]:
        return sorted(self.buff_registry.keys())

    def list_active_effect_ids(self) -> list[str]:
        return [e.effect_id for e in self.profile.active_effects]

    def clear_effect(self, effect_id: str) -> bool:
        before = len(self.profile.active_effects)
        keep: list[LifeEffect] = []
        for effect in self.profile.active_effects:
            if effect.effect_id == effect_id:
                self._revert_effect_attr_modifiers(effect)
                # 停止绑定动作
                buff_record = self.buff_registry.get(effect.effect_id)
                if buff_record:
                    self._stop_record_action(buff_record)
                continue
            keep.append(effect)
        self.profile.active_effects = keep
        return len(self.profile.active_effects) < before

    def _clear_buffs_from_record(self, record: dict[str, Any]) -> None:
        clear_buffs = record.get("clear_buffs")
        if clear_buffs is None:
            return
        raw_ids = [clear_buffs] if isinstance(clear_buffs, str) else list(clear_buffs) if isinstance(clear_buffs, list) else []
        for buff_id in raw_ids:
            bid = str(buff_id).strip()
            if not bid:
                continue
            self.clear_effect(bid)

    def _apply_record(self, record: dict[str, Any], source: str, duration_override: int | None = None) -> None:
        record_id = str(record.get("id") or record.get("name") or "anonymous")
        record_name = self._resolve_record_name(record, record_id)
        record_desc = self._resolve_record_desc(record)

        # chance 字段：正值=触发概率(0-100%)；负值=移除同 ID 效果的概率
        chance = record.get("chance")
        if chance is not None:
            chance_val = float(chance)
            if chance_val >= 0:
                if random.random() * 100 >= chance_val:
                    return  # 未触发，跳过所有效果
            else:
                if random.random() * 100 < abs(chance_val):
                    self.clear_effect(record_id)
                return  # 负值始终跳过普通应用流程

        self._clear_buffs_from_record(record)

        # Instant attr effects (tracked in attr_modifiers for revert on buff end).
        apply_attrs: dict[str, float] = {}
        for attr in self.attr_keys:
            if attr in record:
                try:
                    delta = float(record[attr])
                    apply_attrs[attr] = delta
                    self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) + delta
                except Exception:
                    pass

        # Instant state effects (tracked in apply_states for revert on buff end).
        apply_states: dict[str, float] = {}
        for state in self.state_keys:
            if state in record:
                try:
                    delta = float(record[state])
                    apply_states[state] = delta
                    self._change_state(state, delta)
                except Exception:
                    pass

        self._apply_nutrition_record(record)

        # attr_exp：属性经验收益
        attr_exp_field = record.get("attr_exp")
        if isinstance(attr_exp_field, dict):
            levelups = self._apply_attr_exp_delta(attr_exp_field)
            if levelups:
                self._completed_trigger_results.extend(levelups)

        # buff_refs: 引用其他 buff 的 ID，使用时直接套用对应 buff 的完整效果
        buff_refs = record.get("buff_refs", [])
        if isinstance(buff_refs, list):
            for ref_id in buff_refs:
                ref_record = self.buff_registry.get(str(ref_id))
                if ref_record:
                    self._apply_record(ref_record, source=source, duration_override=duration_override)
                else:
                    _log.WARN(f"[Life]buff_refs 引用的 buff 不存在: {ref_id}")

        cap_modifiers = self._extract_cap_modifiers(record)

        # Periodic effects (e.g. hp + s -> hps).
        per_tick: dict[str, float] = {}
        duration_ticks = 0
        stack_rule = "add"

        for state in self.state_keys:
            value_key = f"{state}s"
            time_key = f"{state}st"
            rule_key = f"{state}sr"
            if value_key in record:
                per_tick[state] = float(record.get(value_key, 0))
                duration_ticks = max(duration_ticks, int(record.get(time_key, 0)))
                stack_rule = str(record.get(rule_key, stack_rule))

        nutrition_per_tick: dict[str, float] = {}
        for n_key in self.nutrition_keys:
            value_key = f"{n_key}s"
            if value_key in record:
                try:
                    nutrition_per_tick[n_key] = float(record[value_key])
                except Exception:
                    pass

        if duration_override is not None:
            if per_tick or apply_states or apply_attrs or cap_modifiers or nutrition_per_tick:
                duration_ticks = max(1, int(duration_override))
            elif duration_ticks > 0:
                duration_ticks = max(1, int(duration_override))

        has_periodic_or_instant = bool(per_tick or apply_states or apply_attrs or cap_modifiers or nutrition_per_tick)
        if has_periodic_or_instant and duration_ticks > 0:
            self._register_effect(
                LifeEffect(
                    effect_id=record_id,
                    effect_name=record_name,
                    effect_desc=record_desc,
                    source=source,
                    per_tick=per_tick,
                    remaining_ticks=duration_ticks,
                    stack_rule=stack_rule,
                    cap_modifiers=cap_modifiers,
                    nutrition_per_tick=nutrition_per_tick,
                    apply_states=apply_states,
                    attr_modifiers=apply_attrs,
                )
            )
        elif cap_modifiers or apply_attrs or apply_states:
            self._apply_cap_modifiers(cap_modifiers)
        elif not has_periodic_or_instant and (
            record.get("action_id") or record.get("display_in_status_bar")
        ):
            # 纯标记型 buff（如 death）：无定时/即时效果，但有动作或状态栏显示需求
            if duration_override is not None:
                eff_duration = max(1, int(duration_override))
            elif duration_ticks > 0:
                eff_duration = duration_ticks
            else:
                eff_duration = 0
            self._register_effect(
                LifeEffect(
                    effect_id=record_id,
                    effect_name=record_name,
                    effect_desc=record_desc,
                    source=source,
                    per_tick={},
                    remaining_ticks=eff_duration,
                    stack_rule="noadd" if eff_duration <= 0 else stack_rule,
                    managed=eff_duration <= 0,
                    apply_states={},
                    attr_modifiers={},
                )
            )
        elif any(str(t.get("buff_id") or "") == record_id for t in self.tag_registry.values()):
            # 标签监控的 buff：无定时效果，以 managed 模式注册为标记效果
            self._register_effect(
                LifeEffect(
                    effect_id=record_id,
                    effect_name=record_name,
                    effect_desc=record_desc,
                    source=source,
                    per_tick={},
                    remaining_ticks=1,
                    stack_rule="noadd",
                    managed=True,
                    apply_states=apply_states,
                )
            )

        # exp 字段：使用物品/事件结果时获得全局经验
        exp_gain = record.get("exp")
        if exp_gain is not None:
            try:
                gain = float(exp_gain)
                if gain != 0.0:
                    self.profile.exp = max(0.0, self.profile.exp + gain)
                    self._process_char_levelup()
            except Exception:
                pass

        # permanent_attr_delta 字段：永久属性修正
        perm_delta = record.get("permanent_attr_delta")
        if isinstance(perm_delta, dict):
            for attr_key, delta_val in perm_delta.items():
                try:
                    delta = float(delta_val)
                    self.profile.permanent_attr_delta[str(attr_key)] = (
                        self.profile.permanent_attr_delta.get(str(attr_key), 0.0) + delta
                    )
                    # 同时将永久修正写入 attrs（使其对实际数值生效）
                    self.profile.attrs[str(attr_key)] = (
                        self.profile.attrs.get(str(attr_key), 0.0) + delta
                    )
                except Exception:
                    pass

        self._refresh_attr_range_effects()

        _log.DEBUG(f"[Life]应用{source}: {record_id}")

    def _extract_cap_modifiers(self, record: dict[str, Any]) -> list[tuple[str, str, Any]]:
        modifiers: list[tuple[str, str, Any]] = []
        for key, value in record.items():
            if key.endswith("_max2"):
                base = key[:-5]
                if base in self.state_keys or base in self.nutrition_keys:
                    modifiers.append(("max2", base, value))
            elif key.endswith("_max"):
                base = key[:-4]
                if base in self.state_keys or base in self.nutrition_keys:
                    modifiers.append(("max", base, value))
            elif key.endswith("_min"):
                base = key[:-4]
                if base in self.state_keys or base in self.nutrition_keys:
                    modifiers.append(("min", base, value))
        return modifiers

    def _apply_cap_modifiers(self, modifiers: list[tuple[str, str, Any]]) -> None:
        self._static_cap_modifiers.extend(modifiers)

    def _apply_cap_modifiers_to_caps(
        self,
        modifiers: list[tuple[str, str, Any]],
        max_caps: dict[str, float],
        min_caps: dict[str, float],
    ) -> None:
        for mode, state, raw_value in modifiers:
            if state not in max_caps or state not in min_caps:
                continue
            if mode == "max":
                delta = self._to_delta(raw_value, max_caps[state])
                max_caps[state] += delta
            elif mode == "min":
                delta = self._to_delta(raw_value, min_caps[state])
                min_caps[state] += delta
            elif mode == "max2":
                max_caps[state] *= self._to_multiplier(raw_value)

    def _register_effect(self, effect: LifeEffect) -> None:
        existing = next((e for e in self.profile.active_effects if e.effect_id == effect.effect_id), None)
        if not existing:
            self.profile.active_effects.append(effect)
            return

        rule = effect.stack_rule.lower()
        if rule == "noadd":
            return
        if rule == "refresh":
            existing.per_tick = dict(effect.per_tick)
            existing.nutrition_per_tick = dict(effect.nutrition_per_tick)
            existing.remaining_ticks = effect.remaining_ticks
            existing.effect_name = effect.effect_name
            existing.effect_desc = effect.effect_desc
            existing.cap_modifiers = list(effect.cap_modifiers)
            return

        # add/default
        for k, v in effect.per_tick.items():
            existing.per_tick[k] = existing.per_tick.get(k, 0.0) + v
        for k, v in effect.nutrition_per_tick.items():
            existing.nutrition_per_tick[k] = existing.nutrition_per_tick.get(k, 0.0) + v
        existing.remaining_ticks += effect.remaining_ticks
        existing.cap_modifiers.extend(effect.cap_modifiers)

    def tick(self) -> None:
        if self.paused:
            return
        next_effects: list[LifeEffect] = []
        for effect in self.profile.active_effects:
            for state, delta in effect.per_tick.items():
                self._change_state(state, delta)
            for nutrition_key, val in effect.nutrition_per_tick.items():
                self._change_nutrition(nutrition_key, val)

            if effect.managed:
                # 由外部管理的 buff（如营养区间 buff），不倒计时、不自动移除
                next_effects.append(effect)
            else:
                effect.remaining_ticks -= 1
                if effect.remaining_ticks > 0:
                    next_effects.append(effect)
                else:
                    self._revert_effect_attr_modifiers(effect)
                    # buff 自然到期：停止绑定的动作
                    buff_record = self.buff_registry.get(effect.effect_id)
                    if buff_record:
                        self._stop_record_action(buff_record)

        self.profile.active_effects = next_effects
        self._tick_nutrition()
        self.tick_triggers()
        self._sync_managed_nutrition_buffs()
        self._sync_managed_state_buffs()
        self._tick_passive_buffs()
        self._refresh_attr_range_effects()
        self._tick_exp()

        # 死亡检测：hp ≤ 0 且当前不处于死亡状态
        if not self.is_dead and "hp" in self.profile.states:
            if self.profile.states["hp"] <= 0:
                self._trigger_death()

    def _tick_passive_buffs(self) -> None:
        """每 tick 检测被动 buff 触发条件，按概率随机激活。"""
        if not self.passive_buff_registry:
            return
        active_ids = {e.effect_id for e in self.profile.active_effects}
        for pb_id, record in self.passive_buff_registry.items():
            # requires_buff 条件（列表中任意一个存在即满足）
            rb = record.get("requires_buff")
            if rb is not None:
                check_ids = [rb] if isinstance(rb, str) else list(rb)
                if not any(str(bid) in active_ids for bid in check_ids if bid):
                    continue
            # requires_no_buff 条件（列表中任意一个存在则跳过）
            rnb = record.get("requires_no_buff")
            if rnb is not None:
                check_ids = [rnb] if isinstance(rnb, str) else list(rnb)
                if any(str(bid) in active_ids for bid in check_ids if bid):
                    continue
            # attr_conditions 条件（全部满足才继续）
            attr_conds = record.get("attr_conditions")
            if isinstance(attr_conds, list):
                cond_ok = True
                for cond in attr_conds:
                    if not isinstance(cond, dict):
                        continue
                    attr_key = str(cond.get("attr") or "").strip()
                    if not attr_key:
                        continue
                    attr_val = self.profile.attrs.get(attr_key, 0.0)
                    cond_min = cond.get("min")
                    cond_max = cond.get("max")
                    if cond_min is not None and attr_val < float(cond_min):
                        cond_ok = False
                        break
                    if cond_max is not None and attr_val > float(cond_max):
                        cond_ok = False
                        break
                if not cond_ok:
                    continue
            # 计算有效概率 = 基础概率 + 属性加成
            base_chance = float(record.get("base_chance", 0.0))
            attr_bonus_map = record.get("attr_bonus")
            bonus = 0.0
            if isinstance(attr_bonus_map, dict):
                for attr_key, bonus_per_point in attr_bonus_map.items():
                    attr_val = self.profile.attrs.get(str(attr_key), 0.0)
                    try:
                        bonus += float(attr_val) * float(bonus_per_point)
                    except Exception:
                        pass
            effective_chance = max(0.0, base_chance + bonus)
            if effective_chance <= 0.0:
                continue
            # 随机触发
            if random.random() * 100.0 < effective_chance:
                on_trigger = record.get("on_trigger")
                if isinstance(on_trigger, dict):
                    buff_id = str(on_trigger.get("buff_id") or "").strip()
                    if buff_id:
                        duration_override = self._resolve_duration_formula(on_trigger)
                        self.apply_buff(buff_id, duration_override=duration_override)
                    else:
                        # on_trigger 支持事件式 guaranteed/random_pools；
                        # 若未提供这些字段，则按 buff-like 记录直接应用。
                        result_log: list[dict[str, Any]] = []
                        self._execute_event_guaranteed(on_trigger, result_log)
                        self._execute_event_random_pools(on_trigger, result_log)
                        if not result_log:
                            self._apply_record(on_trigger, source="passive_buff")
                        self._append_recent_result_logs(
                            trigger_id=str(pb_id),
                            trigger_name=str(record.get("name") or pb_id),
                            source="passive",
                            result_log=result_log,
                            add_none_when_empty=False,
                        )
                _log.DEBUG(f"[Life][passive_buff]触发: {pb_id}")

    def _resolve_duration_formula(self, on_trigger: dict[str, Any]) -> int | None:
        formula = on_trigger.get("duration_formula")
        if not isinstance(formula, dict):
            return None
        base = self._to_float_safe(formula.get("base"), 0.0)
        total = base
        terms = formula.get("terms")
        if isinstance(terms, list):
            for term in terms:
                if not isinstance(term, dict):
                    continue
                attr_key = str(term.get("attr") or "").strip()
                if not attr_key:
                    continue
                coeff = self._to_float_safe(term.get("coeff"), 0.0)
                total += self._effective_attr(attr_key) * coeff
        lower = formula.get("min")
        upper = formula.get("max")
        if lower is not None:
            total = max(float(lower), total)
        if upper is not None:
            total = min(float(upper), total)
        if total <= 0:
            return None
        return max(1, int(round(total)))

    def _tick_exp(self) -> None:
        """每 tick 增加被动经验并处理升级。满级后经验继续积累但不再触发升级。"""
        if self.is_dead:
            return
        passive = self._passive_exp_per_tick + self._inventory_passive_exp_bonus
        if passive > 0:
            self.profile.exp = min(_EXP_MAX, max(0.0, self.profile.exp + passive))
            if self.profile.level < self._max_level:
                self._process_char_levelup()

    def _process_char_levelup(self) -> None:
        """检查全局等级经验是否达到升级阈值，连续升级直到不足为止。
        满级时经验继续积累，不截断，不变负。
        """
        while self.profile.level < self._max_level:
            required = self._exp_table.get(self.profile.level)
            if required is None or self.profile.exp < required:
                break
            self.profile.exp = max(0.0, self.profile.exp - required)
            self.profile.level += 1
            self._apply_char_level_attr_bonus(self.profile.level)
            _log.DEBUG(f"[Life][Level]升级: Lv.{self.profile.level} 剩余经验={self.profile.exp:.2f}")
        # 保证经验值永远非负且不超上限
        self.profile.exp = min(_EXP_MAX, max(0.0, self.profile.exp))

    def _apply_char_level_attr_bonus(self, new_level: int) -> None:
        """根据 attrs.json 中的 char_level_bonuses 计算并应用升级到 new_level 时的属性加成。"""
        for attr_id, defn in self.attr_definitions.items():
            char_level_bonuses = defn.get("char_level_bonuses")
            if not isinstance(char_level_bonuses, list):
                continue
            for bonus_entry in char_level_bonuses:
                if not isinstance(bonus_entry, dict):
                    continue
                b_type = str(bonus_entry.get("type") or "").strip()
                b_bonus: dict[str, float] = bonus_entry.get("bonus") or {}
                if not isinstance(b_bonus, dict):
                    continue

                apply = False
                if b_type == "at_level":
                    apply = (new_level == int(bonus_entry.get("level", -1)))
                elif b_type == "per_levels":
                    every = int(bonus_entry.get("every", 0))
                    if every <= 0:
                        continue
                    offset = int(bonus_entry.get("min_level_offset", 0))
                    # 实际首次触发等级 = offset + every + 1
                    first_trigger = offset + every + 1
                    if new_level >= first_trigger:
                        apply = ((new_level - offset - 1) % every == 0)

                if apply:
                    for bonus_attr, bonus_val in b_bonus.items():
                        try:
                            delta = float(bonus_val)
                        except Exception:
                            continue
                        if bonus_attr in self.profile.attrs:
                            self.profile.attrs[bonus_attr] += delta
                            _log.DEBUG(f"[Life][Level]等级修正 Lv.{new_level}: {bonus_attr}+{delta}")

    def _refresh_attr_range_effects(self) -> None:
        max_caps = {
            state: float(self.state_definitions.get(state, {}).get("max", GLOBAL_VALUE_MAX)) for state in self.state_keys
        }
        min_caps = {state: float(self.state_definitions.get(state, {}).get("min", 0.0)) for state in self.state_keys}
        for n_key in self.nutrition_keys:
            defn = self.nutrition_definitions.get(n_key, {})
            max_caps[n_key] = float(defn.get("max", 100.0))
            min_caps[n_key] = float(defn.get("min", 0.0))

        breakdown: dict[str, dict[str, float]] = {
            state: {
                "max_flat_delta": 0.0,
                "min_flat_delta": 0.0,
                "max_fixed_delta": 0.0,
                "min_fixed_delta": 0.0,
                "max_percent_value_delta": 0.0,
                "min_percent_value_delta": 0.0,
                "max_percent_add": 0.0,
                "max_percent_sub": 0.0,
                "min_percent_add": 0.0,
                "min_percent_sub": 0.0,
                "tick_delta": 0.0,
            }
            for state in self.state_keys
        }
        for n_key in self.nutrition_keys:
            breakdown[n_key] = {
                "max_flat_delta": 0.0,
                "min_flat_delta": 0.0,
                "max_fixed_delta": 0.0,
                "min_fixed_delta": 0.0,
                "max_percent_value_delta": 0.0,
                "min_percent_value_delta": 0.0,
                "max_percent_add": 0.0,
                "max_percent_sub": 0.0,
                "min_percent_add": 0.0,
                "min_percent_sub": 0.0,
                "tick_delta": 0.0,
            }

        def _record_percent(state: str, mode: str, raw_value: Any) -> None:
            percent = self._parse_percent_value(raw_value)
            if percent is None:
                return
            if mode == "max":
                if percent >= 0:
                    breakdown[state]["max_percent_add"] += percent
                else:
                    breakdown[state]["max_percent_sub"] += percent
            elif mode == "min":
                if percent >= 0:
                    breakdown[state]["min_percent_add"] += percent
                else:
                    breakdown[state]["min_percent_sub"] += percent

        def _apply_one_modifier(mode: str, state: str, raw_value: Any) -> None:
            if state not in max_caps or state not in min_caps:
                return

            if mode == "max":
                before = max_caps[state]
                delta = self._to_delta(raw_value, before)
                max_caps[state] = before + delta
                if state in breakdown:
                    breakdown[state]["max_flat_delta"] += delta
                    percent = self._parse_percent_value(raw_value)
                    if percent is None:
                        breakdown[state]["max_fixed_delta"] += delta
                    else:
                        breakdown[state]["max_percent_value_delta"] += delta
                    _record_percent(state, mode, raw_value)
                return

            if mode == "min":
                before = min_caps[state]
                delta = self._to_delta(raw_value, before)
                min_caps[state] = before + delta
                if state in breakdown:
                    breakdown[state]["min_flat_delta"] += delta
                    percent = self._parse_percent_value(raw_value)
                    if percent is None:
                        breakdown[state]["min_fixed_delta"] += delta
                    else:
                        breakdown[state]["min_percent_value_delta"] += delta
                    _record_percent(state, mode, raw_value)
                return

            if mode == "max2":
                before = max_caps[state]
                max_caps[state] = before * self._to_multiplier(raw_value)
                if state in breakdown:
                    delta = max_caps[state] - before
                    breakdown[state]["max_flat_delta"] += delta
                    breakdown[state]["max_percent_value_delta"] += delta

                    percent = self._parse_percent_value(raw_value)
                    if percent is None:
                        try:
                            percent = (self._to_multiplier(raw_value) - 1.0) * 100.0
                        except Exception:
                            percent = None
                    if percent is not None:
                        if percent >= 0:
                            breakdown[state]["max_percent_add"] += percent
                        else:
                            breakdown[state]["max_percent_sub"] += percent
                return

        for mode, state, raw_value in self._static_cap_modifiers:
            _apply_one_modifier(mode, state, raw_value)
        for effect in self.profile.active_effects:
            for mode, state, raw_value in effect.cap_modifiers:
                _apply_one_modifier(mode, state, raw_value)

        self._attr_cap_bonus_max = {k: 0.0 for k in self.state_keys}
        self._attr_cap_bonus_min = {k: 0.0 for k in self.state_keys}

        for attr_name, rules in self.attribute_rules.items():
            current = float(self.profile.attrs.get(attr_name, 0.0))
            for rule in rules:
                min_v = float(rule.get("min", float("-inf")))
                max_v = float(rule.get("max", float("inf")))
                if not (min_v <= current < max_v):
                    continue

                effects = rule.get("effects", {})
                if not isinstance(effects, dict):
                    continue

                for key, value in effects.items():
                    if key.endswith("_max"):
                        base = key[:-4]
                        if base in max_caps:
                            before = max_caps[base]
                            delta = self._to_delta(value, before)
                            max_caps[base] = before + delta
                            self._attr_cap_bonus_max[base] += delta
                            breakdown[base]["max_flat_delta"] += delta
                            if self._parse_percent_value(value) is None:
                                breakdown[base]["max_fixed_delta"] += delta
                            else:
                                breakdown[base]["max_percent_value_delta"] += delta
                            _record_percent(base, "max", value)
                    elif key.endswith("_min"):
                        base = key[:-4]
                        if base in min_caps:
                            before = min_caps[base]
                            delta = self._to_delta(value, before)
                            min_caps[base] = before + delta
                            self._attr_cap_bonus_min[base] += delta
                            breakdown[base]["min_flat_delta"] += delta
                            if self._parse_percent_value(value) is None:
                                breakdown[base]["min_fixed_delta"] += delta
                            else:
                                breakdown[base]["min_percent_value_delta"] += delta
                            _record_percent(base, "min", value)

        for state in self.state_keys:
            if min_caps[state] > max_caps[state]:
                min_caps[state] = max_caps[state]
            self.profile.state_min[state] = min_caps[state]
            self.profile.state_max[state] = max_caps[state]
            self._clamp_state(state)

        for n_key in self.nutrition_keys:
            if min_caps[n_key] > max_caps[n_key]:
                min_caps[n_key] = max_caps[n_key]
            self.profile.nutrition_min[n_key] = min_caps[n_key]
            self.profile.nutrition_max[n_key] = max_caps[n_key]
            self._clamp_nutrition(n_key)

        tick_deltas = self._collect_state_tick_deltas()
        for state, delta in tick_deltas.items():
            if state in breakdown:
                breakdown[state]["tick_delta"] = float(delta)

        # 收集营养值的每 tick 变化量（衰减 + 效果修正）
        for n_key in self.nutrition_keys:
            defn = self.nutrition_definitions.get(n_key, {})
            decay = float(defn.get("decay", 0.0))
            effect_delta = 0.0
            for effect in self.profile.active_effects:
                effect_delta += effect.nutrition_per_tick.get(n_key, 0.0)
            breakdown[n_key]["tick_delta"] = -decay + effect_delta

        self._state_runtime_breakdown = breakdown

    def _trigger_death(self) -> None:
        """处理桌宠死亡：应用死亡 buff、暂停 tick、记录死亡摘要。"""
        if self.is_dead:
            return

        _log.DEBUG("[Life]_trigger_death 开始执行")

        # 停止濒死动作
        dying_record = self.buff_registry.get("dying")
        if dying_record:
            self._stop_record_action(dying_record)

        # 应用死亡 buff（触发死亡动作）
        death_record = self.buff_registry.get("death")
        _log.DEBUG(f"[Life]死亡记录: {death_record.get('id') if death_record else None}, action_id={death_record.get('action_id') if death_record else None}")
        if death_record:
            # 确保 death 不出现在图鉴中
            self.profile.unlocked_buffs.discard("death")
            self._trigger_record_action(death_record)
            # 移除所有已有的 death 效果（无论来源），统一替换为 managed 效果
            self.profile.active_effects = [
                e for e in self.profile.active_effects
                if e.effect_id != "death"
            ]
            self.profile.active_effects.append(LifeEffect(
                    effect_id="death",
                    effect_name=str(death_record.get("name", "死亡")),
                    effect_desc=str(death_record.get("desc", "")),
                    source="death",
                    per_tick={},
                    remaining_ticks=0,
                    managed=True,
                ))

        self.is_dead = True
        self.paused = True
        self._death_summary = {
            "died_at": time.time(),
            "life_started_at": self._life_started_at,
            "play_time_s": round(time.time() - self._life_started_at),
            "final_states": dict(self.profile.states),
            "final_attrs": dict(self.profile.attrs),
        }
        _log.INFO("[Life]桌宠已死亡")

    def get_death_summary(self) -> dict[str, Any]:
        """返回死亡摘要信息；桌宠存活时返回空字典。"""
        if self._death_summary is None:
            return {}
        return dict(self._death_summary)

    def revive(self) -> bool:
        """尝试复活桌宠（仅当 hp > 0 时成功）。成功返回 True，否则返回 False。"""
        hp = float(self.profile.states.get("hp", 0.0))
        if hp <= 0:
            _log.WARN("[Life]无法复活：HP 仍为 0")
            return False
        # 停止死亡动作
        death_record = self.buff_registry.get("death")
        if death_record:
            self._stop_record_action(death_record)
        # 移除所有死亡效果（无论来源）
        self.profile.active_effects = [
            e for e in self.profile.active_effects
            if e.effect_id != "death"
        ]
        self.is_dead = False
        self.paused = False
        self._death_summary = None
        _log.INFO("[Life]桌宠已复活")
        return True


    def _parse_percent_value(self, value: Any) -> float | None:
        if isinstance(value, str):
            text = value.strip()
            if text.endswith("%"):
                try:
                    return float(text[:-1])
                except Exception:
                    return None
        return None

    def _collect_state_tick_deltas(self) -> dict[str, float]:
        totals: dict[str, float] = {state: 0.0 for state in self.state_keys}

        for effect in self.profile.active_effects:
            for state, delta in effect.per_tick.items():
                if state in totals:
                    totals[state] += float(delta)

        for nutrition_key, definition in self.nutrition_definitions.items():
            current = float(self.profile.nutrition.get(nutrition_key, definition.get("default", 0.0)))
            for effect_def in definition.get("effects", []):
                if not isinstance(effect_def, dict):
                    continue
                if effect_def.get("buff_id"):
                    continue

                min_v = float(effect_def.get("min", float("-inf")))
                max_v = float(effect_def.get("max", float("inf")))
                if not (min_v <= current < max_v):
                    continue

                for state, delta in dict(effect_def.get("states", {})).items():
                    if state in totals:
                        totals[state] += float(delta)

        return totals

    def get_state_runtime_snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tick_deltas = self._collect_state_tick_deltas()

        for state in self.state_keys:
            definition = self.state_definitions.get(state, {})
            base_min = float(definition.get("min", 0.0))
            base_max = float(definition.get("max", GLOBAL_VALUE_MAX))

            current_value = float(self.profile.states.get(state, definition.get("default", 0.0)))
            current_min = float(self.profile.state_min.get(state, base_min))
            current_max = float(self.profile.state_max.get(state, base_max))

            detail = self._state_runtime_breakdown.get(state, {})
            max_flat_delta = float(detail.get("max_flat_delta", current_max - base_max))
            min_flat_delta = float(detail.get("min_flat_delta", current_min - base_min))
            max_fixed_delta = float(detail.get("max_fixed_delta", max_flat_delta))
            min_fixed_delta = float(detail.get("min_fixed_delta", min_flat_delta))
            max_percent_value_delta = float(detail.get("max_percent_value_delta", max_flat_delta - max_fixed_delta))
            min_percent_value_delta = float(detail.get("min_percent_value_delta", min_flat_delta - min_fixed_delta))
            max_percent_add = float(detail.get("max_percent_add", 0.0))
            max_percent_sub = float(detail.get("max_percent_sub", 0.0))
            min_percent_add = float(detail.get("min_percent_add", 0.0))
            min_percent_sub = float(detail.get("min_percent_sub", 0.0))
            tick_delta = float(detail.get("tick_delta", tick_deltas.get(state, 0.0)))

            rows.append(
                {
                    "id": state,
                    "name": tr(str(definition.get("i18n_key") or f"life.state.{state}"), default=str(definition.get("name") or state)),
                    "value": current_value,
                    "base_min": base_min,
                    "base_max": base_max,
                    "min": current_min,
                    "max": current_max,
                    "overflow": max(0.0, current_max - base_max),
                    "max_flat_delta": max_flat_delta,
                    "min_flat_delta": min_flat_delta,
                    "max_fixed_delta": max_fixed_delta,
                    "min_fixed_delta": min_fixed_delta,
                    "max_percent_value_delta": max_percent_value_delta,
                    "min_percent_value_delta": min_percent_value_delta,
                    "max_percent_add": max_percent_add,
                    "max_percent_sub": max_percent_sub,
                    "min_percent_add": min_percent_add,
                    "min_percent_sub": min_percent_sub,
                    "max_percent_net": max_percent_add + max_percent_sub,
                    "min_percent_net": min_percent_add + min_percent_sub,
                    "tick_delta": tick_delta,
                }
            )

        return rows

    def _change_state(self, state: str, delta: float) -> None:
        if state not in self.profile.states:
            return
        self.profile.states[state] += delta
        self._clamp_state(state)

    def _apply_nutrition_record(self, record: dict[str, Any]) -> None:
        nutrition_payload = record.get("nutrition")
        if not isinstance(nutrition_payload, dict):
            return
        for nutrition_key, delta in nutrition_payload.items():
            try:
                self._change_nutrition(str(nutrition_key), float(delta))
            except Exception:
                continue

    def _tick_nutrition(self) -> None:
        if not self.nutrition_definitions:
            return

        for nutrition_key, definition in self.nutrition_definitions.items():
            decay = float(definition.get("decay", 0.0))
            if decay > 0:
                self._change_nutrition(nutrition_key, -decay)

    def _sync_managed_nutrition_buffs(self) -> None:
        """根据当前营养值同步 managed buff 的激活/移除状态。
        在 tick 时和 reload_registries 后均需调用，确保初始状态正确。
        """
        if not self.nutrition_definitions:
            return

        for nutrition_key, definition in self.nutrition_definitions.items():
            current = float(self.profile.nutrition.get(nutrition_key, definition.get("default", 0.0)))
            base_max = float(definition.get("max", 100.0))
            source_tag = f"nutrition:{nutrition_key}"

            for effect_def in definition.get("effects", []):
                in_range = self._threshold_effect_in_range(effect_def, current, base_max)
                # 额外的 buff 条件检查
                if in_range:
                    in_range = self._effect_conditions_met(effect_def)
                buff_id = effect_def.get("buff_id")

                if buff_id:
                    # 新方式：通过 buff_id 管理持续 buff 的生命周期
                    existing = next(
                        (e for e in self.profile.active_effects
                         if e.effect_id == buff_id and e.source == source_tag),
                        None,
                    )
                    if in_range and existing is None:
                        buff_record = self.buff_registry.get(str(buff_id))
                        if buff_record:
                            if buff_record.get("consume_self"):
                                # 自消耗 buff：仅执行即时效果，不注册为持续 managed buff
                                self._apply_record(buff_record, source=source_tag)
                            else:
                                self._apply_managed_buff(buff_record, source=source_tag)
                    elif not in_range and existing is not None:
                        self._revert_effect_attr_modifiers(existing)
                        br = self.buff_registry.get(str(buff_id))
                        if br:
                            self._stop_record_action(br)
                        self.profile.active_effects.remove(existing)
                else:
                    # 旧方式（向下兼容）：直接每 tick 改变状态值
                    if not in_range:
                        continue
                    for state, delta in dict(effect_def.get("states", {})).items():
                        self._change_state(str(state), float(delta))
                    for attr, delta in dict(effect_def.get("attrs", {})).items():
                        if attr not in self.profile.attrs:
                            continue
                        self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) + float(delta)

    def _threshold_effect_in_range(self, effect_def: dict[str, Any], current: float, base_max: float) -> bool:
        percent_min = float(effect_def.get("percent_min", float("-inf")))
        percent_max = float(effect_def.get("percent_max", float("inf")))
        if percent_min != float("-inf") or percent_max != float("inf"):
            safe_base = base_max if base_max > 0 else 1.0
            percent_value = (current / safe_base) * 100.0
            return percent_min <= percent_value < percent_max

        min_v = float(effect_def.get("min", float("-inf")))
        max_v = float(effect_def.get("max", float("inf")))
        return min_v <= current < max_v

    def _effect_conditions_met(self, effect_def: dict[str, Any]) -> bool:
        """检查 effect_def 的 requires_buff / requires_no_buff 条件是否满足。"""
        active_ids = {e.effect_id for e in self.profile.active_effects}

        requires_buff = effect_def.get("requires_buff")
        if requires_buff is not None:
            check_ids = [requires_buff] if isinstance(requires_buff, str) else list(requires_buff)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid not in active_ids:
                    return False

        requires_no_buff = effect_def.get("requires_no_buff")
        if requires_no_buff is not None:
            check_ids = [requires_no_buff] if isinstance(requires_no_buff, str) else list(requires_no_buff)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid in active_ids:
                    return False

        return True

    def _sync_managed_state_buffs(self) -> None:
        if not self.state_definitions:
            return

        for state_key, definition in self.state_definitions.items():
            current = float(self.profile.states.get(state_key, definition.get("default", 0.0)))
            base_max = float(definition.get("max", GLOBAL_VALUE_MAX))
            source_tag = f"state:{state_key}"

            for effect_def in definition.get("effects", []):
                if not isinstance(effect_def, dict):
                    continue

                in_range = self._threshold_effect_in_range(effect_def, current, base_max)
                # 额外的 buff 条件检查
                if in_range:
                    in_range = self._effect_conditions_met(effect_def)
                buff_id = effect_def.get("buff_id")

                if buff_id:
                    existing = next(
                        (
                            e
                            for e in self.profile.active_effects
                            if e.effect_id == buff_id and e.source == source_tag
                        ),
                        None,
                    )
                    if in_range and existing is None:
                        buff_record = self.buff_registry.get(str(buff_id))
                        if buff_record:
                            if buff_record.get("consume_self"):
                                # 自消耗 buff：仅执行即时效果，不注册为持续 managed buff
                                self._apply_record(buff_record, source=source_tag)
                            else:
                                self._apply_managed_buff(buff_record, source=source_tag)
                    elif not in_range and existing is not None:
                        self._revert_effect_attr_modifiers(existing)
                        br = self.buff_registry.get(str(buff_id))
                        if br:
                            self._stop_record_action(br)
                        self.profile.active_effects.remove(existing)
                else:
                    if not in_range:
                        continue
                    for state, delta in dict(effect_def.get("states", {})).items():
                        self._change_state(str(state), float(delta))
                    for attr, delta in dict(effect_def.get("attrs", {})).items():
                        if attr not in self.profile.attrs:
                            continue
                        self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) + float(delta)

    def _apply_managed_buff(self, record: dict[str, Any], source: str) -> None:
        """激活一个由外部条件（如营养区间）管理的持续 buff。
        该 buff 不会自动倒计时，必须由外部显式移除。
        """
        record_id = str(record.get("id") or record.get("name") or "anonymous")
        record_name = str(record.get("name") or record_id)
        record_desc = str(record.get("desc") or record.get("description") or "").strip()

        per_tick: dict[str, float] = {}
        for state in self.state_keys:
            value_key = f"{state}s"
            if value_key in record:
                per_tick[state] = float(record[value_key])

        cap_modifiers = self._extract_cap_modifiers(record)
        attr_modifiers: dict[str, float] = {}
        for attr in self.attr_keys:
            if attr in record:
                attr_modifiers[attr] = float(record[attr])

        for attr, delta in attr_modifiers.items():
            self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) + delta

        # 一次性状态修正（直接匹配状态键名，非 {state}s 格式）
        apply_states: dict[str, float] = {}
        for state_key in self.state_keys:
            if state_key in record:
                try:
                    apply_states[state_key] = float(record[state_key])
                except Exception:
                    pass
        for state, delta in apply_states.items():
            self.profile.states[state] = self.profile.states.get(state, 0.0) + delta

        nutrition_per_tick: dict[str, float] = {}
        for n_key in self.nutrition_keys:
            value_key = f"{n_key}s"
            if value_key in record:
                try:
                    nutrition_per_tick[n_key] = float(record[value_key])
                except Exception:
                    pass

        effect = LifeEffect(
            effect_id=record_id,
            effect_name=record_name,
            effect_desc=record_desc,
            source=source,
            per_tick=per_tick,
            remaining_ticks=0,
            stack_rule="refresh",
            cap_modifiers=cap_modifiers,
            attr_modifiers=attr_modifiers,
            managed=True,
            nutrition_per_tick=nutrition_per_tick,
            apply_states=apply_states,
        )
        self.profile.active_effects.append(effect)
        state_info = f" states={effect.apply_states}" if effect.apply_states else ""
        attr_info = f" attrs={effect.attr_modifiers}" if effect.attr_modifiers else ""
        _log.DEBUG(f"[Life]激活持续Buff: {record_id} (来源: {source}){attr_info}{state_info}")

        # 触发绑定动作
        self._trigger_record_action(record)

    def _revert_effect_attr_modifiers(self, effect: LifeEffect) -> None:
        if effect.attr_modifiers:
            for attr, delta in effect.attr_modifiers.items():
                if attr not in self.profile.attrs:
                    continue
                self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) - float(delta)
        if effect.apply_states:
            for state, delta in effect.apply_states.items():
                if state not in self.profile.states:
                    continue
                self.profile.states[state] = self.profile.states.get(state, 0.0) - float(delta)

    def _change_nutrition(self, nutrition_key: str, delta: float) -> None:
        if nutrition_key not in self.profile.nutrition:
            return
        self.profile.nutrition[nutrition_key] += delta
        self._clamp_nutrition(nutrition_key)

    def _clamp_nutrition(self, nutrition_key: str) -> None:
        if nutrition_key not in self.profile.nutrition:
            return
        lo = self.profile.nutrition_min.get(nutrition_key, 0.0)
        hi = self.profile.nutrition_max.get(nutrition_key, 100.0)
        self.profile.nutrition[nutrition_key] = max(lo, min(hi, self.profile.nutrition[nutrition_key]))

    def get_nutrition_snapshot(self) -> list[dict[str, Any]]:
        # 汇总所有活跃效果对营养的每 tick 增量
        effect_nutrition_deltas: dict[str, float] = {}
        for effect in self.profile.active_effects:
            for n_key, val in effect.nutrition_per_tick.items():
                effect_nutrition_deltas[n_key] = effect_nutrition_deltas.get(n_key, 0.0) + val

        snapshot: list[dict[str, Any]] = []
        for nutrition_key, definition in self.nutrition_definitions.items():
            nutrition_name = tr(
                str(definition.get("i18n_key") or f"life.nutrition.{nutrition_key}"),
                default=str(definition.get("name") or nutrition_key),
            )
            decay = float(definition.get("decay", 0.0))
            effect_delta = effect_nutrition_deltas.get(nutrition_key, 0.0)
            base_max = float(definition.get("max", 100.0))
            base_min = float(definition.get("min", 0.0))
            current_max = float(self.profile.nutrition_max.get(nutrition_key, base_max))
            current_min = float(self.profile.nutrition_min.get(nutrition_key, base_min))

            detail = self._state_runtime_breakdown.get(nutrition_key, {})
            max_flat_delta = float(detail.get("max_flat_delta", current_max - base_max))
            min_flat_delta = float(detail.get("min_flat_delta", current_min - base_min))
            max_fixed_delta = float(detail.get("max_fixed_delta", max_flat_delta))
            min_fixed_delta = float(detail.get("min_fixed_delta", min_flat_delta))
            max_percent_value_delta = float(detail.get("max_percent_value_delta", max_flat_delta - max_fixed_delta))
            min_percent_value_delta = float(detail.get("min_percent_value_delta", min_flat_delta - min_fixed_delta))
            max_percent_add = float(detail.get("max_percent_add", 0.0))
            max_percent_sub = float(detail.get("max_percent_sub", 0.0))
            min_percent_add = float(detail.get("min_percent_add", 0.0))
            min_percent_sub = float(detail.get("min_percent_sub", 0.0))
            tick_delta = float(detail.get("tick_delta", -decay + effect_delta))

            snapshot.append(
                {
                    "id": nutrition_key,
                    "name": nutrition_name,
                    "value": float(self.profile.nutrition.get(nutrition_key, definition.get("default", 0.0))),
                    "base_min": base_min,
                    "base_max": base_max,
                    "min": current_min,
                    "max": current_max,
                    "overflow": max(0.0, current_max - base_max),
                    "max_flat_delta": max_flat_delta,
                    "min_flat_delta": min_flat_delta,
                    "max_fixed_delta": max_fixed_delta,
                    "min_fixed_delta": min_fixed_delta,
                    "max_percent_value_delta": max_percent_value_delta,
                    "min_percent_value_delta": min_percent_value_delta,
                    "max_percent_add": max_percent_add,
                    "max_percent_sub": max_percent_sub,
                    "min_percent_add": min_percent_add,
                    "min_percent_sub": min_percent_sub,
                    "max_percent_net": max_percent_add + max_percent_sub,
                    "min_percent_net": min_percent_add + min_percent_sub,
                    "decay": decay,
                    "tick_delta": tick_delta,
                }
            )
        return snapshot

    def get_attr_snapshot(self) -> list[dict[str, Any]]:
        """返回每个属性的值分解快照：基础值、永久修正、效果修正、等级修正、颜色、经验、等级。"""
        if not self.attr_definitions:
            return []
        attr_keys = list(self.attr_definitions.keys())
        effect_deltas: dict[str, float] = {k: 0.0 for k in attr_keys}
        for effect in self.profile.active_effects:
            for attr, delta in effect.attr_modifiers.items():
                if attr in effect_deltas:
                    effect_deltas[attr] += float(delta)

        result: list[dict[str, Any]] = []
        for attr in attr_keys:
            defn = self.attr_definitions.get(attr, {})
            base = float(defn.get("initial", 10.0))
            color = str(defn.get("color", "#666666"))
            i18n_key = str(defn.get("i18n_key") or f"life.attr.{attr}")
            name = tr(i18n_key, default=str(defn.get("name", attr)))
            current = float(self.profile.attrs.get(attr, 0.0))
            effect_delta = effect_deltas.get(attr, 0.0)
            item_permanent_delta = float(self.profile.permanent_attr_delta.get(attr, 0.0))
            # level_bonus：用于展示，从当前 profile.attrs 中反推全局等级贡献
            level_bonus = self._compute_char_level_attr_bonus(attr, self.profile.level)
            # permanent_delta = 总变化 - effect修正 - 物品永久修正 - 等级修正（剩余为属性经验/升级带来的永久修正）
            permanent_delta = current - base - effect_delta - item_permanent_delta - level_bonus
            current_exp = float(self.profile.attr_exp.get(attr, 0.0))
            current_level = int(self.profile.attr_level.get(attr, 0))
            level_table = defn.get("level_table", [])
            next_exp_required: float | None = None
            if isinstance(level_table, list):
                for lt_entry in level_table:
                    if lt_entry.get("level", 0) > current_level:
                        next_exp_required = float(lt_entry["exp_required"])
                        break
            inventory_bonus = self._inventory_passive_attrs.get(attr, 0.0)
            result.append({
                "id": attr,
                "name": name,
                "color": color,
                "value": current,
                "base": base,
                "permanent_delta": permanent_delta,
                "effect_delta": effect_delta,
                "inventory_bonus": inventory_bonus,
                "exp": current_exp,
                "level": current_level,
                "next_exp_required": next_exp_required,
                "level_bonus": level_bonus,
                "item_permanent_delta": item_permanent_delta,
            })
        return result

    def _compute_char_level_attr_bonus(self, attr_id: str, current_level: int) -> float:
        """计算全局等级 1~current_level 累计带来的属性 attr_id 加成（仅用于展示分层）。"""
        defn = self.attr_definitions.get(attr_id, {})
        char_level_bonuses = defn.get("char_level_bonuses")
        if not isinstance(char_level_bonuses, list):
            return 0.0
        total = 0.0
        for bonus_entry in char_level_bonuses:
            if not isinstance(bonus_entry, dict):
                continue
            b_type = str(bonus_entry.get("type") or "").strip()
            b_bonus: dict = bonus_entry.get("bonus") or {}
            if not isinstance(b_bonus, dict) or attr_id not in b_bonus:
                continue
            try:
                bonus_val = float(b_bonus[attr_id])
            except Exception:
                continue
            if b_type == "at_level":
                trigger_level = int(bonus_entry.get("level", -1))
                if 1 <= trigger_level <= current_level:
                    total += bonus_val
            elif b_type == "per_levels":
                every = int(bonus_entry.get("every", 0))
                if every <= 0:
                    continue
                offset = int(bonus_entry.get("min_level_offset", 0))
                first_trigger = offset + every + 1
                if current_level >= first_trigger:
                    count = (current_level - offset - 1) // every
                    total += bonus_val * count
        return total

    def get_collection_snapshot(self) -> dict[str, Any]:
        """返回图鉴快照，包含物品/效果/触发器/事件结果的收集进度。"""
        def _entry(rid: str, record: dict) -> dict:
            return {
                "id": rid,
                "name": self._resolve_record_name(record, rid),
                "desc": self._resolve_record_desc(record),
            }

        # 物品：动态判断背包持有
        item_entries: list[dict] = []
        items_unlocked = 0
        for rid, rec in self.item_registry.items():
            unlocked = self.profile.inventory.get(rid, 0) > 0
            entry = _entry(rid, rec)
            entry["unlocked"] = unlocked
            item_entries.append(entry)
            if unlocked:
                items_unlocked += 1

        # buff
        buff_entries: list[dict] = []
        buffs_unlocked = 0
        for rid, rec in self.buff_registry.items():
            if rid == "death":
                continue
            unlocked = rid in self.profile.unlocked_buffs
            entry = _entry(rid, rec)
            entry["unlocked"] = unlocked
            buff_entries.append(entry)
            if unlocked:
                buffs_unlocked += 1

        # 事件触发器
        trigger_entries: list[dict] = []
        triggers_unlocked = 0
        for rid, rec in self.event_trigger_registry.items():
            unlocked = rid in self.profile.unlocked_triggers
            entry = _entry(rid, rec)
            entry["unlocked"] = unlocked
            trigger_entries.append(entry)
            if unlocked:
                triggers_unlocked += 1

        # 事件结果
        outcome_entries: list[dict] = []
        outcomes_unlocked = 0
        for rid, rec in self.event_outcome_registry.items():
            unlocked = rid in self.profile.unlocked_outcomes
            entry = _entry(rid, rec)
            entry["unlocked"] = unlocked
            outcome_entries.append(entry)
            if unlocked:
                outcomes_unlocked += 1

        # 排序：已解锁在前，其余按 id 字母序
        def sort_key(e: dict) -> tuple:
            return (0 if e["unlocked"] else 1, str(e.get("id", "")))

        item_entries.sort(key=sort_key)
        buff_entries.sort(key=sort_key)
        trigger_entries.sort(key=sort_key)
        outcome_entries.sort(key=sort_key)

        return {
            "items": {
                "total": len(item_entries),
                "unlocked": items_unlocked,
                "entries": item_entries,
            },
            "buffs": {
                "total": len(buff_entries),
                "unlocked": buffs_unlocked,
                "entries": buff_entries,
            },
            "triggers": {
                "total": len(trigger_entries),
                "unlocked": triggers_unlocked,
                "entries": trigger_entries,
            },
            "outcomes": {
                "total": len(outcome_entries),
                "unlocked": outcomes_unlocked,
                "entries": outcome_entries,
            },
        }

    def unlock_all_collections(self) -> None:
        """解锁全部图鉴（物品、效果、触发器、事件结果）。"""
        for rid in self.item_registry:
            if self.profile.inventory.get(rid, 0) <= 0:
                self.profile.inventory[rid] = 1
        for rid in self.buff_registry:
            if rid != "death":
                self.profile.unlocked_buffs.add(rid)
        for rid in self.event_trigger_registry:
            self.profile.unlocked_triggers.add(rid)
        for rid in self.event_outcome_registry:
            self.profile.unlocked_outcomes.add(rid)
        self._recompute_inventory_passive_attrs()
        _log.INFO("[Life]已解锁全部图鉴")

    def gain_attr_exp(self, attr_id: str, amount: float) -> list[dict[str, Any]]:
        """给指定属性增加经验值，触发升级和永久加成。返回本次升级事件列表。"""
        if attr_id not in self.profile.attr_exp:
            self.profile.attr_exp[attr_id] = 0.0
        if attr_id not in self.profile.attr_level:
            self.profile.attr_level[attr_id] = 0
        try:
            delta = float(amount)
        except Exception:
            return []
        if delta <= 0:
            return []
        self.profile.attr_exp[attr_id] += delta
        return self._process_attr_levelup(attr_id)

    def _apply_attr_exp_delta(self, exp_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """批量处理 attr_exp 字典，返回所有升级事件。"""
        levelups: list[dict[str, Any]] = []
        if not isinstance(exp_dict, dict):
            return levelups
        for attr_id, amount in exp_dict.items():
            try:
                levelups.extend(self.gain_attr_exp(str(attr_id), float(amount)))
            except Exception:
                pass
        return levelups

    def _process_attr_levelup(self, attr_id: str) -> list[dict[str, Any]]:
        """检查属性经验是否达到升级阈值，应用永久加成，返回升级事件列表。"""
        defn = self.attr_definitions.get(attr_id, {})
        level_table = defn.get("level_table", [])
        if not isinstance(level_table, list) or not level_table:
            return []

        levelup_events: list[dict[str, Any]] = []
        current_level = int(self.profile.attr_level.get(attr_id, 0))
        current_exp = float(self.profile.attr_exp.get(attr_id, 0.0))

        while True:
            next_entry = None
            for lt_entry in level_table:
                if lt_entry.get("level", 0) == current_level + 1:
                    next_entry = lt_entry
                    break
            if next_entry is None:
                break
            exp_required = float(next_entry["exp_required"])
            if current_exp < exp_required:
                break

            current_level += 1
            permanent_bonus = next_entry.get("permanent_bonus", {})
            if isinstance(permanent_bonus, dict):
                for key, value in permanent_bonus.items():
                    if key in self.profile.attrs:
                        try:
                            self.profile.attrs[key] = self.profile.attrs.get(key, 0.0) + float(value)
                        except Exception:
                            pass
                    elif key.endswith("_max") or key.endswith("_min"):
                        suffix = "_max" if key.endswith("_max") else "_min"
                        state_key = key[: -len(suffix)]
                        mode = suffix[1:]
                        if state_key in self.state_keys:
                            self._static_cap_modifiers.append((mode, state_key, value))

            self._refresh_attr_range_effects()

            attr_name = tr(
                str(defn.get("i18n_key") or f"life.attr.{attr_id}"),
                default=str(defn.get("name", attr_id)),
            )
            event = {
                "type": "attr_levelup",
                "attr_id": attr_id,
                "attr_name": attr_name,
                "new_level": current_level,
                "permanent_bonus": dict(permanent_bonus) if isinstance(permanent_bonus, dict) else {},
            }
            levelup_events.append(event)
            _log.INFO(f"[Life][Attr]升级: {attr_id} -> Lv{current_level}")

        self.profile.attr_level[attr_id] = current_level
        return levelup_events

    # ── Event system ────────────────────────────────────────────────

    def get_trigger_cooldown_remaining(self, trigger_id: str) -> float:
        ready_at = self._trigger_cooldowns.get(trigger_id)
        if ready_at is None:
            return 0.0
        return max(0.0, ready_at - time.time())

    def can_fire_trigger(self, trigger_id: str) -> tuple[bool, str]:
        """检查事件触发器是否可以触发。返回 (可否, 原因)。"""
        trigger = self.event_trigger_registry.get(trigger_id)
        if not trigger:
            return False, "unknown_trigger"
        if self.is_dead:
            classes = trigger.get("classes", [])
            if not isinstance(classes, list) or "emergency" not in classes:
                return False, "dead"
        if self.paused:
            return False, "paused"
        # 正在执行中
        if trigger_id in self._trigger_executing:
            finish_at = self._trigger_executing[trigger_id]
            if time.time() < finish_at:
                return False, "executing"

        now = time.time()
        running_ids = [
            tid
            for tid, finish_at in self._trigger_executing.items()
            if tid != trigger_id and finish_at > now
        ]

        tags_mode = str(trigger.get("tags_mode") or "normal").strip().lower()
        if tags_mode == "reverse_global" and running_ids:
            return False, "reverse_global_busy"
        for running_id in running_ids:
            running_trigger = self.event_trigger_registry.get(running_id, {})
            running_mode = str(running_trigger.get("tags_mode") or "normal").strip().lower()
            if running_mode == "global":
                return False, f"global_busy:{running_id}"
        if tags_mode == "global" and running_ids:
            return False, "global_requires_idle"

        if bool(trigger.get("mutex_by_tag", False)):
            trigger_tags: set[str] = set(str(t).strip() for t in (trigger.get("tags") or []) if str(t).strip())
            if trigger_tags:
                for running_id in running_ids:
                    running_trigger = self.event_trigger_registry.get(running_id, {})
                    running_tags: set[str] = set(
                        str(t).strip() for t in (running_trigger.get("tags") or []) if str(t).strip()
                    )
                    common_tags = trigger_tags & running_tags
                    if common_tags:
                        return False, f"tag_mutex:{sorted(common_tags)[0]}"
        # 自身 CD
        if self.get_trigger_cooldown_remaining(trigger_id) > 0:
            return False, "on_cooldown"
        # 互斥检查：若 A.mutex 包含 B，则 B 在 CD 中时 A 不可使用
        mutex_list = trigger.get("mutex", [])
        if isinstance(mutex_list, list):
            for other_id in mutex_list:
                other_id = str(other_id).strip()
                if not other_id:
                    continue
                if self.get_trigger_cooldown_remaining(other_id) > 0:
                    return False, f"mutex:{other_id}"
        # 必须拥有该物品
        requires_item = trigger.get("requires_item")
        if requires_item is not None:
            check_ids = [requires_item] if isinstance(requires_item, str) else list(requires_item)
            for item_id in check_ids:
                item_id = str(item_id).strip()
                if not item_id:
                    continue
                if self.profile.inventory.get(item_id, 0) < 1:
                    return False, f"missing_item:{item_id}"
        # 必须没有该物品
        requires_no_item = trigger.get("requires_no_item")
        if requires_no_item is not None:
            check_ids = [requires_no_item] if isinstance(requires_no_item, str) else list(requires_no_item)
            for item_id in check_ids:
                item_id = str(item_id).strip()
                if not item_id:
                    continue
                if self.profile.inventory.get(item_id, 0) >= 1:
                    return False, f"has_item:{item_id}"
        # 必须拥有该 buff
        active_ids = {e.effect_id for e in self.profile.active_effects}
        requires_buff = trigger.get("requires_buff")
        if requires_buff is not None:
            check_ids = [requires_buff] if isinstance(requires_buff, str) else list(requires_buff)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid not in active_ids:
                    return False, f"missing_buff:{bid}"
        # 必须没有该 buff
        requires_no_buff = trigger.get("requires_no_buff")
        if requires_no_buff is not None:
            check_ids = [requires_no_buff] if isinstance(requires_no_buff, str) else list(requires_no_buff)
            for bid in check_ids:
                bid = str(bid).strip()
                if bid and bid in active_ids:
                    return False, f"has_buff:{bid}"
        # 检查标签注册表的限制：若标签关联的 buff 处于活跃状态，且标签为 global_event，触发器必须拥有该标签
        trigger_tags: set[str] = set(trigger.get("tags") or [])
        for tag_id, tag_def in self.tag_registry.items():
            if not bool(tag_def.get("global_event", False)):
                continue
            linked_buff = str(tag_def.get("buff_id") or "").strip()
            if linked_buff and linked_buff in active_ids:
                if tag_id not in trigger_tags:
                    return False, f"tag_restricted:{tag_id}"

        # 最低触发等级
        min_level = trigger.get("min_level")
        if min_level is not None:
            try:
                if self.profile.level < int(min_level):
                    return False, "level_too_low"
            except Exception:
                pass

        # 成本校验（仅校验 state，真实扣除在 fire_trigger）
        costs = trigger.get("costs")
        if isinstance(costs, dict):
            for state_key, raw_cost in costs.items():
                key = str(state_key).strip()
                if key not in self.state_keys:
                    continue
                try:
                    cost_val = float(raw_cost)
                except Exception:
                    continue
                if cost_val <= 0:
                    continue
                current_val = float(self.profile.states.get(key, 0.0))
                if current_val < cost_val:
                    return False, f"insufficient_state:{key}"

        return True, ""

    def get_trigger_fail_message(self, trigger_id: str, reason: str) -> str | None:
        """从触发器 json 的 fail_messages 中查找对应原因的自定义文本，支持前缀通配匹配。
        对 tag_restricted:{tag_id} 原因额外回查标签注册表的 fire_restricted_i18n_key。"""
        trigger = self.event_trigger_registry.get(trigger_id)
        if trigger:
            fail_messages = trigger.get("fail_messages")
            if isinstance(fail_messages, dict):
                if reason in fail_messages:
                    return str(fail_messages[reason])
                colon_idx = reason.find(":")
                if colon_idx >= 0:
                    prefix = reason[:colon_idx]
                    if f"{prefix}:*" in fail_messages:
                        return str(fail_messages[f"{prefix}:*"])
                    if prefix in fail_messages:
                        return str(fail_messages[prefix])
        # 标签限制：从标签注册表读取 fire_restricted_i18n_key
        if reason.startswith("tag_restricted:"):
            tag_id = reason[len("tag_restricted:"):]
            tag_def = self.tag_registry.get(tag_id)
            if tag_def:
                i18n_key = str(tag_def.get("fire_restricted_i18n_key") or "").strip()
                if i18n_key:
                    return tr(i18n_key)
        return None

    def get_trigger_executing_remaining(self, trigger_id: str) -> float:
        """返回触发器剩余执行时间（0 表示未在执行中）。"""
        finish_at = self._trigger_executing.get(trigger_id)
        if finish_at is None:
            return 0.0
        remaining = finish_at - time.time()
        if remaining <= 0:
            return 0.0
        return remaining

    def fire_trigger(self, trigger_id: str) -> dict[str, Any] | None:
        """执行事件触发器，返回执行结果摘要（用于 UI 展示），失败返回 None。"""
        can, reason = self.can_fire_trigger(trigger_id)
        if not can:
            _log.WARN(f"[Life][Event]触发器不可用: {trigger_id} reason={reason}")
            return None

        trigger = self.event_trigger_registry[trigger_id]
        trigger_name = self._resolve_record_name(trigger, trigger_id)

        # 通过 can_fire_trigger 后立即扣除成本，确保执行中事件不会规避消耗。
        self._apply_trigger_costs(trigger)

        # 执行时间：duration_s > 0 时先进入执行状态，延迟产出结果
        duration_s = trigger.get("duration_s")
        has_duration = False
        if duration_s is not None:
            try:
                dur = float(duration_s)
                if dur > 0:
                    self._trigger_executing[trigger_id] = time.time() + dur
                    has_duration = True
                    _log.DEBUG(f"[Life][Event]开始执行: {trigger_id} 耗时={dur}s")
            except Exception:
                pass

        if has_duration:
            _log.INFO(f"[Life][Event]开始执行 trigger={trigger_id} name={trigger_name} duration={float(duration_s)}")
            self._append_recent_event_log(
                {
                    "type": "pending",
                    "source": "trigger",
                    "trigger_id": trigger_id,
                    "trigger_name": trigger_name,
                }
            )
            # 尚未完成，返回 pending 结果（UI 可据此显示进度）
            return {
                "trigger_id": trigger_id,
                "trigger_name": trigger_name,
                "pending": True,
                "duration_s": float(duration_s),
                "results": [],
            }

        # 无执行时间，立即执行
        return self._complete_trigger(trigger_id)

    def _complete_trigger(self, trigger_id: str) -> dict[str, Any]:
        """执行触发器的实际效果并启动冷却。"""
        trigger = self.event_trigger_registry[trigger_id]
        trigger_name = self._resolve_record_name(trigger, trigger_id)

        # 从执行中移除
        self._trigger_executing.pop(trigger_id, None)

        # 启动冷却
        cooldown_s = trigger.get("cooldown_s")
        if cooldown_s is not None:
            try:
                cd = float(cooldown_s)
                if cd > 0:
                    self._trigger_cooldowns[trigger_id] = time.time() + cd
            except Exception:
                pass

        result_log: list[dict[str, Any]] = []
        self._execute_event_guaranteed(trigger, result_log)
        self._execute_event_random_pools(trigger, result_log)

        # 图鉴：记录已解锁的触发器
        self.profile.unlocked_triggers.add(trigger_id)

        _log.DEBUG(f"[Life][Event]完成触发: {trigger_id} 结果数={len(result_log)}")
        _log.INFO(f"[Life][Event]执行完成 trigger={trigger_id} name={trigger_name} results={len(result_log)}")
        # 触发绑定动作
        self._trigger_record_action(trigger)
        self._append_recent_event_log(
            {
                "type": "completed",
                "source": "trigger",
                "trigger_id": trigger_id,
                "trigger_name": trigger_name,
            }
        )
        self._append_recent_result_logs(
            trigger_id=trigger_id,
            trigger_name=trigger_name,
            source="trigger",
            result_log=result_log,
            add_none_when_empty=True,
        )
        for entry in result_log:
            et = str(entry.get("type") or "")
            eid = str(entry.get("id") or "")
            if et == "item":
                _log.INFO(f"[Life][Event][Result] trigger={trigger_id} type=item id={eid} count={int(entry.get('count', 1))}")
            elif et == "outcome":
                _log.INFO(f"[Life][Event][Result] trigger={trigger_id} type=outcome id={eid} name={entry.get('name', eid)}")
            elif et == "buff":
                _log.INFO(f"[Life][Event][Result] trigger={trigger_id} type=buff id={eid}")
        return {
            "trigger_id": trigger_id,
            "trigger_name": trigger_name,
            "pending": False,
            "results": result_log,
        }

    def _apply_trigger_costs(self, trigger: dict[str, Any]) -> None:
        costs = trigger.get("costs")
        if not isinstance(costs, dict):
            return
        trigger_id = str(trigger.get("id") or trigger.get("name") or "anonymous")
        for state_key, raw_cost in costs.items():
            key = str(state_key).strip()
            if key not in self.state_keys:
                continue
            try:
                cost_val = float(raw_cost)
            except Exception:
                continue
            if cost_val <= 0:
                continue
            self._change_state(key, -cost_val)
            _log.DEBUG(f"[Life][Event]扣除触发成本 trigger={trigger_id} state={key} cost={cost_val}")

    def tick_triggers(self) -> list[dict[str, Any]]:
        """检查执行中的触发器并完成到期的。返回本次 tick 完成的结果列表。"""
        completed: list[dict[str, Any]] = []
        now = time.time()
        for trigger_id in list(self._trigger_executing):
            if now >= self._trigger_executing[trigger_id]:
                result = self._complete_trigger(trigger_id)
                completed.append(result)
        if completed:
            self._completed_trigger_results.extend(completed)
            _log.DEBUG(f"[Life][Event]本 tick 完成触发器数量={len(completed)}")
        return completed

    def pop_completed_trigger_results(self) -> list[dict[str, Any]]:
        """取出并清空执行完成事件队列。"""
        if not self._completed_trigger_results:
            return []
        payload = list(self._completed_trigger_results)
        self._completed_trigger_results.clear()
        return payload

    def _append_recent_event_log(self, row: dict[str, Any]) -> None:
        if not isinstance(row, dict):
            return
        self._recent_event_log_seq += 1
        payload = dict(row)
        payload["seq"] = int(self._recent_event_log_seq)
        payload["ts"] = float(time.time())
        self._recent_event_logs.append(payload)
        self._recent_event_logs = self._recent_event_logs[-self._RECENT_EVENT_LOG_MAX:]

    def _append_recent_result_logs(
        self,
        trigger_id: str,
        trigger_name: str,
        source: str,
        result_log: list[dict[str, Any]],
        add_none_when_empty: bool,
    ) -> None:
        if not result_log:
            if add_none_when_empty:
                self._append_recent_event_log(
                    {
                        "type": "result",
                        "source": source,
                        "trigger_id": trigger_id,
                        "trigger_name": trigger_name,
                        "entry": {"type": "none"},
                    }
                )
            return

        for entry in result_log:
            if not isinstance(entry, dict):
                continue
            self._append_recent_event_log(
                {
                    "type": "result",
                    "source": source,
                    "trigger_id": trigger_id,
                    "trigger_name": trigger_name,
                    "entry": dict(entry),
                }
            )

    def get_recent_event_logs(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._recent_event_logs]

    def _execute_event_guaranteed(self, record: dict[str, Any], result_log: list[dict[str, Any]]) -> None:
        guaranteed = record.get("guaranteed")
        if not isinstance(guaranteed, dict):
            return
        # 必定给予物品
        for item_entry in guaranteed.get("items", []):
            if not isinstance(item_entry, dict):
                continue
            item_id = str(item_entry.get("id") or "").strip()
            count = max(1, int(item_entry.get("count", 1)))
            if item_id and self.add_item(item_id, count):
                item_record = self.item_registry.get(item_id, {})
                item_name = self._resolve_record_name(item_record, item_id)
                result_log.append({"type": "item", "id": item_id, "name": item_name, "count": count})
        # 必定给予 buff
        for buff_entry in guaranteed.get("buffs", []):
            buff_id = str(buff_entry).strip() if not isinstance(buff_entry, dict) else str(buff_entry.get("id") or "").strip()
            if buff_id and self.apply_buff(buff_id):
                buff_record = self.buff_registry.get(buff_id, {})
                buff_name = self._resolve_record_name(buff_record, buff_id)
                result_log.append({"type": "buff", "id": buff_id, "name": buff_name})
        # 必定触发事件结果
        for outcome_entry in guaranteed.get("outcomes", []):
            outcome_id = str(outcome_entry).strip() if not isinstance(outcome_entry, dict) else str(outcome_entry.get("id") or "").strip()
            if outcome_id:
                self._execute_outcome(outcome_id, result_log, depth=0)

    def _execute_event_random_pools(self, record: dict[str, Any], result_log: list[dict[str, Any]]) -> None:
        pools = record.get("random_pools")
        if not isinstance(pools, list):
            return
        for pool in pools:
            if not isinstance(pool, dict):
                continue
            entries = pool.get("entries")
            if not isinstance(entries, list) or not entries:
                continue
            self._roll_random_pool(pool, result_log, depth=0)

    def _roll_random_pool(self, pool: dict[str, Any], result_log: list[dict[str, Any]], depth: int) -> None:
        if depth > 10:
            _log.WARN("[Life][Event]事件链深度超过10，中止")
            return
        entries = pool.get("entries")
        if not isinstance(entries, list):
            return
        valid_entries = [e for e in entries if isinstance(e, dict)]
        if not valid_entries:
            return

        # 计算基础概率与属性加成后的有效概率
        base_chances = [float(e.get("chance", 0)) for e in valid_entries]
        base_total = sum(base_chances)

        effective_chances: list[float] = []
        for entry, base_chance in zip(valid_entries, base_chances):
            attr_bonus = entry.get("attr_bonus")
            bonus = 0.0
            try:
                bonus += float(entry.get("flat_bonus", 0.0))
            except Exception:
                pass
            if isinstance(attr_bonus, dict):
                for attr_key, bonus_per_point in attr_bonus.items():
                    attr_val = self._effective_attr(str(attr_key))
                    try:
                        bonus += float(attr_val) * float(bonus_per_point)
                    except Exception:
                        pass
            state_bonus = entry.get("state_bonus")
            if isinstance(state_bonus, dict):
                for state_key, bonus_per_point in state_bonus.items():
                    s_key = str(state_key).strip()
                    if s_key not in self.state_keys:
                        continue
                    state_val = float(self.profile.states.get(s_key, 0.0))
                    try:
                        bonus += state_val * float(bonus_per_point)
                    except Exception:
                        pass
            effective_chances.append(max(0.0, base_chance + bonus))

        # 基础不触发概率固定，不受属性影响。
        # 当 base_total <= 0 时，允许通过 bonus 驱动概率（如 flat_bonus/state_bonus）。
        if base_total > 0:
            base_no_fire = max(0.0, 100.0 - base_total)
        else:
            base_no_fire = 0.0
        effective_total = sum(effective_chances) + base_no_fire
        if effective_total <= 0:
            fallback = pool.get("fallback")
            if isinstance(fallback, dict):
                self._apply_pool_entry(fallback, result_log, depth)
            return

        # 归一化：超过100%时等比缩放，保证总概率不超过100%
        if effective_total > 100.0:
            scale = 100.0 / effective_total
            normalized = [c * scale for c in effective_chances]
        else:
            normalized = effective_chances

        roll = random.random() * 100.0
        cumulative = 0.0
        for entry, chance in zip(valid_entries, normalized):
            cumulative += chance
            if roll < cumulative:
                self._apply_pool_entry(entry, result_log, depth)
                break
        else:
            fallback = pool.get("fallback")
            if isinstance(fallback, dict):
                self._apply_pool_entry(fallback, result_log, depth)

    def _apply_pool_entry(self, entry: dict[str, Any], result_log: list[dict[str, Any]], depth: int) -> None:
        entry_type = str(entry.get("type") or "").strip().lower()
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            return

        if entry_type == "item":
            count = max(1, int(entry.get("count", 1)))
            if self.add_item(entry_id, count):
                item_record = self.item_registry.get(entry_id, {})
                item_name = self._resolve_record_name(item_record, entry_id)
                result_log.append({"type": "item", "id": entry_id, "name": item_name, "count": count})
        elif entry_type == "buff":
            if self.apply_buff(entry_id):
                buff_record = self.buff_registry.get(entry_id, {})
                buff_name = self._resolve_record_name(buff_record, entry_id)
                result_log.append({"type": "buff", "id": entry_id, "name": buff_name})
        elif entry_type == "outcome":
            self._execute_outcome(entry_id, result_log, depth=depth)

    def _execute_outcome(self, outcome_id: str, result_log: list[dict[str, Any]], depth: int) -> None:
        if depth > 10:
            _log.WARN(f"[Life][Event]事件链深度超过10，跳过: {outcome_id}")
            return
        outcome = self.event_outcome_registry.get(outcome_id)
        if not outcome:
            _log.WARN(f"[Life][Event]未知事件结果: {outcome_id}")
            return

        outcome_name = self._resolve_record_name(outcome, outcome_id)
        outcome_desc = self._resolve_record_desc(outcome)
        result_log.append({"type": "outcome", "id": outcome_id, "name": outcome_name, "desc": outcome_desc})
        # 图鉴：记录已解锁的事件结果
        self.profile.unlocked_outcomes.add(outcome_id)
        _log.DEBUG(f"[Life][Event]应用 outcome id={outcome_id} depth={depth}")

        # 触发绑定动作
        self._trigger_record_action(outcome)

        # 应用 outcome 的直接效果（即时状态变化 + attr_exp）
        effects = outcome.get("effects")
        if isinstance(effects, dict):
            for key, value in effects.items():
                if key in self.state_keys:
                    try:
                        self._change_state(key, float(value))
                    except Exception:
                        pass
            # attr_exp 字段支持
            attr_exp_field = effects.get("attr_exp")
            if isinstance(attr_exp_field, dict):
                levelups = self._apply_attr_exp_delta(attr_exp_field)
                if levelups:
                    self._completed_trigger_results.extend(levelups)
        # outcome 顶层 attr_exp 字段
        top_attr_exp = outcome.get("attr_exp")
        if isinstance(top_attr_exp, dict):
            levelups = self._apply_attr_exp_delta(top_attr_exp)
            if levelups:
                self._completed_trigger_results.extend(levelups)

        # 顶层 permanent_attr_delta：永久属性修正，同时同步到当前属性值。
        permanent_attr_delta = outcome.get("permanent_attr_delta")
        if isinstance(permanent_attr_delta, dict):
            for attr_key, raw_delta in permanent_attr_delta.items():
                a_key = str(attr_key).strip()
                if a_key not in self.attr_keys:
                    continue
                try:
                    delta = float(raw_delta)
                except Exception:
                    continue
                if delta == 0:
                    continue
                self.profile.permanent_attr_delta[a_key] = self.profile.permanent_attr_delta.get(a_key, 0.0) + delta
                self.profile.attrs[a_key] = self.profile.attrs.get(a_key, 0.0) + delta

        self._execute_event_guaranteed(outcome, result_log)

        pools = outcome.get("random_pools")
        if isinstance(pools, list):
            for pool in pools:
                if not isinstance(pool, dict):
                    continue
                entries = pool.get("entries")
                if isinstance(entries, list) and entries:
                    self._roll_random_pool(pool, result_log, depth=depth + 1)

        self._clear_buffs_from_record(outcome)

    def get_tag_display_map(self) -> dict[str, dict[str, str]]:
        """返回标签 ID → {name, color} 映射，供 UI 渲染标签气泡。"""
        result: dict[str, dict[str, str]] = {}
        for tag_id, tag_def in self.tag_registry.items():
            name = tag_def.get("name", tag_id)
            i18n_key = tag_def.get("i18n_key")
            if i18n_key:
                from util.i18n import tr
                resolved = tr(i18n_key)
                if resolved != i18n_key:
                    name = resolved
            result[tag_id] = {
                "name": name,
                "color": tag_def.get("color", "#888888"),
            }
        return result

    def get_event_triggers_snapshot(self) -> list[dict[str, Any]]:
        """返回所有已注册事件触发器的快照列表（用于 UI 展示）。"""
        snapshot: list[dict[str, Any]] = []
        for trigger_id, trigger in self.event_trigger_registry.items():
            cooldown_remaining = self.get_trigger_cooldown_remaining(trigger_id)
            executing_remaining = self.get_trigger_executing_remaining(trigger_id)
            can, reason = self.can_fire_trigger(trigger_id)
            snapshot.append({
                "id": trigger_id,
                "name": self._resolve_record_name(trigger, trigger_id),
                "desc": self._resolve_record_desc(trigger),
                "cooldown_s": float(trigger.get("cooldown_s", 0)),
                "duration_s": float(trigger.get("duration_s", 0)),
                "cooldown_remaining": cooldown_remaining,
                "executing_remaining": executing_remaining,
                "on_cooldown": cooldown_remaining > 0,
                "executing": executing_remaining > 0,
                "can_fire": can,
                "block_reason": reason,
                "mutex": list(trigger.get("mutex", [])),
                "mutex_by_tag": bool(trigger.get("mutex_by_tag", False)),
                "tags_mode": str(trigger.get("tags_mode") or "normal"),
                "costs": dict(trigger.get("costs") or {}),
                "classes": list(trigger.get("_classes", [])),
                "tags": list(trigger.get("tags") or []),
            })
        return snapshot

    def get_event_trigger_detail(self, trigger_id: str) -> dict[str, Any] | None:
        trigger = self.event_trigger_registry.get(trigger_id)
        if not trigger:
            return None
        payload = dict(trigger)
        payload["name"] = self._resolve_record_name(trigger, trigger_id)
        payload["desc"] = self._resolve_record_desc(trigger)
        return payload

    def get_event_outcome_detail(self, outcome_id: str) -> dict[str, Any] | None:
        outcome = self.event_outcome_registry.get(outcome_id)
        if not outcome:
            return None
        payload = dict(outcome)
        payload["name"] = self._resolve_record_name(outcome, outcome_id)
        payload["desc"] = self._resolve_record_desc(outcome)
        return payload

    def list_event_trigger_ids(self) -> list[str]:
        return sorted(self.event_trigger_registry.keys())

    def list_event_outcome_ids(self) -> list[str]:
        return sorted(self.event_outcome_registry.keys())

    def fire_outcome(self, outcome_id: str) -> bool:
        outcome = self.event_outcome_registry.get(outcome_id)
        if not outcome:
            return False
        self._execute_outcome(outcome_id, [], 0)
        return True

    def _clamp_state(self, state: str) -> None:
        lo = self.profile.state_min.get(state, 0.0)
        hi = self.profile.state_max.get(state, 100.0)
        self.profile.states[state] = max(lo, min(hi, self.profile.states[state]))

    def _to_delta(self, value: Any, base: float) -> float:
        if isinstance(value, str) and value.strip().endswith("%"):
            raw = float(value.strip().rstrip("%"))
            return base * raw / 100.0
        return float(value)

    def _to_multiplier(self, value: Any) -> float:
        if isinstance(value, str) and value.strip().endswith("%"):
            raw = float(value.strip().rstrip("%"))
            return 1.0 + raw / 100.0
        return float(value)

    def _to_float_safe(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def dump_profile(self) -> dict[str, Any]:
        now = time.time()
        return {
            "states": self.profile.states,
            "state_max": self.profile.state_max,
            "state_min": self.profile.state_min,
            "nutrition": self.profile.nutrition,
            "attrs": self.profile.attrs,
            "inventory": self.profile.inventory,
            "item_cooldowns": {
                k: round(v - now, 3)
                for k, v in self._item_cooldowns.items()
                if v > now
            },
            "trigger_cooldowns": {
                k: round(v - now, 3)
                for k, v in self._trigger_cooldowns.items()
                if v > now
            },
            "trigger_executing": {
                k: round(v - now, 3)
                for k, v in self._trigger_executing.items()
                if v > now
            },
            "active_effects": [
                {
                    "effect_id": e.effect_id,
                    "effect_name": e.effect_name,
                    "effect_desc": e.effect_desc,
                    "source": e.source,
                    "per_tick": e.per_tick,
                    "nutrition_per_tick": e.nutrition_per_tick,
                    "remaining_ticks": e.remaining_ticks,
                    "stack_rule": e.stack_rule,
                    "cap_modifiers": e.cap_modifiers,
                    "attr_modifiers": e.attr_modifiers,
                    "apply_states": e.apply_states,
                    "managed": e.managed,
                }
                for e in self.profile.active_effects
            ],
            "is_dead": self.is_dead,
            "death_summary": self._death_summary,
            "life_started_at": self._life_started_at,
            "attr_exp": dict(self.profile.attr_exp),
            "attr_level": dict(self.profile.attr_level),
            "attr_base": dict(self.profile.attr_base),
            # 全局等级系统
            "level": self.profile.level,
            "exp": self.profile.exp,
            "permanent_attr_delta": dict(self.profile.permanent_attr_delta),
            # 图鉴收集
            "unlocked_buffs": list(self.profile.unlocked_buffs),
            "unlocked_triggers": list(self.profile.unlocked_triggers),
            "unlocked_outcomes": list(self.profile.unlocked_outcomes),
            "recent_event_logs": list(self._recent_event_logs),
            "recent_event_log_seq": int(self._recent_event_log_seq),
        }

    def load_profile(self, data: dict[str, Any]) -> None:
        # 死亡状态恢复
        self.is_dead = bool(data.get("is_dead", False))
        self._death_summary = data.get("death_summary") if self.is_dead else None
        started = data.get("life_started_at")
        if started is not None:
            try:
                self._life_started_at = float(started)
            except Exception:
                pass
        if self.is_dead:
            self.paused = True

        self.profile.states.update(data.get("states", {}))
        raw_nutrition = data.get("nutrition", {})
        if isinstance(raw_nutrition, dict):
            for key, value in raw_nutrition.items():
                if str(key) not in self.profile.nutrition:
                    continue
                self.profile.nutrition[str(key)] = self._to_float_safe(value, self.profile.nutrition[str(key)])
        self.profile.attrs.update(data.get("attrs", {}))
        # attr_exp / attr_level 恢复
        raw_attr_exp = data.get("attr_exp", {})
        if isinstance(raw_attr_exp, dict):
            for k, v in raw_attr_exp.items():
                try:
                    self.profile.attr_exp[str(k)] = float(v)
                except Exception:
                    pass
        raw_attr_level = data.get("attr_level", {})
        if isinstance(raw_attr_level, dict):
            for k, v in raw_attr_level.items():
                try:
                    self.profile.attr_level[str(k)] = int(v)
                except Exception:
                    pass
        raw_attr_base = data.get("attr_base", {})
        if isinstance(raw_attr_base, dict):
            for k, v in raw_attr_base.items():
                try:
                    self.profile.attr_base[str(k)] = float(v)
                except Exception:
                    pass
        # 全局等级系统恢复（向后兼容，旧存档无该字段时使用默认值）
        try:
            self.profile.level = max(1, int(data.get("level", 1)))
        except Exception:
            self.profile.level = 1
        try:
            self.profile.exp = max(0.0, float(data.get("exp", 0.0)))
        except Exception:
            self.profile.exp = 0.0
        raw_perm = data.get("permanent_attr_delta", {})
        if isinstance(raw_perm, dict):
            for k, v in raw_perm.items():
                try:
                    self.profile.permanent_attr_delta[str(k)] = float(v)
                except Exception:
                    pass
        # 满级 clamp（存档等级可能高于当前配置最高等级）
        if self.profile.level > self._max_level:
            self.profile.level = self._max_level

        parsed_inventory: dict[str, int] = {}
        raw_inventory = data.get("inventory", {})
        if isinstance(raw_inventory, dict):
            for k, v in raw_inventory.items():
                try:
                    count = int(v)
                except Exception:
                    continue
                if count > 0:
                    parsed_inventory[str(k)] = count
        self.profile.inventory = parsed_inventory

        self.profile.active_effects = []
        for raw in data.get("active_effects", []):
            if not isinstance(raw, dict):
                continue
            self.profile.active_effects.append(
                LifeEffect(
                    effect_id=str(raw.get("effect_id", "")),
                    effect_name=str(raw.get("effect_name") or raw.get("effect_id") or ""),
                    effect_desc=str(raw.get("effect_desc", "")),
                    source=str(raw.get("source", "")),
                    per_tick={k: float(v) for k, v in dict(raw.get("per_tick", {})).items()},
                    nutrition_per_tick={k: float(v) for k, v in dict(raw.get("nutrition_per_tick", {})).items()},
                    remaining_ticks=int(raw.get("remaining_ticks", 0)),
                    stack_rule=str(raw.get("stack_rule", "add")),
                    cap_modifiers=[
                        (str(entry[0]), str(entry[1]), entry[2])
                        for entry in list(raw.get("cap_modifiers", []))
                        if isinstance(entry, (list, tuple)) and len(entry) == 3
                    ],
                    attr_modifiers={k: float(v) for k, v in dict(raw.get("attr_modifiers", {})).items()},
                    apply_states={k: float(v) for k, v in dict(raw.get("apply_states", {})).items()},
                    managed=bool(raw.get("managed", False)),
                )
            )

        for state in self.state_keys:
            self._clamp_state(state)
        for nutrition_key in self.nutrition_keys:
            self._clamp_nutrition(nutrition_key)
        self._refresh_attr_range_effects()

        # 移除从存档恢复的 managed effects（来源为 nutrition: 或 state:），
        # 由 sync 方法从当前 buff_registry 重建，确保新的 cap_modifiers 被正确提取
        self.profile.active_effects = [
            e for e in self.profile.active_effects
            if not e.source.startswith("nutrition:") and not e.source.startswith("state:")
        ]
        self._sync_managed_nutrition_buffs()
        self._sync_managed_state_buffs()
        self._refresh_attr_range_effects()

        now = time.time()
        self._item_cooldowns.clear()
        for item_id, remaining in data.get("item_cooldowns", {}).items():
            try:
                r = float(remaining)
            except Exception:
                continue
            if r > 0:
                self._item_cooldowns[str(item_id)] = now + r

        self._trigger_cooldowns.clear()
        for trigger_id, remaining in data.get("trigger_cooldowns", {}).items():
            try:
                r = float(remaining)
            except Exception:
                continue
            if r > 0:
                self._trigger_cooldowns[str(trigger_id)] = now + r

        self._trigger_executing.clear()
        self._completed_trigger_results.clear()
        self._recent_event_logs.clear()
        self._recent_event_log_seq = 0
        for trigger_id, remaining in data.get("trigger_executing", {}).items():
            try:
                r = float(remaining)
            except Exception:
                continue
            if r > 0:
                self._trigger_executing[str(trigger_id)] = now + r

        raw_recent_logs = data.get("recent_event_logs", [])
        if isinstance(raw_recent_logs, list):
            sanitized: list[dict[str, Any]] = []
            for row in raw_recent_logs:
                if isinstance(row, dict):
                    payload = dict(row)
                    if "ts" not in payload:
                        payload["ts"] = 0.0
                    sanitized.append(payload)
            self._recent_event_logs = sanitized[-self._RECENT_EVENT_LOG_MAX:]
        try:
            self._recent_event_log_seq = int(data.get("recent_event_log_seq", 0))
        except Exception:
            self._recent_event_log_seq = 0
        if self._recent_event_log_seq <= 0 and self._recent_event_logs:
            # 兼容旧存档：无 seq 字段时，按现有条目重建序号。
            self._recent_event_log_seq = len(self._recent_event_logs)
            for idx, row in enumerate(self._recent_event_logs, start=1):
                row["seq"] = idx

        # 图鉴收集
        self.profile.unlocked_buffs = set(data.get("unlocked_buffs", []))
        self.profile.unlocked_triggers = set(data.get("unlocked_triggers", []))
        self.profile.unlocked_outcomes = set(data.get("unlocked_outcomes", []))

        self._recompute_inventory_passive_attrs()
        _log.INFO(
            f"[Life]存档已载入 level={self.profile.level} exp={self.profile.exp:.2f} "
            f"inventory={len(self.profile.inventory)} effects={len(self.profile.active_effects)} dead={self.is_dead}"
        )

    def reset_profile(self) -> None:
        """清除所有当前养成数据，恢复到默认初始状态并保存存档。"""
        self._static_cap_modifiers.clear()
        self._attr_cap_bonus_max = {k: 0.0 for k in self.state_keys}
        self._attr_cap_bonus_min = {k: 0.0 for k in self.state_keys}
        self._item_cooldowns.clear()
        self._trigger_cooldowns.clear()
        self._trigger_executing.clear()
        self._completed_trigger_results.clear()
        self._recent_event_logs.clear()
        self._recent_event_log_seq = 0
        self.is_dead = False
        self._death_summary = None
        self._life_started_at = time.time()
        self.profile = self._create_default_profile()
        self._sync_managed_nutrition_buffs()
        self._sync_managed_state_buffs()
        self._refresh_attr_range_effects()
        self.save("default")
        _log.INFO("[Life]养成数据已重置")

    def save(self, profile_id: str = "default") -> None:
        _log.DEBUG(
            f"[Life]准备保存存档 id={profile_id} level={self.profile.level} exp={self.profile.exp:.2f} "
            f"effects={len(self.profile.active_effects)}"
        )
        self.store.save_profile(profile_id, self.dump_profile())

    def load(self, profile_id: str = "default") -> bool:
        payload = self.store.load_profile(profile_id)
        if payload is None:
            _log.INFO(f"[Life]未找到存档，跳过载入: {profile_id}")
            return False
        self.load_profile(payload)
        _log.INFO(f"[Life]load(profile_id={profile_id}) 成功")
        return True

    _EXPORT_FORMAT_VERSION = 1
    _IMPORT_MAX_BYTES = 4 * 1024 * 1024  # 4 MB

    def export_profile(self, file_path: str | Path) -> tuple[bool, str]:
        """将当前养成数据导出为 JSON 文件。\n\n返回 (True, "") 或 (False, 错误原因)。"""
        try:
            path = Path(file_path)
            export_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            payload = {
                "meta": {
                    "format_version": self._EXPORT_FORMAT_VERSION,
                    "export_time": export_time,
                    "character_name": self.character_name,
                },
                "profile": self.dump_profile(),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            _log.INFO(f"[Life]存档已导出: {path}")
            return True, ""
        except Exception as exc:
            _log.EXCEPTION("[Life]存档导出失败", exc)
            return False, str(exc)

    def import_profile(self, file_path: str | Path) -> tuple[bool, str]:
        """从 JSON 文件导入养成存档。\n\n返回 (True, "") 或 (False, 错误原因)。"""
        try:
            path = Path(file_path)
            if not path.is_file():
                return False, f"文件不存在: {path}"
            size = path.stat().st_size
            if size > self._IMPORT_MAX_BYTES:
                mb = size / (1024 * 1024)
                return False, f"文件过大 ({mb:.1f} MB)，导入上限为 4 MB"
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                return False, "文件格式错误：根对象必须是 JSON 对象"
            if "profile" not in data:
                return False, "文件缺少必要的 'profile' 字段"
            meta = data.get("meta", {})
            fmt_ver = meta.get("format_version") if isinstance(meta, dict) else None
            if fmt_ver != self._EXPORT_FORMAT_VERSION:
                return False, f"存档版本不兼容 (format_version={fmt_ver!r})，无法导入"
            self.load_profile(data["profile"])
            _log.INFO(f"[Life]存档已导入: {path}")
            return True, ""
        except json.JSONDecodeError as exc:
            _log.WARN(f"[Life]存档导入失败（JSON 解析错误）: {exc}")
            return False, f"JSON 解析错误: {exc}"
        except Exception as exc:
            _log.EXCEPTION("[Life]存档导入失败", exc)
            return False, str(exc)

    # ═══════════════════════════════════════════════
    # 动作绑定
    # ═══════════════════════════════════════════════

    def _get_action_system(self):
        """获取 ActionSystem 单例（避免循环导入）。"""
        try:
            from module.default.action import get_action_system
            return get_action_system()
        except Exception:
            return None

    def _trigger_record_action(self, record: dict, is_item: bool = False) -> None:
        """根据 record 中的 action_id 触发动作。

        Args:
            record: buff/item/trigger/outcome 的注册数据
            is_item: 是否为物品（物品的 loop 只播放一轮）
        """
        action_id = record.get("action_id")
        _log.DEBUG(f"[Life]_trigger_record_action: record_id={record.get('id')} action_id={action_id}")
        if not action_id or not isinstance(action_id, str):
            _log.DEBUG(f"[Life]_trigger_record_action: 无动作ID (from {record.get('id', '?')})")
            return
        asys = self._get_action_system()
        if not asys:
            _log.WARN(f"[Life]获取动作系统失败（asys=None）")
            return
        action_record = asys.action_registry.get(action_id)
        if not action_record:
            _log.WARN(f"[Life]动作绑定未注册: {action_id} (from {record.get('id', '?')})")
            return

        _log.INFO(f"[Life]触发绑定动作: {action_id} (from {record.get('id', '?')})")
        asys.trigger_action(action_id)

        # 物品：loop 模式只播放一轮后停止
        if is_item and action_record.play_mode == "loop":
            total_ms = action_record.frame_interval_ms * action_record.frame_count
            if total_ms > 0:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(total_ms, lambda: asys.stop_action(action_id))
                _log.DEBUG(f"[Life]物品 loop 动作将在 {total_ms}ms 后停止: {action_id}")

    def _stop_record_action(self, record: dict) -> None:
        """停止 record 绑定的动作。"""
        action_id = record.get("action_id")
        if not action_id or not isinstance(action_id, str):
            return
        asys = self._get_action_system()
        if asys:
            asys.stop_action(action_id)
            _log.DEBUG(f"[Life]停止绑定动作: {action_id} (from {record.get('id', '?')})")

    def _resync_buff_actions(self) -> None:
        """重新触发所有活跃 buff 的绑定动作（用于显示宠物后恢复动作）。"""
        for effect in self.profile.active_effects:
            record = self.buff_registry.get(effect.effect_id)
            if record and record.get("action_id"):
                self._trigger_record_action(record)
