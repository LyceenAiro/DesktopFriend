import random
from PySide6.QtCore import QTimer

from ui.PetWindow import PetWindow
from util.log import _log
from Event.input.move import move_left, move_right, move_jump

class AutoWalk:
    def __init__(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        # 检查时间
        self.check_time = 5000
        self.timer.start(self.check_time)
        # 开关控制
        self.is_paused_due_to_action = False  # 因为正在执行动作而暂停
        self.idle_time = 0
        self.idle_threshold = 60
        # 动作几率
        self._walk_left_per = 2
        self._walk_right_per = 2
        self._jump_per = 5
        _log.INFO("Register AutoWalk success")

    def stop_timer(self):
        """停止定时器"""
        self.timer.stop()
        _log.INFO("[AI]AutoWalk timer stopped")

    def start_timer(self):
        """启动定时器"""
        self.timer.stop()  # 先停止
        self.timer.start()  # 再启动
        _log.INFO(f"[AI]AutoWalk timer started, active: {self.timer.isActive()}")

    def reset_idle(self):
        """重置空闲时间"""
        self.idle_time = 0
        _log.INFO("[AI]Idle time reset")

    def _on_timer(self):
        self.idle_time += self.check_time / 1000.0
        if PetWindow.AutoMove and not self.is_paused_due_to_action and not PetWindow.is_follow_mouse and self.idle_time > self.idle_threshold:
            self._perform_random_action()
        else:
            _log.INFO(
                f"[AI]AutoWalk is disabled or paused. AutoMove: {PetWindow.AutoMove}, "
                f"Paused: {self.is_paused_due_to_action}, FollowMouse: {PetWindow.is_follow_mouse}, Idle: {self.idle_time:.1f}s"
            )

    def _can_move_left(self, move_count) -> bool:
        if PetWindow.x() - 2 < 0:
            return False
        if PetWindow.origin_x - move_count < PetWindow.max_move_range * -1:
            return False
        return True

    def _can_move_right(self, move_count) -> bool:
        if PetWindow.x() + 2 >= PetWindow.screen_max_x:
            return False
        if PetWindow.origin_x + move_count > PetWindow.max_move_range:
            return False
        return True

    def _perform_random_action(self):
        # 检查几率总和是否超过100%
        total_per = self._walk_left_per + self._walk_right_per + self._jump_per
        if total_per > 100:
            raise ValueError(f"动作几率总和超过100%: 左移={self._walk_left_per}, 右移={self._walk_right_per}, 跳跃={self._jump_per}, 总和={total_per}")
        # 设置暂停状态，防止重复触发
        self.is_paused_due_to_action = True
        # 停止定时器
        self.stop_timer()

        # 计算动作几率
        per_start = 0
        left_rand_ok = per_start + self._walk_left_per
        right_rand_ok = left_rand_ok + self._walk_right_per
        jump_rand_ok = right_rand_ok + self._jump_per
        # 随机选择动作
        walk_count = self._rand_walk()
        left_ok = self._can_move_left(walk_count)
        right_ok = self._can_move_right(walk_count)
        rand = random.randint(1, 100)
        _log.INFO(f"[AI]AutoWalk code {rand}, left_ok={left_ok}, right_ok={right_ok}")

        if rand <= left_rand_ok:
            if left_ok:
                PetWindow.move_count = walk_count
                move_left(PetWindow)
            elif right_ok:
                PetWindow.move_count = walk_count
                move_right(PetWindow)
            else:
                self._no_action()
        elif rand <= right_rand_ok:
            if right_ok:
                PetWindow.move_count = walk_count
                move_right(PetWindow)
            elif left_ok:
                PetWindow.move_count = walk_count
                move_left(PetWindow)
            else:
                self._no_action()
        elif rand <= jump_rand_ok:
            move_jump(PetWindow)
        else:
            self._no_action()

    def _rand_walk(self):
        rand = random.randint(2, 10)
        _log.INFO(f"[AI]Random walk count: {rand}")
        return rand

    def _no_action(self):
        self.is_paused_due_to_action = False
        self.start_timer()

# 创建全局实例
auto_walk = AutoWalk()