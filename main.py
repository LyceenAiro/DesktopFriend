import sys
from ui.PetWindow import PetWindow, app
from register import registerInit



from warnings import filterwarnings
filterwarnings("ignore", category=DeprecationWarning)


if __name__ == "__main__":
    registerInit()
    PetWindow.show()
    sys.exit(app.exec())