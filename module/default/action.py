from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap

from module.default.action_schema import validate_action_record
from util.log import _log


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #


@dataclass
class ActionRecord:
    """一个已注册的动作定义。"""
    id: str
    name: str
    desc: str
    frames: list[QPixmap]  # 已解析的帧图像列表
    frame_count: int  # 实际播放帧数
    frame_interval_ms: int  # 帧间隔（毫秒）
    play_mode: str  # "once" | "loop" | "random"
    random_per: float  # 0 < random_per <= 100，仅 random 模式
    block_mode: str  # "exclusive" | "sequence" | "normal"
    animation_sorting: list[int] | None = None  # 帧索引排序
    is_vanilla: bool = False  # 原版动画标记
    source: str = ""  # 来源（vanilla / mod_id / builtin）


@dataclass
class AnimationState:
    """一个正在播放中的动作实例状态。"""
    action_id: str
    current_frame: int = 0
    timer: QTimer | None = None
    started_at: float = 0.0  # time.time()
    random_check_timer: QTimer | None = None


# --------------------------------------------------------------------------- #
# 全局单例
# --------------------------------------------------------------------------- #

_action_system: "ActionSystem | None" = None


def get_action_system() -> "ActionSystem | None":
    return _action_system


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #


def base64_to_pixmap(base64_str: str, width: int = 128, height: int = 128) -> QPixmap:
    """将 base64 字符串解码为 QPixmap。"""
    import base64
    from PySide6.QtCore import QByteArray

    try:
        image_data = base64.b64decode(base64_str)
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(image_data))
        if not pixmap.isNull():
            return pixmap.scaled(width, height)
        return QPixmap(width, height)
    except Exception as e:
        _log.ERROR(f"[Action]base64_to_pixmap 失败: {e}")
        return QPixmap(width, height)


def resolve_resource_reference(ref: str) -> str:
    """解析 @KEY 格式的资源引用，返回对应的 base64 字符串。

    若 ref 不以 '@' 开头，则原样返回（直接是 base64 数据）。
    """
    if not isinstance(ref, str) or not ref.startswith("@"):
        return ref
    key = ref[1:]
    try:
        from resources.image_resources import _RESOURCE_CACHE
        value = _RESOURCE_CACHE.get(key)
        if value is not None:
            return value
    except (ImportError, AttributeError):
        pass
    # 回退：直接从模块全局变量查找
    try:
        import resources.image_resources as res_mod
        value = getattr(res_mod, key, None)
        if value is not None and isinstance(value, str):
            return value
    except ImportError:
        pass
    _log.ERROR(f"[Action]资源包中未找到 key: {key}")
    return ""


# --------------------------------------------------------------------------- #
# ActionSystem 核心
# --------------------------------------------------------------------------- #


class ActionSystem:
    """动作注册表 + 播放管理器。

    管理所有动作的注册、播放控制、优先级处理（exclusive/sequence/normal）。
    初始化时需要传入 DesktopPet 实例以控制 PetArt 显示。
    """

    def __init__(self, pet_window, default_interval_ms: int = 600, set_pixmap_callback: Callable | None = None):
        global _action_system
        _action_system = self

        self._pet = pet_window  # DesktopPet 引用
        self._default_interval_ms = default_interval_ms
        self._set_pixmap_callback = set_pixmap_callback  # 外部 pixmap 设置回调，用于解耦

        # 注册表
        self.action_registry: dict[str, ActionRecord] = {}

        # 播放状态
        self._active_exclusive: str | None = None  # 当前独占动作 ID
        self._sequence_queue: list[str] = []  # 排队的序列动作 ID
        self._active_normal: str | None = None  # 当前普通模式动作 ID
        self._playing: dict[str, AnimationState] = {}  # action_id -> state

        # 原版动画状态（供原版逻辑兼容）
        self._vanilla_idle_active = True
        self._auto_walk_paused = False

        # 用于在外部 set_pixmap 不可用时直接操作 PetArt
        self._can_set_pixmap_directly = pet_window is not None

        _log.INFO(f"[Action]ActionSystem 初始化, default_interval={default_interval_ms}ms")

    # ── 内部 pixmap 设置 ──────────────────────

    def _set_pixmap(self, pixmap: QPixmap) -> None:
        if self._set_pixmap_callback:
            self._set_pixmap_callback(pixmap)
        elif self._can_set_pixmap_directly and self._pet is not None:
            try:
                self._pet.PetArt.setPixmap(pixmap)
            except Exception:
                pass

    # ── 注册 ──────────────────────────────────

    def register_action(self, record: dict, resource_resolver: Callable | None = None) -> bool:
        """从 JSON dict 注册一个动作。返回是否成功。"""
        # 1. schema 校验
        issues = validate_action_record(record)
        errors = [i for i in issues if i.level == "error"]
        if errors:
            _log.ERROR(f"[Action]注册失败 {record.get('id', '?')}: {[e.message for e in errors]}")
            return False

        action_id = record["id"]
        if action_id in self.action_registry:
            _log.WARN(f"[Action]动作ID已存在，覆盖: {action_id}")

        # 2. 解析 image_base64
        resolve = resource_resolver or resolve_resource_reference
        try:
            resolved_images: list[QPixmap] = []
            for img_ref in record["image_base64"]:
                b64_str = resolve(str(img_ref))
                if not b64_str:
                    _log.ERROR(f"[Action]图像引用解析为空: {img_ref}")
                    return False
                pixmap = base64_to_pixmap(b64_str)
                if pixmap.isNull():
                    _log.ERROR(f"[Action]图像解析失败: {img_ref}")
                    return False
                resolved_images.append(pixmap)
        except Exception as e:
            _log.ERROR(f"[Action]image_base64解析失败 {action_id}: {e}")
            return False

        # 3. 构建帧序列
        sorting = record.get("animation_sorting")
        if sorting is not None:
            for idx in sorting:
                if idx >= len(resolved_images):
                    _log.ERROR(f"[Action]animation_sorting索引越界 {action_id}: idx={idx} len={len(resolved_images)}")
                    return False
            frames = [resolved_images[i] for i in sorting]
        else:
            frame_count = int(record.get("frames", 1))
            if frame_count > len(resolved_images):
                _log.ERROR(f"[Action]image_base64数量不足 {action_id}: need={frame_count} have={len(resolved_images)}")
                return False
            frames = resolved_images[:frame_count]

        # 4. 处理 random_per -> loop 的自动转换
        play_mode = str(record.get("play_mode", "once")).strip().lower()
        random_per = float(record.get("random_per", 0))
        if play_mode == "random" and random_per >= 100:
            play_mode = "loop"
            random_per = 0
            _log.INFO(f"[Action]random_per=100，自动转为loop: {action_id}")

        # 5. 构建 ActionRecord
        rec = ActionRecord(
            id=action_id,
            name=str(record.get("name", action_id)),
            desc=str(record.get("desc", "")),
            frames=frames,
            frame_count=len(frames),
            frame_interval_ms=int(record.get("frame_interval_ms", self._default_interval_ms)),
            play_mode=play_mode,
            random_per=random_per,
            block_mode=str(record.get("block_mode", "normal")).strip().lower(),
            animation_sorting=sorting,
            is_vanilla=False,
            source=str(record.get("_source", "builtin")),
        )

        self.action_registry[action_id] = rec
        _log.INFO(f"[Action]注册成功: id={action_id} name={rec.name} mode={play_mode} block={rec.block_mode} frames={len(frames)}")
        return True

    def register_vanilla_action(
        self,
        action_id: str,
        frames: list[QPixmap],
        frame_interval_ms: int,
        play_mode: str,
        block_mode: str = "normal",
    ) -> None:
        """编程式注册原版动画。"""
        rec = ActionRecord(
            id=action_id,
            name=action_id,
            desc="",
            frames=frames,
            frame_count=len(frames),
            frame_interval_ms=frame_interval_ms,
            play_mode=play_mode,
            random_per=0.0,
            block_mode=block_mode,
            is_vanilla=True,
            source="vanilla",
        )
        self.action_registry[action_id] = rec
        _log.INFO(f"[Action]原版动画注册: id={action_id} mode={play_mode} block={block_mode} frames={len(frames)}")

    def unregister_action(self, action_id: str) -> None:
        """移除注册，停止正在播放的该动作。"""
        self.stop_action(action_id)
        self.action_registry.pop(action_id, None)
        _log.INFO(f"[Action]已注销: {action_id}")

    # ── 播放控制 ──────────────────────────────

    def trigger_action(self, action_id: str) -> None:
        """触发一个动作，根据 block_mode 处理优先级。"""
        record = self.action_registry.get(action_id)
        if not record:
            _log.WARN(f"[Action]触发失败，动作未注册: {action_id}")
            return

        _log.INFO(f"[Action]触发: id={action_id} mode={record.play_mode} block={record.block_mode}")

        if record.block_mode == "exclusive":
            self._stop_all_for_exclusive()
            self._start_playing(action_id)
            self._active_exclusive = action_id
            self._pause_auto_walk()
        elif record.block_mode == "sequence":
            if record.play_mode not in ("once", "random"):
                _log.WARN(f"[Action]序列模式仅支持 once/random: {action_id}")
                return
            self._sequence_queue.append(action_id)
            _log.INFO(f"[Action]序列入队: id={action_id} 队列长度={len(self._sequence_queue)}")
            self._pause_auto_walk()
            self._process_sequence_queue()
        else:  # normal
            self._active_normal = action_id
            if self._active_exclusive or self._sequence_queue:
                _log.DEBUG(f"[Action]独占/序列播放中，普通动作暂存: {action_id}")
            else:
                self._stop_normal_if_any()
                self._stop_vanilla_idle()
                self._start_playing(action_id)

    def stop_action(self, action_id: str) -> None:
        """停止一个正在播放的动作。"""
        state = self._playing.pop(action_id, None)
        if state is None:
            return
        _log.DEBUG(f"[Action]停止: {action_id}")

        if state.timer:
            state.timer.stop()
        if state.random_check_timer:
            state.random_check_timer.stop()

        record = self.action_registry.get(action_id)
        if record and record.block_mode == "exclusive" and self._active_exclusive == action_id:
            self._active_exclusive = None
            self._resume_auto_walk()
            self._resume_normal_or_idle()
        elif record and record.block_mode == "normal" and self._active_normal == action_id:
            self._active_normal = None
            self._resume_idle()

    # ── 内部播放逻辑 ──────────────────────────

    def _start_playing(self, action_id: str) -> None:
        """开始播放动作帧动画。"""
        record = self.action_registry.get(action_id)
        if not record:
            return

        state = AnimationState(action_id=action_id, started_at=time.time())

        if record.play_mode == "random":
            state.random_check_timer = QTimer()
            state.random_check_timer.setInterval(1000)
            state.random_check_timer.timeout.connect(lambda: self._random_check(action_id))
            state.random_check_timer.start()
            _log.DEBUG(f"[Action]random模式启动概率检查: {action_id} per={record.random_per}")
            self._playing[action_id] = state
            return

        if len(record.frames) == 1:
            self._set_pixmap(record.frames[0])
            if record.play_mode == "once":
                self._on_once_complete(action_id)
            else:
                self._playing[action_id] = state
            return

        state.timer = QTimer()
        state.timer.setInterval(record.frame_interval_ms)
        state.timer.timeout.connect(lambda: self._advance_frame(action_id))
        state.timer.start()
        self._set_pixmap(record.frames[0])
        self._playing[action_id] = state
        _log.DEBUG(f"[Action]开始播放: {action_id} mode={record.play_mode} frames={len(record.frames)} interval={record.frame_interval_ms}ms")

    def _advance_frame(self, action_id: str) -> None:
        """帧动画前进一步。"""
        state = self._playing.get(action_id)
        record = self.action_registry.get(action_id)
        if not state or not record:
            return

        state.current_frame = (state.current_frame + 1) % len(record.frames)
        self._set_pixmap(record.frames[state.current_frame])

        if record.play_mode == "once" and state.current_frame == 0:
            # 一轮播放完毕
            self._on_once_complete(action_id)
        else:
            _log.DEBUG(f"[Action]帧切换: {action_id} frame={state.current_frame}/{len(record.frames)}")

    def _random_check(self, action_id: str) -> None:
        """random 模式每秒概率检查。"""
        record = self.action_registry.get(action_id)
        if not record:
            return
        rolled = random.random() * 100
        triggered = rolled < record.random_per
        _log.DEBUG(f"[Action]random检查: id={action_id} per={record.random_per} 结果={'触发' if triggered else '未触发'}")
        if triggered:
            state = self._playing.get(action_id)
            if state and state.random_check_timer:
                state.random_check_timer.stop()
            self._start_playing_once_round(action_id)
        else:
            _log.DEBUG(f"[Action]random未触发: {action_id} per={record.random_per}")

    def _start_playing_once_round(self, action_id: str) -> None:
        """播放一轮动画（用于 random 模式触发时）。"""
        record = self.action_registry.get(action_id)
        if not record:
            return

        if len(record.frames) == 1:
            self._set_pixmap(record.frames[0])
            self._on_random_round_complete(action_id)
            return

        state = AnimationState(action_id=action_id, started_at=time.time())
        state.timer = QTimer()
        state.timer.setInterval(record.frame_interval_ms)
        state.timer.timeout.connect(lambda: self._advance_random_round(action_id))
        state.timer.start()
        self._set_pixmap(record.frames[0])
        self._playing[action_id] = state

    def _advance_random_round(self, action_id: str) -> None:
        """random 触发后的单轮动画帧前进。"""
        state = self._playing.get(action_id)
        record = self.action_registry.get(action_id)
        if not state or not record:
            return

        state.current_frame += 1
        if state.current_frame >= len(record.frames):
            self._on_random_round_complete(action_id)
            return

        self._set_pixmap(record.frames[state.current_frame])

    def _on_random_round_complete(self, action_id: str) -> None:
        """random 模式一轮播放完毕，重新启动概率检查。"""
        state = self._playing.pop(action_id, None)
        if state and state.timer:
            state.timer.stop()

        record = self.action_registry.get(action_id)
        if record:
            # 重新启动概率检查
            new_state = AnimationState(action_id=action_id, started_at=time.time())
            new_state.random_check_timer = QTimer()
            new_state.random_check_timer.setInterval(1000)
            new_state.random_check_timer.timeout.connect(lambda: self._random_check(action_id))
            new_state.random_check_timer.start()
            self._playing[action_id] = new_state
            _log.DEBUG(f"[Action]random轮播完毕，重新启动概率检查: {action_id}")

    def _on_once_complete(self, action_id: str) -> None:
        """once 动作播放完毕回调。"""
        state = self._playing.pop(action_id, None)
        if state and state.timer:
            state.timer.stop()

        record = self.action_registry.get(action_id)
        if not record:
            return

        if record.block_mode == "exclusive":
            # 单帧 once+exclusive：保持独占状态直到外部调用 stop_action
            # 适用于 buff 绑定的静态动作（如濒死、死亡）
            if len(record.frames) == 1:
                self._playing[action_id] = AnimationState(action_id=action_id)
                _log.DEBUG(f"[Action]单帧独占动作保持: {action_id}（等待 stop_action 清理）")
                return
            _log.DEBUG(f"[Action]独占动作播放完毕: {action_id}")
            self._active_exclusive = None
            self._resume_auto_walk()
            self._resume_normal_or_idle()
        elif record and record.block_mode == "sequence":
            _log.DEBUG(f"[Action]序列动作播放完毕: {action_id}")
            if self._sequence_queue and self._sequence_queue[0] == action_id:
                self._sequence_queue.pop(0)
            self._process_sequence_queue()
        elif record and record.block_mode == "normal":
            if self._active_normal == action_id:
                self._active_normal = None
            self._resume_idle()

    # ── 序列处理 ──────────────────────────────

    def _process_sequence_queue(self) -> None:
        """处理序列队列中的下一个动作。"""
        if not self._sequence_queue:
            _log.DEBUG("[Action]序列队列为空")
            self._resume_auto_walk()
            self._resume_normal_or_idle()
            return
        next_id = self._sequence_queue[0]
        if next_id not in self._playing:
            self._stop_vanilla_idle()
            self._start_playing(next_id)
            _log.INFO(f"[Action]序列播放: {next_id} 队列剩余={len(self._sequence_queue) - 1}")

    # ── 状态管理 ──────────────────────────────

    def _stop_all_for_exclusive(self) -> None:
        """停止所有正在播放的动作（为独占动作让路）。"""
        for aid in list(self._playing.keys()):
            self.stop_action(aid)
        self._active_exclusive = None
        self._active_normal = None
        self._sequence_queue.clear()
        self._stop_vanilla_idle()

    def _stop_normal_if_any(self) -> None:
        """停止当前 normal 动作。"""
        if self._active_normal and self._active_normal in self._playing:
            self.stop_action(self._active_normal)
        self._active_normal = None

    def _stop_vanilla_idle(self) -> None:
        """暂停原版待机动画。"""
        self._vanilla_idle_active = False

    def _resume_idle(self) -> None:
        """恢复待机动画（若无 normal 动作）。"""
        if self._active_normal and self._active_normal not in self._playing:
            self._start_playing(self._active_normal)
        else:
            self._vanilla_idle_active = True

    def _resume_normal_or_idle(self) -> None:
        """恢复普通模式动作或待机动画。"""
        if self._active_normal and self._active_normal not in self._playing:
            _log.DEBUG(f"[Action]恢复普通动作: {self._active_normal}")
            self._start_playing(self._active_normal)
        else:
            self._resume_idle()

    def _pause_auto_walk(self) -> None:
        """暂停自动行走。"""
        if self._auto_walk_paused:
            return
        self._auto_walk_paused = True
        try:
            from Event.Ai.walk import auto_walk
            auto_walk.is_paused_due_to_action = True
            auto_walk.stop_timer()
            _log.DEBUG("[Action]自动行走已暂停")
        except Exception:
            pass

    def _resume_auto_walk(self) -> None:
        """恢复自动行走。"""
        if not self._auto_walk_paused:
            return
        self._auto_walk_paused = False
        try:
            from Event.Ai.walk import auto_walk
            auto_walk.is_paused_due_to_action = False
            auto_walk.start_timer()
            _log.DEBUG("[Action]自动行走已恢复")
        except Exception:
            pass

    # ── 输入中断协调 ──────────────────────────

    def stop_exclusive_for_input(self) -> str | None:
        """暂停当前独占动作（用于输入中断），返回动作 ID。"""
        aid = self._active_exclusive
        if aid:
            self.stop_action(aid)
        return aid

    def resume_exclusive_from_input(self, action_id: str | None) -> None:
        """恢复因输入中断而暂停的独占动作。"""
        if action_id and action_id in self.action_registry:
            self.trigger_action(action_id)

    def stop_all(self) -> None:
        """停止所有正在播放的动作，清除所有播放状态。"""
        for aid in list(self._playing.keys()):
            state = self._playing.pop(aid, None)
            if state:
                if state.timer:
                    state.timer.stop()
                if state.random_check_timer:
                    state.random_check_timer.stop()
        self._active_exclusive = None
        self._active_normal = None
        self._sequence_queue.clear()
        self._vanilla_idle_active = True
        self._resume_auto_walk()

    # ── 查询 ──────────────────────────────────

    def get_all_action_ids(self) -> list[str]:
        return sorted(self.action_registry.keys())

    def is_action_playing(self, action_id: str) -> bool:
        return action_id in self._playing

    def has_exclusive_or_sequence(self) -> bool:
        """是否有独占或序列动作正在播放。"""
        return self._active_exclusive is not None or bool(self._sequence_queue)

    # ── 批量注册 ──────────────────────────────

    def load_actions_from_json(self, json_path: str, source: str = "builtin") -> int:
        """从 JSON 文件加载并注册动作。返回成功注册数。"""
        import json
        from pathlib import Path

        path = Path(json_path)
        if not path.exists():
            _log.WARN(f"[Action]动作JSON文件不存在: {json_path}")
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            _log.ERROR(f"[Action]读取JSON失败 {json_path}: {e}")
            return 0

        if not isinstance(data, list):
            _log.ERROR(f"[Action]JSON格式错误，需要列表: {json_path}")
            return 0

        success_count = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            item["_source"] = source
            if self.register_action(item):
                success_count += 1

        _log.INFO(f"[Action]从 {json_path} 加载动作: {success_count}/{len(data)}")
        return success_count

    def scan_action_directory(self, directory: str, source: str = "builtin") -> int:
        """扫描目录下所有 JSON 文件并注册动作。返回成功注册总数。"""
        from pathlib import Path

        dir_path = Path(directory)
        if not dir_path.is_dir():
            return 0

        total = 0
        for json_file in sorted(dir_path.glob("*.json")):
            total += self.load_actions_from_json(str(json_file), source=source)
        return total
