from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from util.log import _log


class DefaultModRegistry:
    """Default 模组（动作/资源包）的发现、校验与加载。

    管理 mod 目录下所有具有 action/ 或 resources/ 子目录的模组。
    """

    def __init__(self, mod_root: str | Path = "mod", protocol_version: str = "0.3"):
        self.mod_root = Path(mod_root)
        self.protocol_version = protocol_version
        self._loaded_mods: dict[str, dict] = {}
        self._event_log: list[dict] = []

    # ── 发现 ──────────────────────────────────

    def discover(self) -> list[Path]:
        """扫描 mod_root/ 下所有子目录，返回按名称排序的路径列表。"""
        if not self.mod_root.is_dir():
            _log.WARN(f"[DefaultMod]mod 目录不存在: {self.mod_root}")
            return []
        dirs = sorted(
            [d for d in self.mod_root.iterdir() if d.is_dir() and not d.name.startswith(".")],
            key=lambda d: d.name,
        )
        _log.DEBUG(f"[DefaultMod]发现 {len(dirs)} 个 mod 目录")
        return dirs

    # ── 加载 pack_info ────────────────────────

    def load_pack_info(self, mod_dir: Path) -> dict | None:
        """读取 mod 目录下的 pack_info.json。"""
        pack_path = mod_dir / "pack_info.json"
        if not pack_path.exists():
            return None
        try:
            with open(pack_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                _log.WARN(f"[DefaultMod]pack_info.json 格式错误: {pack_path}")
                return None
            return data
        except Exception as e:
            _log.WARN(f"[DefaultMod]读取 pack_info.json 失败 {pack_path}: {e}")
            return None

    # ── 校验 ──────────────────────────────────

    def validate(self, packs: dict[str, dict]) -> dict[str, list[str]]:
        """校验所有 mod 的 pack_info，返回 {mod_id: [错误信息]}。"""
        errors: dict[str, list[str]] = {}

        for mod_id, pack in packs.items():
            mod_errors: list[str] = []

            # 检查 id 字段
            pack_id = str(pack.get("id", "")).strip()
            if not pack_id:
                mod_errors.append("pack_info.json 缺少 id 字段")
            elif pack_id != mod_id:
                mod_errors.append(f"目录名 '{mod_id}' 与 id '{pack_id}' 不匹配")

            # 检查 requires_resource_pack
            required_pack = pack.get("requires_resource_pack")
            if required_pack:
                try:
                    from resources.image_resources import get_resource_pack_name
                    current_pack = get_resource_pack_name()
                    if current_pack != required_pack and not current_pack.endswith(required_pack):
                        mod_errors.append(f"需要资源包 '{required_pack}'，当前为 '{current_pack}'")
                except Exception:
                    mod_errors.append(f"需要资源包 '{required_pack}'，但无法获取当前资源包名称")

            if mod_errors:
                errors[mod_id] = mod_errors

        return errors

    # ── 解析加载顺序 ──────────────────────────

    def resolve_load_order(self, packs: dict) -> list[str]:
        """返回按 requires 拓扑排序的 mod ID 列表。"""
        graph: dict[str, set[str]] = {}
        for mod_id, pack in packs.items():
            requires = {str(d).strip() for d in pack.get("requires", []) if str(d).strip()}
            graph[mod_id] = requires & set(packs.keys())

        order: list[str] = []
        visited: set[str] = set()
        temp: set[str] = set()

        def _visit(mid: str) -> None:
            if mid in temp:
                _log.WARN(f"[DefaultMod]检测到循环依赖: {mid}")
                return
            if mid in visited:
                return
            temp.add(mid)
            for dep in graph.get(mid, set()):
                _visit(dep)
            temp.discard(mid)
            visited.add(mid)
            order.append(mid)

        for mod_id in graph:
            if mod_id not in visited:
                _visit(mod_id)

        _log.INFO(f"[DefaultMod]加载顺序: {order}")
        return order

    # ── 加载 ──────────────────────────────────

    def execute_with_builtin_loader(self, action_system) -> dict:
        """加载所有 default 模组。

        扫描每个 mod 的 action/ 和 resources/ 子目录，向 ActionSystem 注册。

        Args:
            action_system: ActionSystem 实例

        Returns:
            dict: {"loaded": [mod_id, ...], "issues": {mod_id: [error, ...]}}
        """
        mod_dirs = self.discover()

        # 加载 pack_info
        packs: dict[str, dict] = {}
        pack_map: dict[str, Path] = {}
        for mod_dir in mod_dirs:
            pack = self.load_pack_info(mod_dir)
            if pack is not None:
                mid = str(pack.get("id", mod_dir.name)).strip()
                packs[mid] = pack
                pack_map[mid] = mod_dir
            else:
                # 没有 pack_info 但有 action/ 或 resources/ 目录也可以加载
                has_action = (mod_dir / "action").is_dir()
                has_resources = (mod_dir / "resources").is_dir()
                if has_action or has_resources:
                    mid = mod_dir.name
                    packs[mid] = {"id": mid, "name": mid, "requires": []}
                    pack_map[mid] = mod_dir

        # 校验
        errors = self.validate(packs)
        valid_packs = {mid: pack for mid, pack in packs.items() if mid not in errors}

        # 解析加载顺序
        load_order = self.resolve_load_order(valid_packs)

        # 执行加载
        issues: dict[str, list[str]] = {}
        loaded: list[str] = []
        loaded_ids: set[str] = set()

        for mod_id in load_order:
            mod_dir = pack_map[mod_id]
            mod_issues: list[str] = []

            # 先加载 resources/
            resources_dir = mod_dir / "resources"
            if resources_dir.is_dir():
                try:
                    count = self._load_mod_resources(resources_dir, mod_id)
                    if count > 0:
                        _log.INFO(f"[DefaultMod]{mod_id} 加载了 {count} 个资源")
                except Exception as e:
                    mod_issues.append(f"资源加载失败: {e}")

            # 加载 action/
            action_dir = mod_dir / "action"
            if action_dir.is_dir():
                try:
                    count = action_system.scan_action_directory(str(action_dir), source=mod_id)
                    if count > 0:
                        _log.INFO(f"[DefaultMod]{mod_id} 注册了 {count} 个动作")
                except Exception as e:
                    mod_issues.append(f"动作加载失败: {e}")

            if mod_issues:
                issues[mod_id] = mod_issues
            else:
                loaded.append(mod_id)
                loaded_ids.add(mod_id)

        return {
            "loaded": loaded,
            "issues": issues,
        }

    # ── 资源加载 ──────────────────────────────

    def _load_mod_resources(self, resources_dir: Path, mod_id: str) -> int:
        """加载 mod 的 resources/ 目录中的 JSON 文件。

        将资源 key-value 对注入到 image_resources 模块的缓存中。

        Returns:
            成功注入的键数量
        """
        count = 0
        for json_file in sorted(resources_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    _log.WARN(f"[DefaultMod]{mod_id} resources 文件非字典格式: {json_file.name}")
                    continue

                from resources import image_resources as res_mod
                for key, value in data.items():
                    if isinstance(key, str) and isinstance(value, str):
                        setattr(res_mod, key, value)
                        res_mod._RESOURCE_CACHE[key] = value
                        count += 1

                _log.DEBUG(f"[DefaultMod]{mod_id} 资源文件 {json_file.name}: 注入 {len(data)} 个键")
            except Exception as e:
                _log.WARN(f"[DefaultMod]{mod_id} 资源加载失败 {json_file.name}: {e}")

        return count

    def get_loaded_mod_ids(self) -> list[str]:
        return list(self._loaded_mods.keys())
