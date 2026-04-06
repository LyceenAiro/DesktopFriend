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
    _play_hide_animation(self, lambda: _exit_app(self, app))


def _exit_app(self: DesktopPet, app):
    _log.INFO("退出桌宠")
    self.hide()
    app.exit()


def HideApp(self: DesktopPet):
    # 隐藏程序
    _log.INFO("隐藏桌宠")
    _play_hide_animation(self)


def _create_movie_from_base64(data: str):
    data_bytes = QByteArray.fromBase64(data.encode('utf-8'))
    buffer = QBuffer()
    buffer.setData(data_bytes)
    buffer.open(QBuffer.ReadOnly)

    movie = QMovie(buffer)
    movie._buffer = buffer
    return movie


def _create_icon_from_base64(base64_data):
    data_bytes = QByteArray.fromBase64(base64_data.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(data_bytes)
    return QIcon(pixmap)


def _play_hide_animation(self: DesktopPet, on_finished=None):
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

def TrayIconActivated(reason, self: DesktopPet):
    if reason == QSystemTrayIcon.DoubleClick:
        # 双击触发
        if self.isVisible():
            _log.INFO("触发桌宠已经显示")
            move_jump(self)
            QTimer.singleShot(250, lambda: move_jump(self))
            return
        ShowApp(self)


def ShowApp(self: DesktopPet):
    if self.isVisible():
        return
    self.PetArt.setPixmap(PetArtList[NONE_ART])
    self.show()
    self.activateWindow()
    _log.INFO("显示桌宠触发")
    _play_show_animation(self)


def _play_show_animation(self: DesktopPet):
    self.PetArt.setPixmap(PetArtList[NONE_ART])
    movie = _create_movie_from_base64(HIDE_GIF)
    movie.setCacheMode(QMovie.CacheAll)
    movie.start()

    def start_reverse():
        frame_count = movie.frameCount()
        if frame_count <= 0:
            self.PetArt.setPixmap(PetArtList[DEFAULT])
            return

        timer = QTimer(self)
        current = frame_count - 1

        def step():
            nonlocal current
            if current < 0:
                timer.stop()
                self.PetArt.setPixmap(PetArtList[DEFAULT])
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