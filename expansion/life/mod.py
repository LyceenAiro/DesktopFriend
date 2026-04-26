from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from util.i18n import attach_lang_dir, detach_lang_dir
from util.log import _log


_HOOK_SKIP = object()


def _parse_version_tuple(version_text: str) -> tuple[int, ...] | None:
    text = str(version_text or "").strip()
    if not text:
        return None
    parts = text.split(".")
    parsed: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        parsed.append(int(part))
    return tuple(parsed)


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    l = left + (0,) * (width - len(left))
    r = right + (0,) * (width - len(right))
    if l < r:
        return -1
    if l > r:
        return 1
    return 0


def _check_constraint(version_text: str, constraint_text: str) -> bool | None:
    version = _parse_version_tuple(version_text)
    if version is None:
        return None

    raw = str(constraint_text or "").strip()
    if not raw:
        return None

    operator = "=="
    target_text = raw
    for prefix in (">=", "<=", "==", ">", "<"):
        if raw.startswith(prefix):
            operator = prefix
            target_text = raw[len(prefix) :].strip()
            break

    target = _parse_version_tuple(target_text)
    if target is None:
        return None

    cmp_result = _compare_versions(version, target)
    if operator == ">=":
        return cmp_result >= 0
    if operator == "<=":
        return cmp_result <= 0
    if operator == ">":
        return cmp_result > 0
    if operator == "<":
        return cmp_result < 0
    return cmp_result == 0


def _safe_read_json(file_path: Path) -> dict[str, Any] | None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class LifeModRegistry:
    """Life-mod discovery + metadata validation."""

    def __init__(self, mod_root: str | Path = "mod", protocol_version: str = "0.3"):
        self.mod_root = Path(mod_root)
        self.protocol_version = str(protocol_version).strip() or "0.3"
        self._loaded_mods: dict[str, dict[str, Any]] = {}
        self._event_log: list[dict[str, str]] = []
        self._resource_hooks: dict[str, dict[str, Any]] = {}
        self._actually_removed_ids: dict[str, dict[str, list[str]]] = {}

    def discover(self) -> list[Path]:
        if not self.mod_root.exists():
            _log.DEBUG(f"[Mod]mod目录不存在: {self.mod_root}")
            return []
        dirs = sorted([p for p in self.mod_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
        _log.INFO(f"[Mod]扫描到 {len(dirs)} 个 mod 目录: {[d.name for d in dirs]}")
        return dirs

    def load_pack_info(self, mod_dir: Path) -> dict[str, Any] | None:
        pack = _safe_read_json(mod_dir / "pack_info.json")
        if pack is None:
            _log.WARN(f"[Mod]{mod_dir.name}: pack_info.json 缺失或格式错误")
        else:
            _log.DEBUG(f"[Mod]{mod_dir.name}: id={pack.get('id')}, version={pack.get('version')}")
        return pack

    def _collect_mods(
        self,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, Path], dict[str, list[str]]]:
        issues: dict[str, list[str]] = {}
        info_map: dict[str, dict[str, Any]] = {}
        source_map: dict[str, str] = {}
        path_map: dict[str, Path] = {}

        for mod_dir in self.discover():
            pack = self.load_pack_info(mod_dir)
            if not pack:
                issues[mod_dir.name] = ["pack_info.json 缺失或格式错误"]
                continue

            mod_id = str(pack.get("id") or mod_dir.name).strip()
            if mod_id in info_map:
                issues.setdefault(mod_dir.name, []).append(f"重复mod id: {mod_id}")
                prev = source_map.get(mod_id)
                if prev:
                    issues.setdefault(prev, []).append(f"重复mod id: {mod_id}")
                continue

            info_map[mod_id] = pack
            source_map[mod_id] = mod_dir.name
            path_map[mod_id] = mod_dir

        return info_map, source_map, path_map, issues

    def validate(self, _pre_collected=None) -> dict[str, list[str]]:
        if _pre_collected is not None:
            info_map, _, _, issues = _pre_collected
        else:
            info_map, _, _, issues = self._collect_mods()
        ids = set(info_map.keys())
        protocol_version = _parse_version_tuple(self.protocol_version)

        for mod_id, pack in info_map.items():
            errors: list[str] = []
            requires = pack.get("requires", [])
            conflicts = pack.get("conflicts", [])
            requires_versions = pack.get("requires_versions", {})
            min_protocol = str(pack.get("min_protocol", "")).strip()
            max_protocol = str(pack.get("max_protocol", "")).strip()

            if protocol_version is None:
                errors.append("当前协议版本非法")
            else:
                if min_protocol:
                    check_min = _check_constraint(self.protocol_version, f">={min_protocol}")
                    if check_min is None:
                        errors.append("min_protocol 版本格式非法")
                    elif not check_min:
                        errors.append(f"协议版本过低: 需要 >= {min_protocol}")
                if max_protocol:
                    check_max = _check_constraint(self.protocol_version, f"<={max_protocol}")
                    if check_max is None:
                        errors.append("max_protocol 版本格式非法")
                    elif not check_max:
                        errors.append(f"协议版本过高: 需要 <= {max_protocol}")

            if not isinstance(requires, list):
                errors.append("requires 必须是列表")
            else:
                for dep in requires:
                    dep_id = str(dep).strip()
                    if dep_id and dep_id not in ids:
                        errors.append(f"缺少前置mod: {dep_id}")

            if not isinstance(conflicts, list):
                errors.append("conflicts 必须是列表")
            else:
                for conf in conflicts:
                    conf_id = str(conf).strip()
                    if conf_id and conf_id in ids:
                        errors.append(f"存在冲突mod: {conf_id}")

            if not isinstance(requires_versions, dict):
                errors.append("requires_versions 必须是字典")
            else:
                for dep_id_raw, rule_raw in requires_versions.items():
                    dep_id = str(dep_id_raw).strip()
                    rule = str(rule_raw).strip()
                    if not dep_id or not rule:
                        errors.append("requires_versions 包含空依赖或空约束")
                        continue

                    dep_pack = info_map.get(dep_id)
                    if dep_pack is None:
                        errors.append(f"requires_versions 引用了未安装依赖: {dep_id}")
                        continue

                    dep_version = str(dep_pack.get("version", "")).strip()
                    check_result = _check_constraint(dep_version, rule)
                    if check_result is None:
                        errors.append(f"依赖版本约束非法: {dep_id} {rule}")
                    elif not check_result:
                        errors.append(f"依赖版本不满足: {dep_id} 需要 {rule}，实际 {dep_version or 'unknown'}")

            if errors:
                issues[mod_id] = errors

        if issues:
            for mid, errs in issues.items():
                for err in errs:
                    _log.WARN(f"[Mod]校验问题: {mid}: {err}")
        else:
            _log.DEBUG(f"[Mod]校验通过，共 {len(info_map)} 个 mod")

        return issues

    def _read_user_order(self) -> tuple[list[str], set[str]]:
        """读取 load_order.json 中用户自定义的 mod 顺序和禁用列表。

        Returns:
            (order, disabled_mods) 其中 order 为加载顺序，disabled_mods 为禁用的 mod id 集合。
        """
        order_file = self.mod_root / "load_order.json"
        try:
            if order_file.exists():
                data = json.loads(order_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    raw = data.get("order", [])
                    if isinstance(raw, list):
                        order = [str(x).strip() for x in raw if str(x).strip()]
                    disabled_raw = data.get("disabled_mods", [])
                    if isinstance(disabled_raw, list):
                        disabled = {str(x).strip() for x in disabled_raw if str(x).strip()}
                    else:
                        disabled = set()
                    return order, disabled
        except Exception:
            pass
        return [], set()

    def resolve_load_order(self) -> tuple[list[str], dict[str, list[str]]]:
        """Return deterministic mod load order and issues.

        Mods with validation issues (bad pack_info, protocol mismatch, etc.)
        are skipped immediately. Mods whose dependencies are not yet met are
        NOT skipped here — they are included in the order and deferred to
        execute_load_plan() for retry-based dependency resolution.

        Intentionally disabled mods (from load_order.json) are also skipped.

        Returns:
            (order, issues) where order contains only loadable mod candidates
            and issues shows mods that were directly skipped (validation fail,
            disabled). Dependency failures are handled at load time.
        """

        issues = self.validate()
        info_map, _, _, _ = self._collect_mods()

        # 读取用户自定义的禁用列表，将其加入 skip_set
        _, disabled_mods = self._read_user_order()
        # 清除已不存在的 mod 的禁用记录，避免误计入 log
        stale = disabled_mods - info_map.keys()
        if stale:
            disabled_mods -= stale
            _log.DEBUG(f"[Mod]清理 load_order.json 中已移除 mod 的禁用记录: {sorted(stale)}")
            try:
                order_file = self.mod_root / "load_order.json"
                if order_file.exists():
                    data = json.loads(order_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        raw_disabled = data.get("disabled_mods", [])
                        if isinstance(raw_disabled, list):
                            data["disabled_mods"] = [x for x in raw_disabled if str(x).strip() not in stale]
                            order_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        skip_set: set[str] = set(issues.keys()) | disabled_mods

        # Log skipped mods. Intentionally disabled mods are logged at INFO level.
        for mod_id in skip_set:
            if mod_id in disabled_mods and mod_id not in issues:
                _log.INFO(f"[Mod]跳过 {mod_id}: 已禁用")
                continue
            for reason in issues.get(mod_id, ["未知原因"]):
                _log.WARN(f"[Mod]跳过 {mod_id}: {reason}")

        valid_info = {mod_id: pack for mod_id, pack in info_map.items() if mod_id not in skip_set}

        if not valid_info:
            return [], issues

        # 读取用户自定义顺序，用于同层节点的 tie-breaking
        user_order, _ = self._read_user_order()
        _max_pos = len(user_order)

        def _sort_key(mod_id: str) -> tuple[int, str]:
            try:
                pos = user_order.index(mod_id)
            except ValueError:
                pos = _max_pos  # 未在 load_order.json 中列出的排到最后
            return (pos, mod_id)

        requires_map: dict[str, set[str]] = {}
        dependents_map: dict[str, set[str]] = {mod_id: set() for mod_id in valid_info}

        for mod_id, pack in valid_info.items():
            requires = pack.get("requires", [])
            requires_set = {str(dep).strip() for dep in requires if str(dep).strip() and str(dep).strip() in valid_info}
            requires_map[mod_id] = requires_set
            for dep in requires_set:
                if dep in dependents_map:
                    dependents_map[dep].add(mod_id)

        in_degree: dict[str, int] = {mod_id: len(reqs) for mod_id, reqs in requires_map.items()}
        queue = sorted([mod_id for mod_id, deg in in_degree.items() if deg == 0], key=_sort_key)
        order: list[str] = []

        while queue:
            current = queue.pop(0)
            order.append(current)
            for dep_mod in sorted(dependents_map.get(current, set()), key=_sort_key):
                in_degree[dep_mod] -= 1
                if in_degree[dep_mod] == 0:
                    queue.append(dep_mod)
            queue.sort(key=_sort_key)

        if len(order) != len(valid_info):
            cycle_nodes = sorted([mod_id for mod_id, deg in in_degree.items() if deg > 0])
            for mod_id in cycle_nodes:
                reason = "检测到依赖环，无法加载"
                issues.setdefault(mod_id, []).append(reason)
                _log.WARN(f"[Mod]跳过 {mod_id}: {reason}")
            order = [mod_id for mod_id in order if mod_id not in set(cycle_nodes)]

        if order:
            _log.INFO(f"[Mod]计划加载 {len(order)} 个 mod: {order}")

        return order, issues

    def build_load_plan(self) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, list[str]]]:
        """Build a deterministic load plan as (mod_id, pack_info) tuples.

        Issues only contain skipped mods and are informational; a non-empty
        issues dict does NOT mean the plan itself failed.
        """
        order, issues = self.resolve_load_order()
        info_map, _, _, _ = self._collect_mods()
        plan = [(mod_id, info_map[mod_id]) for mod_id in order if mod_id in info_map]
        return plan, issues

    def get_loaded_mod_ids(self) -> list[str]:
        return list(self._loaded_mods.keys())

    def get_event_log(self) -> list[dict[str, str]]:
        return list(self._event_log)

    def register_resource_hook(self, name: str, attach_callback, detach_callback) -> None:
        self._resource_hooks[str(name)] = {
            "attach": attach_callback,
            "detach": detach_callback,
        }

    def register_life_nutrition_hook(self, life_system) -> None:
        def _attach(mod_id: str, pack: dict[str, Any], mod_dir: Path | None):
            if mod_dir is None:
                return _HOOK_SKIP
            nutrition_dir = mod_dir / "nutrition"
            if not nutrition_dir.exists():
                return _HOOK_SKIP
            life_system.attach_mod_resource_dirs(nutrition_dir=nutrition_dir, reload=True)
            return {"nutrition_dir": nutrition_dir}

        def _detach(mod_id: str, pack: dict[str, Any], state: dict[str, Any] | None):
            if not state:
                return None
            nutrition_dir = state.get("nutrition_dir")
            if nutrition_dir is None:
                return None
            life_system.detach_mod_resource_dirs(nutrition_dir=nutrition_dir, reload=True)
            return None

        self.register_resource_hook("life_nutrition", _attach, _detach)

    def unregister_resource_hook(self, name: str) -> bool:
        key = str(name)
        if key not in self._resource_hooks:
            return False
        self._resource_hooks.pop(key, None)
        return True

    def _append_event(
        self,
        action: str,
        mod_id: str,
        status: str,
        message: str = "",
        event_log_path: str | Path | None = None,
    ) -> None:
        event = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": str(action),
            "mod_id": str(mod_id),
            "status": str(status),
            "message": str(message),
        }
        self._event_log.append(event)

        if event_log_path is None:
            return

        log_path = Path(event_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _get_mod_resource_dirs(self, mod_dir: Path) -> dict[str, Path]:
        result: dict[str, Path] = {}
        status_dir = mod_dir / "status"
        buff_dir = mod_dir / "buff"
        item_dir = mod_dir / "item"
        nutrition_dir = mod_dir / "nutrition"
        lang_dir = mod_dir / "lang"
        event_trigger_dir = mod_dir / "event_trigger"
        event_outcome_dir = mod_dir / "event_outcome"
        passive_buff_dir = mod_dir / "passive_buff"
        attr_dir = mod_dir / "attrs"
        if status_dir.exists():
            result["status_dir"] = status_dir
        if buff_dir.exists():
            result["buff_dir"] = buff_dir
        if item_dir.exists():
            result["item_dir"] = item_dir
        if nutrition_dir.exists():
            result["nutrition_dir"] = nutrition_dir
        if lang_dir.exists():
            result["lang_dir"] = lang_dir
        if event_trigger_dir.exists():
            result["event_trigger_dir"] = event_trigger_dir
        if event_outcome_dir.exists():
            result["event_outcome_dir"] = event_outcome_dir
        if passive_buff_dir.exists():
            result["passive_buff_dir"] = passive_buff_dir
        if attr_dir.exists():
            result["attr_dir"] = attr_dir
        level_dir = mod_dir / "level"
        if level_dir.exists():
            result["level_dir"] = level_dir
        tag_dir = mod_dir / "tags"
        if tag_dir.exists():
            result["tag_dir"] = tag_dir
        return result

    def execute_with_builtin_loader(
        self,
        event_log_path: str | Path | None = None,
        life_system=None,
    ) -> dict[str, Any]:
        """Execute load plan with builtin callbacks for integration prototyping.

        This method provides a real transaction flow without coupling to external resource
        loaders yet. It supports test-only simulation flags in pack_info:
        - simulate_load_fail: bool
        - simulate_rollback_fail: bool
        """

        self._event_log.clear()
        _, _, path_map, _ = self._collect_mods()
        loaded_resource_dirs: dict[str, dict[str, Path]] = {}
        loaded_hook_states: dict[str, dict[str, Any]] = {}
        loaded_remove_ids: dict[str, dict[str, list[str]]] = {}

        # Registry snapshot helpers for per-mod diff logging
        _REGISTRY_NAMES = (
            "state_definitions", "nutrition_definitions", "attr_definitions",
            "buff_registry", "item_registry", "event_trigger_registry",
            "event_outcome_registry", "passive_buff_registry", "tag_registry",
        )

        def _snapshot(ls):
            if ls is None:
                return {}
            return {name: dict(getattr(ls, name, {})) for name in _REGISTRY_NAMES}

        def _diff(before, after):
            added, removed, modified = {}, {}, {}
            for key in before:
                b_reg, a_reg = before.get(key, {}), after.get(key, {})
                b_ids, a_ids = set(b_reg.keys()), set(a_reg.keys())
                new_ids = a_ids - b_ids
                if new_ids:
                    added[key] = sorted(new_ids)
                gone_ids = b_ids - a_ids
                if gone_ids:
                    removed[key] = sorted(gone_ids)
                common = b_ids & a_ids
                changed = [i for i in common if json.dumps(b_reg[i], sort_keys=True) != json.dumps(a_reg[i], sort_keys=True)]
                if changed:
                    modified[key] = sorted(changed)
            return added, removed, modified

        def _fmt_diff(added, removed, modified):
            parts = []
            if added:
                items = " ".join(f"{k}:{len(v)} {v}" for k, v in added.items())
                parts.append("新增 " + items)
            if modified:
                items = " ".join(f"{k}:{len(v)} {v}" for k, v in modified.items())
                parts.append("修改 " + items)
            if removed:
                items = " ".join(f"{k}:{len(v)} {v}" for k, v in removed.items())
                parts.append("删除 " + items)
            return " | ".join(parts)

        def _builtin_load(mod_id: str, pack: dict[str, Any]) -> bool:
            _log.DEBUG(f"[Mod]开始加载: {mod_id}")
            if bool(pack.get("simulate_load_fail", False)):
                self._append_event("load", mod_id, "failed", "simulate_load_fail", event_log_path)
                _log.WARN(f"[Mod]{mod_id}: 模拟加载失败")
                return False

            resource_dirs = self._get_mod_resource_dirs(path_map[mod_id]) if mod_id in path_map else {}
            if resource_dirs:
                loaded_resource_dirs[mod_id] = resource_dirs
            if life_system is not None and resource_dirs:
                life_resource_dirs = {
                    k: v
                    for k, v in resource_dirs.items()
                    if k in {"status_dir", "buff_dir", "item_dir", "nutrition_dir", "event_trigger_dir", "event_outcome_dir", "passive_buff_dir", "attr_dir", "level_dir", "tag_dir"}
                }
                if life_resource_dirs:
                    life_system.attach_mod_resource_dirs(reload=False, **life_resource_dirs)

            # remove_ids 收集
            remove_ids = pack.get("remove_ids")
            if life_system is not None and isinstance(remove_ids, dict):
                loaded_remove_ids[mod_id] = remove_ids
                life_system.add_remove_ids(remove_ids)

            # Snapshot registries before reload for per-mod diff
            _before = _snapshot(life_system) if life_system is not None else {}

            if life_system is not None:
                life_system.reload_registries()

            # Diff registries to find added/modified/removed IDs
            _after = _snapshot(life_system) if life_system is not None else {}
            _added, _removed, _modified = _diff(_before, _after)

            # Track actually-removed IDs (map diff keys to remove_ids-style keys)
            _REMOVED_KEY_MAP = {
                "buff_registry": "buff", "item_registry": "item",
                "event_trigger_registry": "event_trigger", "event_outcome_registry": "event_outcome",
                "passive_buff_registry": "passive_buff",
                "state_definitions": "status", "nutrition_definitions": "nutrition",
                "attr_definitions": "attrs", "tag_registry": "tag",
            }
            _actual_removed: dict[str, list[str]] = {}
            for _diff_key, _ids in _removed.items():
                _mapped = _REMOVED_KEY_MAP.get(_diff_key)
                if _mapped and _ids:
                    _actual_removed[_mapped] = _ids
            self._actually_removed_ids[mod_id] = _actual_removed
            if "lang_dir" in resource_dirs:
                attach_lang_dir(resource_dirs["lang_dir"])

            mod_dir = path_map[mod_id] if mod_id in path_map else None
            for hook_name, hook in self._resource_hooks.items():
                try:
                    hook_state = hook["attach"](mod_id, pack, mod_dir)
                except Exception as exc:
                    self._append_event("hook", mod_id, "failed", f"{hook_name}: {exc}", event_log_path)
                    return False
                if hook_state is _HOOK_SKIP:
                    continue
                loaded_hook_states.setdefault(mod_id, {})[hook_name] = hook_state
                self._append_event("hook", mod_id, "ok", hook_name, event_log_path)

            self._loaded_mods[mod_id] = dict(pack)
            self._append_event("load", mod_id, "ok", "", event_log_path)
            diff_text = _fmt_diff(_added, _removed, _modified)
            if diff_text:
                _log.INFO(f"[Mod]加载成功: {mod_id} (v{pack.get('version', '?')}) | {diff_text}")
            else:
                _log.INFO(f"[Mod]加载成功: {mod_id} (v{pack.get('version', '?')}) 资源={list(resource_dirs.keys())} | 无变更")
            return True

        def _builtin_rollback(mod_id: str, pack: dict[str, Any]) -> bool:
            if bool(pack.get("simulate_rollback_fail", False)):
                self._append_event("rollback", mod_id, "failed", "simulate_rollback_fail", event_log_path)
                return False

            resource_dirs = loaded_resource_dirs.get(mod_id, {})
            if life_system is not None and resource_dirs:
                life_resource_dirs = {
                    k: v
                    for k, v in resource_dirs.items()
                    if k in {"status_dir", "buff_dir", "item_dir", "nutrition_dir", "event_trigger_dir", "event_outcome_dir", "passive_buff_dir", "attr_dir", "level_dir", "tag_dir"}
                }
                if life_resource_dirs:
                    life_system.detach_mod_resource_dirs(reload=False, **life_resource_dirs)

            # 回滚 remove_ids
            if life_system is not None and mod_id in loaded_remove_ids:
                loaded_remove_ids.pop(mod_id, None)
                life_system.clear_remove_ids()
                # 重新累积剩余 mod 的 remove_ids
                for remaining_rid in loaded_remove_ids.values():
                    life_system.add_remove_ids(remaining_rid)

            if life_system is not None:
                life_system.reload_registries()
            if "lang_dir" in resource_dirs:
                detach_lang_dir(resource_dirs["lang_dir"])

            hook_states = loaded_hook_states.get(mod_id, {})
            for hook_name, hook in reversed(list(self._resource_hooks.items())):
                if hook_name not in hook_states:
                    continue
                try:
                    hook["detach"](mod_id, pack, hook_states[hook_name])
                    self._append_event("hook_rollback", mod_id, "ok", hook_name, event_log_path)
                except Exception as exc:
                    self._append_event("hook_rollback", mod_id, "failed", f"{hook_name}: {exc}", event_log_path)
                    return False

            loaded_hook_states.pop(mod_id, None)
            loaded_resource_dirs.pop(mod_id, None)
            self._loaded_mods.pop(mod_id, None)
            self._append_event("rollback", mod_id, "ok", "", event_log_path)
            _log.INFO(f"[Mod]回滚成功: {mod_id}")
            return True

        result = self.execute_load_plan(load_callback=_builtin_load, rollback_callback=_builtin_rollback)
        # With the new defer/retry algorithm, execute_load_plan always returns
        # ok=True. Individual load failures are in result["issues"]. We avoid
        # transactional rollback — each mod stands or falls independently.
        abandoned = [m for m in result.get("issues", {}) if "前置mod未满足" in " ".join(result["issues"].get(m, []))]
        if abandoned:
            _log.WARN(f"[Mod]以下 mod 因前置mod未满足被放弃: {abandoned}")
        return result

    def execute_load_plan(
        self,
        load_callback,
        rollback_callback,
    ) -> dict[str, Any]:
        """Execute load plan with graceful dependency resolution.

        Unlike the old transactional approach, this method:
        1. Loads mods in topological order
        2. If a mod's dependencies aren't loaded yet, defers it to a pending queue
        3. After each successful load, retries all pending mods
        4. After the main queue is exhausted, retries pending in rounds
        5. If no progress after retry rounds, abandons remaining pending mods

        Args:
            load_callback: callable(mod_id: str, pack_info: dict) -> bool
            rollback_callback: unused in this algorithm (no transactional rollback)

        Returns:
            {
                "ok": bool,  # always True — individual failures are in issues
                "loaded": list[str],
                "rolled_back": [],
                "issues": dict[str, list[str]],
            }
        """

        plan, issues = self.build_load_plan()
        if not plan:
            if issues:
                _log.WARN(f"[Mod]没有可加载的 mod（{len(issues)} 个 mod 已跳过）")
            return {"ok": True, "loaded": [], "rolled_back": [], "issues": issues}

        result_issues: dict[str, list[str]] = dict(issues)
        loaded_ids: set[str] = set()
        loaded: list[tuple[str, dict[str, Any]]] = []
        pending: list[tuple[str, dict[str, Any]]] = []

        def _deps_satisfied(mod_id: str, pack: dict[str, Any]) -> bool:
            requires = {str(dep).strip() for dep in pack.get("requires", []) if str(dep).strip()}
            return requires <= loaded_ids

        def _try_load(mod_id: str, pack: dict[str, Any]) -> bool:
            try:
                return bool(load_callback(mod_id, pack))
            except Exception as exc:
                result_issues.setdefault(mod_id, []).append(f"加载异常: {exc}")
                return False

        def _retry_pending() -> bool:
            progress = False
            if pending:
                _log.INFO(f"[Mod]重试待加载队列 ({len(pending)} 个)...")
            i = 0
            while i < len(pending):
                mod_id, pack = pending[i]
                if _deps_satisfied(mod_id, pack):
                    if _try_load(mod_id, pack):
                        loaded_ids.add(mod_id)
                        loaded.append((mod_id, pack))
                        pending.pop(i)
                        _log.INFO(f"[Mod]重试成功: {mod_id}")
                        progress = True
                        continue  # re-check remaining pending from same index
                    else:
                        # Actual load failure — don't retry
                        if mod_id not in result_issues:
                            result_issues.setdefault(mod_id, []).append("加载失败")
                        pending.pop(i)
                        continue
                i += 1
            return progress

        # Phase 1: Main queue
        for mod_id, pack in plan:
            if _deps_satisfied(mod_id, pack):
                if _try_load(mod_id, pack):
                    loaded_ids.add(mod_id)
                    loaded.append((mod_id, pack))
                    # Retry pending after each successful load
                    _retry_pending()
                else:
                    # Actual load failure
                    if mod_id not in result_issues:
                        result_issues.setdefault(mod_id, []).append("加载失败")
            else:
                # Defer to pending
                requires = {str(dep).strip() for dep in pack.get("requires", []) if str(dep).strip()}
                missing = sorted(requires - loaded_ids)
                _log.INFO(f"[Mod]延迟加载: {mod_id} (前置 {missing} 未就绪)")
                pending.append((mod_id, pack))

        # Phase 2: Retry rounds
        while pending:
            progress = _retry_pending()
            if not progress:
                break

        # Phase 3: Abandon remaining
        for mod_id, pack in pending:
            requires = {str(dep).strip() for dep in pack.get("requires", []) if str(dep).strip()}
            missing = requires - loaded_ids
            reason = f"前置mod未满足: {', '.join(sorted(missing))}"
            result_issues.setdefault(mod_id, []).append(reason)
            _log.WARN(f"[Mod]放弃 {mod_id}: {reason}")

        if loaded:
            _log.INFO(f"[Mod]加载完成，共 {len(loaded)} 个 mod: {[m for m, _ in loaded]}")
        abandoned = len(pending)
        if abandoned:
            _log.WARN(f"[Mod]放弃加载 {abandoned} 个 mod（前置mod不存在或未加载）")

        return {
            "ok": True,
            "loaded": [mod for mod, _ in loaded],
            "rolled_back": [],
            "issues": result_issues,
        }
