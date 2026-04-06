import sys
from ui.PetWindow import PetWindow, app
from register import registerInit
from PySide6.QtCore import QTimer
from Event.setting.system import ShowApp

from warnings import filterwarnings
filterwarnings("ignore", category=DeprecationWarning)


if __name__ == "__main__":
    registerInit()
    QTimer.singleShot(0, lambda: ShowApp(PetWindow))
    sys.exit(app.exec())