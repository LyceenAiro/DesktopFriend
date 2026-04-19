"""
Buff 图标管理工具

用于处理 buff 图标的 base64 编码/解码和显示
"""

import base64
from io import BytesIO
from typing import Optional, Dict, Any
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QColor


class BuffIconManager:
    """Buff 图标管理器"""
    
    @staticmethod
    def image_to_base64(image_path: str) -> str:
        """
        将图片文件转换为 base64 字符串
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            base64 编码的字符串
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
        except FileNotFoundError:
            raise ValueError(f"图片文件不存在: {image_path}")
        except Exception as e:
            raise ValueError(f"转换图片失败: {e}")
    
    @staticmethod
    def base64_to_pixmap(base64_str: str, size: int = 32) -> Optional[QPixmap]:
        """
        将 base64 字符串转换为 QPixmap
        
        Args:
            base64_str: base64 编码的图片数据
            size: 图片大小（默认 32x32）
            
        Returns:
            QPixmap 对象，或在转换失败时返回 None
        """
        try:
            image_data = base64.b64decode(base64_str)
            image = QImage()
            if not image.loadFromData(image_data):
                return None
            
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return None
            
            # 缩放到指定大小
            return pixmap.scaledToWidth(size, Qt.TransformationMode.SmoothTransformation)
        except Exception as e:
            print(f"[BuffIcon] 解码 base64 失败: {e}")
            return None
    
    @staticmethod
    def create_placeholder_pixmap(size: int = 32) -> QPixmap:
        """
        创建占位符像素图（灰色方块）
        
        Args:
            size: 像素图大小
            
        Returns:
            占位符 QPixmap
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(204, 204, 204))  # 灰色，不透明
        return pixmap
    
    @staticmethod
    def extract_icon_from_buff(buff_data: Dict[str, Any], size: int = 32) -> Optional[QPixmap]:
        """
        从 buff 数据中提取图标
        
        Args:
            buff_data: buff 数据字典
            size: 图标大小
            
        Returns:
            QPixmap 对象，或在无图标时返回 None
        """
        if not isinstance(buff_data, dict):
            return None
        
        icon_base64 = buff_data.get('icon_base64')
        if not icon_base64 or not isinstance(icon_base64, str):
            return None
        
        return BuffIconManager.base64_to_pixmap(icon_base64, size)


class BuffIconConverter:
    """Buff 图标转换工具 - 用于批量处理"""
    
    @staticmethod
    def convert_image_file_to_json_field(image_path: str) -> Dict[str, str]:
        """
        将图片文件转换为可添加到 buff JSON 中的格式
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            包含 icon_base64 字段的字典
        """
        base64_str = BuffIconManager.image_to_base64(image_path)
        return {'icon_base64': base64_str}
    
    @staticmethod
    def save_buff_json_with_icon(buff_dict: Dict[str, Any], icon_path: str) -> Dict[str, Any]:
        """
        将图标添加到 buff 字典中
        
        Args:
            buff_dict: buff 数据字典
            icon_path: 图标文件路径
            
        Returns:
            更新后的 buff 数据字典
        """
        base64_str = BuffIconManager.image_to_base64(icon_path)
        buff_dict['icon_base64'] = base64_str
        return buff_dict
