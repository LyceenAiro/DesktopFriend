from PySide6.QtGui import QPixmap

def ReadPixmap():
    default = QPixmap('resources/PetArt/happy.png').scaled(175, 200)
    pickup = QPixmap('resources/PetArt/awa.png').scaled(175, 200)
    move = QPixmap('resources/PetArt/walk.png').scaled(175, 200)

    return [default, pickup, move]

PetArtList = ReadPixmap()