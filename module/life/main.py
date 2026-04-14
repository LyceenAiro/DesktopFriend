from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from util.log import _log
from util.i18n import tr
from module.life.schema import (
    ValidationIssue,
    validate_buff_record,
    validate_item_record,
    validate_event_trigger_record,
    validate_event_outcome_record,
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
    managed: bool = False  # 由外部（如营养系统）管理生命周期，不倒计时也不自动移除
    nutrition_per_tick: dict[str, float] = field(default_factory=dict)  # 每 tick 额外消耗的营养值（正值=减少）


@dataclass
class LifeProfile:
    states: dict[str, float] = field(default_factory=dict)
    state_max: dict[str, float] = field(default_factory=dict)
    state_min: dict[str, float] = field(default_factory=dict)
    nutrition: dict[str, float] = field(default_factory=dict)
    attrs: dict[str, float] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    active_effects: list[LifeEffect] = field(default_factory=list)


class LifeSystem:
    """0.3 draft implementation for life architecture.

    - Passive json registration for buff and item.
    - Runtime states/attrs with tick updates.
    - SQLite profile save/load.
    """

    def __init__(
        self,
        buff_dir: str | Path = "module/life/buff",
        item_dir: str | Path = "module/life/item",
        status_dir: str | Path = "module/life/status",
        nutrition_dir: str | Path = "module/life/nutrition",
        event_trigger_dir: str | Path = "module/life/event_trigger",
        event_outcome_dir: str | Path = "module/life/event_outcome",
        store: LifeSqliteStore | None = None,
    ):
        self.buff_dir = Path(buff_dir)
        self.item_dir = Path(item_dir)
        self.status_dir = Path(status_dir)
        self.nutrition_dir = Path(nutrition_dir)
        self.event_trigger_dir = Path(event_trigger_dir)
        self.event_outcome_dir = Path(event_outcome_dir)
        self.extra_buff_dirs: list[Path] = []
        self.extra_item_dirs: list[Path] = []
        self.extra_status_dirs: list[Path] = []
        self.extra_nutrition_dirs: list[Path] = []
        self.extra_event_trigger_dirs: list[Path] = []
        self.extra_event_outcome_dirs: list[Path] = []
        self.store = store or LifeSqliteStore()
        self.character_name: str = ""  # 角色名称（由外部注入，如资源包 PACK_NAME）
        self.paused: bool = False  # 暂停时 tick 和物品使用均被冻结

        self.buff_registry: dict[str, dict[str, Any]] = {}
        self.item_registry: dict[str, dict[str, Any]] = {}
        self.event_trigger_registry: dict[str, dict[str, Any]] = {}
        self.event_outcome_registry: dict[str, dict[str, Any]] = {}
        self.attribute_rules: dict[str, list[dict[str, Any]]] = {}
        self.validation_issues: list[ValidationIssue] = []
        self._static_cap_modifiers: list[tuple[str, str, Any]] = []
        self._item_cooldowns: dict[str, float] = {}  # item_id → 可用时间戳 (time.time())
        self._trigger_cooldowns: dict[str, float] = {}  # trigger_id → 可用时间戳
        self._trigger_executing: dict[str, float] = {}  # trigger_id → 完成时间戳 (正在执行中)
        self._completed_trigger_results: list[dict[str, Any]] = []  # 执行完成事件队列（供 UI 消费）

        self.state_definitions: dict[str, dict[str, Any]] = self._load_state_definitions()
        self.nutrition_definitions: dict[str, dict[str, Any]] = self._load_nutrition_definitions()

        self._attr_cap_bonus_max: dict[str, float] = {k: 0.0 for k in self.state_keys}
        self._attr_cap_bonus_min: dict[str, float] = {k: 0.0 for k in self.state_keys}
        self._state_runtime_breakdown: dict[str, dict[str, float]] = {}

        self.profile = self._create_default_profile()
        self.reload_registries()

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

    def get_state_definitions(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.state_definitions.values()]

    def get_nutrition_definitions(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.nutrition_definitions.values()]

    def _create_default_profile(self) -> LifeProfile:
        states = {key: float(defn["default"]) for key, defn in self.state_definitions.items()}
        state_max = {key: float(defn["max"]) for key, defn in self.state_definitions.items()}
        state_min = {key: float(defn["min"]) for key, defn in self.state_definitions.items()}
        nutrition = {key: float(defn["default"]) for key, defn in self.nutrition_definitions.items()}
        attrs = {k: 10.0 for k in BASE_ATTRS}
        inventory = self._load_starter_inventory()
        return LifeProfile(states=states, state_max=state_max, state_min=state_min, nutrition=nutrition, attrs=attrs, inventory=inventory)

    def _load_starter_inventory(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item_root in self._iter_item_dirs():
            for starter_file in sorted(item_root.rglob("starter_inventory.json")):
                try:
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
                    _log.WARNING(f"[Life] Failed to load starter_inventory.json from {starter_file}: {exc}")
        return result

    def reload_registries(self) -> None:
        next_state_defs = self._load_state_definitions()
        next_nutrition_defs = self._load_nutrition_definitions()
        self._sync_profile_states(next_state_defs)
        self._sync_profile_nutrition(next_nutrition_defs)

        self.buff_registry, buff_issues = self._load_registry_dir(
            self._iter_buff_dirs(),
            "buff",
            state_keys=self.state_keys,
            attr_keys=BASE_ATTRS,
            nutrition_keys=self.nutrition_keys,
        )
        self.item_registry, item_issues = self._load_item_registry(
            self._iter_item_dirs(),
            state_keys=self.state_keys,
            attr_keys=BASE_ATTRS,
            nutrition_keys=self.nutrition_keys,
        )
        self.event_trigger_registry, trigger_issues = self._load_event_registry(
            self._iter_event_trigger_dirs(), "event_trigger"
        )
        self.event_outcome_registry, outcome_issues = self._load_event_registry(
            self._iter_event_outcome_dirs(), "event_outcome"
        )
        self.validation_issues = buff_issues + item_issues + trigger_issues + outcome_issues
        self.attribute_rules = self._load_attribute_rules(self.buff_registry)
        self._refresh_attr_range_effects()
        self._sync_managed_nutrition_buffs()
        self._report_validation_issues()
        _log.INFO(
            "[Life]注册完成 "
            f"status={len(self.state_definitions)} nutrition={len(self.nutrition_definitions)} "
            f"buff={len(self.buff_registry)} item={len(self.item_registry)} "
            f"trigger={len(self.event_trigger_registry)} outcome={len(self.event_outcome_registry)}"
        )

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

    def attach_mod_resource_dirs(
        self,
        *,
        status_dir: str | Path | None = None,
        buff_dir: str | Path | None = None,
        item_dir: str | Path | None = None,
        nutrition_dir: str | Path | None = None,
        event_trigger_dir: str | Path | None = None,
        event_outcome_dir: str | Path | None = None,
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

    def _load_state_definitions(self) -> dict[str, dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for directory in self._iter_status_dirs():
            if not directory.exists():
                continue
            for file_path in sorted(directory.rglob("*.json")):
                payload = self._read_json(file_path)
                if isinstance(payload, dict) and "id" in payload:
                    loaded.append(payload)
                elif isinstance(payload, list):
                    loaded.extend([r for r in payload if isinstance(r, dict)])

        if not loaded:
            return self._build_default_state_definitions()

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

            normalized.append(
                {
                    "id": state_id,
                    "name": name,
                    "i18n_key": i18n_key,
                    "default": default_value,
                    "min": min_value,
                    "max": max_value,
                    "order": order,
                }
            )

        if not normalized:
            return self._build_default_state_definitions()

        normalized.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("id", ""))))
        result: dict[str, dict[str, Any]] = {}
        for item in normalized:
            result[str(item["id"])] = item
        return result

    def _load_nutrition_definitions(self) -> dict[str, dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for directory in self._iter_nutrition_dirs():
            if not directory.exists():
                continue
            for file_path in sorted(directory.rglob("*.json")):
                payload = self._read_json(file_path)
                if isinstance(payload, dict) and "id" in payload:
                    loaded.append(payload)
                elif isinstance(payload, list):
                    loaded.extend([r for r in payload if isinstance(r, dict)])

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
                        "states": dict(states) if isinstance(states, dict) else {},
                        "attrs": dict(attrs) if isinstance(attrs, dict) else {},
                    }
                    if buff_id is not None:
                        entry["buff_id"] = str(buff_id)
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
        for item in normalized:
            result[str(item["id"])] = item
        return result

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
            _log.INFO("[Life]schema校验通过")
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

        _log.INFO(f"[Life]schema校验完成 error={error_count} warn={warn_count}")

    def _load_attribute_rules(self, buff_registry: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        rules: dict[str, list[dict[str, Any]]] = {}
        for record in buff_registry.values():
            attr_name = str(record.get("attribute", "")).strip()
            status_rules = record.get("status")
            if attr_name not in BASE_ATTRS or not isinstance(status_rules, list):
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
        for directory in directories:
            if not directory.exists():
                continue

            for file_path in sorted(directory.rglob("*.json")):
                if file_path.name == "class.json":
                    continue
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
                    result[record_id] = record

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
        for root in roots:
            if not root.exists():
                continue

            for file_path in sorted(root.rglob("*.json")):
                if file_path.name in ("starter_inventory.json", "class.json"):
                    continue
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
                            registry[item_id] = item

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
        validate_fn = validate_event_trigger_record if kind == "event_trigger" else validate_event_outcome_record
        for directory in directories:
            if not directory.exists():
                continue
            for file_path in sorted(directory.rglob("*.json")):
                if file_path.name == "class.json":
                    continue
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
                    registry[record_id] = record
        return registry, issues

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

        return True

    def add_item(self, item_id: str, count: int = 1) -> bool:
        if item_id not in self.item_registry:
            _log.WARN(f"[Life]不能加入未知物品: {item_id}")
            return False
        delta = max(1, int(count))
        self.profile.inventory[item_id] = self.profile.inventory.get(item_id, 0) + delta
        return True

    def set_item_count(self, item_id: str, count: int) -> bool:
        if item_id not in self.item_registry:
            _log.WARN(f"[Life]不能设置未知物品数量: {item_id}")
            return False
        normalized = max(0, int(count))
        if normalized == 0:
            self.profile.inventory.pop(item_id, None)
            return True
        self.profile.inventory[item_id] = normalized
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

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        current = self.profile.inventory.get(item_id, 0)
        delta = max(1, int(count))
        if current < delta:
            return False
        left = current - delta
        if left <= 0:
            self.profile.inventory.pop(item_id, None)
        else:
            self.profile.inventory[item_id] = left
        return True

    def get_inventory_snapshot(self) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for item_id, count in sorted(self.profile.inventory.items()):
            item_info = self.item_registry.get(item_id, {})
            cooldown_remaining = self.get_item_cooldown_remaining(item_id)
            snapshot.append(
                {
                    "id": item_id,
                    "name": self._resolve_record_name(item_info, item_id),
                    "category": item_info.get("category", "unknown"),
                    "classes": list(item_info.get("_classes", [])),
                    "desc": self._resolve_record_desc(item_info),
                    "usable": bool(item_info.get("usable", True)),
                    "count": int(count),
                    "cooldown_remaining": cooldown_remaining,
                    "on_cooldown": cooldown_remaining > 0,
                }
            )
        return snapshot

    def can_use_item(self, item_id: str) -> bool:
        item = self.item_registry.get(item_id)
        if not item:
            return False
        if not bool(item.get("usable", True)):
            return False
        ready_at = self._item_cooldowns.get(item_id)
        if ready_at is not None and time.time() < ready_at:
            return False
        return True

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

        for attr_id in BASE_ATTRS:
            if attr_id in item:
                summary["instant_attrs"].append(
                    {
                        "id": attr_id,
                        "i18n_key": f"life.attr.{attr_id}",
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
            "raw": dict(buff),
        }

    def apply_buff(self, buff_id: str, duration_override: int | None = None) -> bool:
        buff = self.buff_registry.get(buff_id)
        if not buff:
            _log.WARN(f"[Life]未知buff: {buff_id}")
            return False

        self._apply_record(buff, source="buff", duration_override=duration_override)
        return True

    def list_buff_ids(self) -> list[str]:
        return sorted(self.buff_registry.keys())

    def list_active_effect_ids(self) -> list[str]:
        return [e.effect_id for e in self.profile.active_effects]

    def clear_effect(self, effect_id: str) -> bool:
        before = len(self.profile.active_effects)
        self.profile.active_effects = [e for e in self.profile.active_effects if e.effect_id != effect_id]
        return len(self.profile.active_effects) < before

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

        for attr in BASE_ATTRS:
            if attr in record:
                self.profile.attrs[attr] = self.profile.attrs.get(attr, 0.0) + float(record[attr])

        # Instant state effects.
        for state in self.state_keys:
            if state in record:
                self._change_state(state, float(record[state]))

        self._apply_nutrition_record(record)

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
            if per_tick or cap_modifiers or nutrition_per_tick:
                duration_ticks = max(1, int(duration_override))
            elif duration_ticks > 0:
                duration_ticks = max(1, int(duration_override))

        if (per_tick or cap_modifiers or nutrition_per_tick) and duration_ticks > 0:
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
                )
            )
        elif cap_modifiers:
            self._apply_cap_modifiers(cap_modifiers)

        self._refresh_attr_range_effects()

        _log.INFO(f"[Life]应用{source}: {record_id}")

    def _extract_cap_modifiers(self, record: dict[str, Any]) -> list[tuple[str, str, Any]]:
        modifiers: list[tuple[str, str, Any]] = []
        for key, value in record.items():
            if key.endswith("_max2"):
                base = key[:-5]
                if base in self.state_keys:
                    modifiers.append(("max2", base, value))
            elif key.endswith("_max"):
                base = key[:-4]
                if base in self.state_keys:
                    modifiers.append(("max", base, value))
            elif key.endswith("_min"):
                base = key[:-4]
                if base in self.state_keys:
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

        self.profile.active_effects = next_effects
        self._tick_nutrition()
        self.tick_triggers()
        self._refresh_attr_range_effects()

    def _refresh_attr_range_effects(self) -> None:
        max_caps = {
            state: float(self.state_definitions.get(state, {}).get("max", GLOBAL_VALUE_MAX)) for state in self.state_keys
        }
        min_caps = {state: float(self.state_definitions.get(state, {}).get("min", 0.0)) for state in self.state_keys}

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

        tick_deltas = self._collect_state_tick_deltas()
        for state, delta in tick_deltas.items():
            if state in breakdown:
                breakdown[state]["tick_delta"] = float(delta)
        self._state_runtime_breakdown = breakdown

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

        self._sync_managed_nutrition_buffs()

    def _sync_managed_nutrition_buffs(self) -> None:
        """根据当前营养值同步 managed buff 的激活/移除状态。
        在 tick 时和 reload_registries 后均需调用，确保初始状态正确。
        """
        if not self.nutrition_definitions:
            return

        for nutrition_key, definition in self.nutrition_definitions.items():
            current = float(self.profile.nutrition.get(nutrition_key, definition.get("default", 0.0)))
            source_tag = f"nutrition:{nutrition_key}"

            for effect_def in definition.get("effects", []):
                min_v = float(effect_def.get("min", float("-inf")))
                max_v = float(effect_def.get("max", float("inf")))
                in_range = min_v <= current < max_v
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
                            self._apply_managed_buff(buff_record, source=source_tag)
                    elif not in_range and existing is not None:
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
            managed=True,
            nutrition_per_tick=nutrition_per_tick,
        )
        self.profile.active_effects.append(effect)
        _log.INFO(f"[Life]激活持续Buff: {record_id} (来源: {source})")

    def _change_nutrition(self, nutrition_key: str, delta: float) -> None:
        if nutrition_key not in self.profile.nutrition:
            return
        self.profile.nutrition[nutrition_key] += delta
        self._clamp_nutrition(nutrition_key)

    def _clamp_nutrition(self, nutrition_key: str) -> None:
        definition = self.nutrition_definitions.get(nutrition_key)
        if not definition:
            return
        lo = float(definition.get("min", 0.0))
        hi = float(definition.get("max", 100.0))
        self.profile.nutrition[nutrition_key] = max(lo, min(hi, self.profile.nutrition[nutrition_key]))

    def get_nutrition_snapshot(self) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for nutrition_key, definition in self.nutrition_definitions.items():
            nutrition_name = tr(
                str(definition.get("i18n_key") or f"life.nutrition.{nutrition_key}"),
                default=str(definition.get("name") or nutrition_key),
            )
            snapshot.append(
                {
                    "id": nutrition_key,
                    "name": nutrition_name,
                    "value": float(self.profile.nutrition.get(nutrition_key, definition.get("default", 0.0))),
                    "min": float(definition.get("min", 0.0)),
                    "max": float(definition.get("max", 100.0)),
                    "decay": float(definition.get("decay", 0.0)),
                }
            )
        return snapshot

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
        if self.paused:
            return False, "paused"
        # 正在执行中
        if trigger_id in self._trigger_executing:
            finish_at = self._trigger_executing[trigger_id]
            if time.time() < finish_at:
                return False, "executing"
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
        return True, ""

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

        # 执行时间：duration_s > 0 时先进入执行状态，延迟产出结果
        duration_s = trigger.get("duration_s")
        has_duration = False
        if duration_s is not None:
            try:
                dur = float(duration_s)
                if dur > 0:
                    self._trigger_executing[trigger_id] = time.time() + dur
                    has_duration = True
                    _log.INFO(f"[Life][Event]开始执行: {trigger_id} 耗时={dur}s")
            except Exception:
                pass

        if has_duration:
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

        _log.INFO(f"[Life][Event]完成触发: {trigger_id} 结果数={len(result_log)}")
        return {
            "trigger_id": trigger_id,
            "trigger_name": trigger_name,
            "pending": False,
            "results": result_log,
        }

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
        return completed

    def pop_completed_trigger_results(self) -> list[dict[str, Any]]:
        """取出并清空执行完成事件队列。"""
        if not self._completed_trigger_results:
            return []
        payload = list(self._completed_trigger_results)
        self._completed_trigger_results.clear()
        return payload

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
                result_log.append({"type": "item", "id": item_id, "count": count})
        # 必定给予 buff
        for buff_entry in guaranteed.get("buffs", []):
            buff_id = str(buff_entry).strip() if not isinstance(buff_entry, dict) else str(buff_entry.get("id") or "").strip()
            if buff_id and self.apply_buff(buff_id):
                result_log.append({"type": "buff", "id": buff_id})
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
            self._roll_random_pool(entries, result_log, depth=0)

    def _roll_random_pool(self, entries: list[dict[str, Any]], result_log: list[dict[str, Any]], depth: int) -> None:
        if depth > 10:
            _log.WARN("[Life][Event]事件链深度超过10，中止")
            return
        total_chance = sum(float(e.get("chance", 0)) for e in entries if isinstance(e, dict))
        if total_chance <= 0:
            return

        # 超额机制
        if total_chance > 300:
            divisor = 4
            draws = 4
        elif total_chance > 100:
            divisor = 2
            draws = 2
        else:
            divisor = 1
            draws = 1

        for _ in range(draws):
            roll = random.random() * 100.0
            cumulative = 0.0
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                chance = float(entry.get("chance", 0)) / divisor
                cumulative += chance
                if roll < cumulative:
                    self._apply_pool_entry(entry, result_log, depth)
                    break

    def _apply_pool_entry(self, entry: dict[str, Any], result_log: list[dict[str, Any]], depth: int) -> None:
        entry_type = str(entry.get("type") or "").strip().lower()
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            return

        if entry_type == "item":
            count = max(1, int(entry.get("count", 1)))
            if self.add_item(entry_id, count):
                result_log.append({"type": "item", "id": entry_id, "count": count})
        elif entry_type == "buff":
            if self.apply_buff(entry_id):
                result_log.append({"type": "buff", "id": entry_id})
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

        # 应用 outcome 的直接效果（即时状态变化）
        effects = outcome.get("effects")
        if isinstance(effects, dict):
            for key, value in effects.items():
                if key in self.state_keys:
                    try:
                        self._change_state(key, float(value))
                    except Exception:
                        pass

        self._execute_event_guaranteed(outcome, result_log)

        pools = outcome.get("random_pools")
        if isinstance(pools, list):
            for pool in pools:
                if not isinstance(pool, dict):
                    continue
                entries = pool.get("entries")
                if isinstance(entries, list) and entries:
                    self._roll_random_pool(entries, result_log, depth=depth + 1)

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
                "classes": list(trigger.get("_classes", [])),
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
                    "remaining_ticks": e.remaining_ticks,
                    "stack_rule": e.stack_rule,
                    "cap_modifiers": e.cap_modifiers,
                }
                for e in self.profile.active_effects
            ],
        }

    def load_profile(self, data: dict[str, Any]) -> None:
        self.profile.states.update(data.get("states", {}))
        raw_nutrition = data.get("nutrition", {})
        if isinstance(raw_nutrition, dict):
            for key, value in raw_nutrition.items():
                if str(key) not in self.profile.nutrition:
                    continue
                self.profile.nutrition[str(key)] = self._to_float_safe(value, self.profile.nutrition[str(key)])
        self.profile.attrs.update(data.get("attrs", {}))
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
                    remaining_ticks=int(raw.get("remaining_ticks", 0)),
                    stack_rule=str(raw.get("stack_rule", "add")),
                    cap_modifiers=[
                        (str(entry[0]), str(entry[1]), entry[2])
                        for entry in list(raw.get("cap_modifiers", []))
                        if isinstance(entry, (list, tuple)) and len(entry) == 3
                    ],
                )
            )

        for state in self.state_keys:
            self._clamp_state(state)
        for nutrition_key in self.nutrition_keys:
            self._clamp_nutrition(nutrition_key)
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
        for trigger_id, remaining in data.get("trigger_executing", {}).items():
            try:
                r = float(remaining)
            except Exception:
                continue
            if r > 0:
                self._trigger_executing[str(trigger_id)] = now + r

    def reset_profile(self) -> None:
        """清除所有当前养成数据，恢复到默认初始状态并保存存档。"""
        self._static_cap_modifiers.clear()
        self._attr_cap_bonus_max = {k: 0.0 for k in self.state_keys}
        self._attr_cap_bonus_min = {k: 0.0 for k in self.state_keys}
        self._item_cooldowns.clear()
        self._trigger_cooldowns.clear()
        self._trigger_executing.clear()
        self._completed_trigger_results.clear()
        self.profile = self._create_default_profile()
        self._sync_managed_nutrition_buffs()
        self.save("default")
        _log.INFO("[Life]养成数据已重置")

    def save(self, profile_id: str = "default") -> None:
        self.store.save_profile(profile_id, self.dump_profile())

    def load(self, profile_id: str = "default") -> bool:
        payload = self.store.load_profile(profile_id)
        if payload is None:
            return False
        self.load_profile(payload)
        return True
