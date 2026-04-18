import ctypes
import sys

from ui.PetArt import PetArtList, DEFAULT, NONE_ART
from util.log import _log
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import QIcon, QMovie, QPixmap, Qt
from PySide6.QtCore import QBuffer, QTimer, QByteArray

from ui.PetWindow import DesktopPet
from Event.input.move import move_jump
from resources.image_resources import HIDE_GIF

def AppStayTop(self: DesktopPet, check):
    if check.isChecked():
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
    else:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
    self.show()

def QuitApp(self: DesktopPet, app):
    # 退出程序
    if not self.isVisible():
        _log.INFO("退出桌宠")
        app.exit()
        return
    # 中断任何正在进行的移动动作
    if hasattr(self, 'jump_timer') and self.jump_timer:
        self.jump_timer.stop()
    self.move_count = 0
    from Event.input.move import _walk
    _walk.stop()
    _play_hide_animation(self, lambda: _exit_app(self, app))


def _exit_app(self: DesktopPet, app):
    _log.INFO("退出桌宠")
    self.AutoMove = False  # 退出时彻底关闭AutoMove
    self.hide()
    app.exit()


def HideApp(self: DesktopPet):
    # 隐藏程序
    _log.INFO("隐藏桌宠")
    self.auto_walk_on_show = self.AutoMove  # 记住隐藏前的状态
    self.AutoMove = False
    self.move_count = 0
    self.origin_x = 0
    from module.life.runtime import enter_hibernation
    enter_hibernation("hidden")
    _play_hide_animation(self)


def _create_movie_from_base64(data: str):
    data_bytes = QByteArray.fromBase64(data.encode('utf-8'))
    buffer = QBuffer()
    buffer.setData(data_bytes)
    buffer.open(QBuffer.ReadOnly)

    movie = QMovie(buffer)
    movie._buffer = buffer
    return movie

def TrayIconActivated(reason, self: DesktopPet):
    if reason == QSystemTrayIcon.DoubleClick:
        # 双击触发
        if self.isVisible():
            _bring_pet_to_front(self)
            _log.INFO("触发桌宠已经显示")
            move_jump(self)
            QTimer.singleShot(250, lambda: move_jump(self))
            from Event.Ai.walk import auto_walk
            auto_walk.reset_idle()
            return
        ShowApp(self)
        _bring_pet_to_front(self)


def _bring_pet_to_front(self: DesktopPet):
    """将窗口临时提到最前，避免取消置顶后被其他窗口遮挡。"""
    was_stay_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
    self.raise_()
    self.activateWindow()
    if was_stay_top or sys.platform != "win32":
        return

    # Windows 下使用原生 API 短暂提到最前，避免切换 Qt flag 造成闪烁。
    hwnd = int(self.winId())
    user32 = ctypes.windll.user32
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW

    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
    self.raise_()
    self.activateWindow()

def ShowApp(self: DesktopPet):
    if self.isVisible():
        return
    self.PetArt.setPixmap(PetArtList[NONE_ART])
    self.show()
    self.activateWindow()
    _log.INFO("显示桌宠触发")
    from module.life.runtime import leave_hibernation
    leave_hibernation("hidden")

    from Event.Ai.walk import auto_walk
    auto_walk.stop_timer()
    auto_walk.reset_idle()

    _play_show_animation(self, lambda: _on_show_finished(self))


def _create_icon_from_base64(base64_data):
    data_bytes = QByteArray.fromBase64(base64_data.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(data_bytes)
    return QIcon(pixmap)


def _play_hide_animation(self: DesktopPet, on_finished=None):
    self.stop_default_action_timer()
    self.PetArt.setPixmap(PetArtList[NONE_ART])
    self.movie = _create_movie_from_base64(HIDE_GIF)
    self.movie.setCacheMode(QMovie.CacheAll)
    if on_finished:
        self.movie.frameChanged.connect(lambda frame_number: _on_hide_frame_changed(self, frame_number, on_finished))
    else:
        self.movie.frameChanged.connect(lambda frame_number: _on_hide_frame_changed(self, frame_number))
    self.PetArt.setMovie(self.movie)
    self.movie.start()


def _on_hide_frame_changed(self: DesktopPet, frame_number: int, on_finished=None):
    frame_count = self.movie.frameCount()
    if frame_count > 0 and frame_number == frame_count - 1:
        self.movie.stop()
        if on_finished:
            on_finished()
        else:
            self.hide()


def _on_show_finished(self: DesktopPet):
    self.AutoMove = self.auto_walk_on_show
    from Event.Ai.walk import auto_walk
    auto_walk.start_timer()
    self.start_default_action_timer()


def _play_show_animation(self: DesktopPet, on_finished=None):
    self.stop_default_action_timer()
    self.PetArt.setPixmap(PetArtList[NONE_ART])
    movie = _create_movie_from_base64(HIDE_GIF)
    movie.setCacheMode(QMovie.CacheAll)
    movie.start()

    def start_reverse():
        frame_count = movie.frameCount()
        if frame_count <= 0:
            self.PetArt.setPixmap(PetArtList[DEFAULT])
            if on_finished:
                on_finished()
            return

        timer = QTimer(self)
        current = frame_count - 1

        def step():
            nonlocal current
            if current < 0:
                timer.stop()
                self.PetArt.setPixmap(PetArtList[DEFAULT])
                if on_finished:
                    on_finished()
                return
            movie.jumpToFrame(current)
            self.PetArt.setPixmap(movie.currentPixmap())
            current -= 1

        timer.timeout.connect(step)
        timer.start(100)
        step()

    if movie.frameCount() > 0:
        start_reverse()
    else:
        def on_load(frame_number):
            if movie.frameCount() > 0:
                movie.frameChanged.disconnect(on_load)
                start_reverse()

        movie.frameChanged.connect(on_load)