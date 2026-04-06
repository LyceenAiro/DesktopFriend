import base64
from pathlib import Path

def convert_images_to_py(images_dict):
    with open("resources/image_resources.py", 'w', encoding='utf-8') as f:
        f.write('# 自动生成的图片资源文件\n')
        f.write('# 请勿手动编辑\n\n')
        
        for var_name, image_path in images_dict.items():
            if Path(image_path).exists():
                with open(image_path, 'rb') as img_file:
                    image_data = img_file.read()
                
                base64_str = base64.b64encode(image_data).decode('utf-8')
                
                f.write(f'{var_name} = """{base64_str}"""\n\n')
                print(f"已转换: {image_path} -> {var_name}")
            else:
                print(f"文件不存在: {image_path}")

if __name__ == "__main__":
    package_name = "default" # 修改资源包名称
    images = {
        'LOGO_PNG': 'logo.png',
        "DEFAULT_PNG": f'resources/PetArt/{package_name}/default.png',
        "DEFAULT2_PNG": f'resources/PetArt/{package_name}/default2.png',
        "JUMP_PNG": f'resources/PetArt/{package_name}/jump.png',
        "PICKUP_PNG": f'resources/PetArt/{package_name}/pickup.png',
        "WALK_PNG": f'resources/PetArt/{package_name}/walk.png',
        "WALK2_PNG": f'resources/PetArt/{package_name}/walk2.png',
        "WALK3_PNG": f'resources/PetArt/{package_name}/walk3.png',
        "WALK4_PNG": f'resources/PetArt/{package_name}/walk4.png',
        "NONE_PNG": f'resources/PetArt/{package_name}/None.png',
        "HIDE_GIF": f'resources/PetArt/{package_name}/hide.gif'
    }
    
    convert_images_to_py(images)
