# from PySide6.QtGui import QPixmap, QTransform

# def ReadPixmap(pack_name='default'):
#     default = QPixmap(f'resources/PetArt/{pack_name}/default.png').scaled(128, 128)
#     default2 = QPixmap(f'resources/PetArt/{pack_name}/default2.png').scaled(128, 128)
#     jump = QPixmap(f'resources/PetArt/{pack_name}/jump.png').scaled(128, 128)
#     pickup = QPixmap(f'resources/PetArt/{pack_name}/pickup.png').scaled(128, 128)
#     walk = QPixmap(f'resources/PetArt/{pack_name}/walk.png').scaled(128, 128)
#     walk2 = QPixmap(f'resources/PetArt/{pack_name}/walk2.png').scaled(128, 128)
#     walk3 = QPixmap(f'resources/PetArt/{pack_name}/walk3.png').scaled(128, 128)
#     walk4 = QPixmap(f'resources/PetArt/{pack_name}/walk4.png').scaled(128, 128)
#     NoneArt = QPixmap(f'resources/PetArt/{pack_name}/None.png').scaled(128, 128)

#     default_r = default.transformed(QTransform().scale(-1, 1))
#     default2_r = default2.transformed(QTransform().scale(-1, 1))
#     walk_r = walk.transformed(QTransform().scale(-1, 1))
#     walk2_r = walk2.transformed(QTransform().scale(-1, 1))
#     walk3_r = walk3.transformed(QTransform().scale(-1, 1))
#     walk4_r = walk4.transformed(QTransform().scale(-1, 1))

#     return [default, default2, default_r, default2_r, jump, pickup, walk, walk2, walk3, walk4, walk_r, walk2_r, walk3_r, walk4_r, NoneArt]

# DEFAULT = 0
# DEFAULT2 = 1
# DEFAULT_R = 2
# DEFAULT2_R = 3
# JUMP = 4
# PICKUP = 5
# WALK1 = 6
# WALK2 = 7
# WALK3 = 8
# WALK4 = 9
# WALK1_R = 10
# WALK2_R = 11
# WALK3_R = 12
# WALK4_R = 13
# NONE_ART = 14

# PetArtList = ReadPixmap("艾罗")

import base64
from PySide6.QtGui import QPixmap, QTransform
from resources.image_resources import *
from PySide6.QtCore import QByteArray

def base64_to_pixmap(base64_str, width=128, height=128):
    try:
        image_data = base64.b64decode(base64_str)
        
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(image_data))
        
        # 缩放
        if not pixmap.isNull():
            return pixmap.scaled(width, height)
        return QPixmap(width, height)
    except Exception as e:
        print(f"创建图片失败: {e}")
        return QPixmap(width, height)

def ReadPixmap(pack_name='default'):
    default = base64_to_pixmap(DEFAULT_PNG, 128, 128)
    default2 = base64_to_pixmap(DEFAULT2_PNG, 128, 128)
    jump = base64_to_pixmap(JUMP_PNG, 128, 128)
    pickup = base64_to_pixmap(PICKUP_PNG, 128, 128)
    walk = base64_to_pixmap(WALK_PNG, 128, 128)
    walk2 = base64_to_pixmap(WALK2_PNG, 128, 128)
    walk3 = base64_to_pixmap(WALK3_PNG, 128, 128)
    walk4 = base64_to_pixmap(WALK4_PNG, 128, 128)
    NoneArt = base64_to_pixmap(NONE_PNG, 128, 128)

    default_r = default.transformed(QTransform().scale(-1, 1))
    default2_r = default2.transformed(QTransform().scale(-1, 1))
    walk_r = walk.transformed(QTransform().scale(-1, 1))
    walk2_r = walk2.transformed(QTransform().scale(-1, 1))
    walk3_r = walk3.transformed(QTransform().scale(-1, 1))
    walk4_r = walk4.transformed(QTransform().scale(-1, 1))

    return [default, default2, default_r, default2_r, jump, pickup, 
            walk, walk2, walk3, walk4, walk_r, walk2_r, walk3_r, walk4_r, NoneArt]

DEFAULT = 0
DEFAULT2 = 1
DEFAULT_R = 2
DEFAULT2_R = 3
JUMP = 4
PICKUP = 5
WALK1 = 6
WALK2 = 7
WALK3 = 8
WALK4 = 9
WALK1_R = 10
WALK2_R = 11
WALK3_R = 12
WALK4_R = 13
NONE_ART = 14

PetArtList = ReadPixmap("")
