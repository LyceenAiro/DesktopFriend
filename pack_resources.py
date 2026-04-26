import base64
import json
from pathlib import Path


def convert_images_to_json(images_dict, output_path="resources/default.json"):
    base_dir = Path(__file__).resolve().parent
    output_file = base_dir / output_path
    output_file.parent.mkdir(parents=True, exist_ok=True)

    image_data = {}
    for var_name, image_path in images_dict.items():
        path = base_dir / image_path
        if path.exists():
            with path.open('rb') as img_file:
                image_bytes = img_file.read()
            image_data[var_name] = base64.b64encode(image_bytes).decode('utf-8')
            print(f"已转换: {path} -> {var_name}")
        else:
            # 如果不是有效路径，作为纯字符串直接写入
            if not Path(image_path).suffix and not ('/' in image_path or '\\' in image_path):
                image_data[var_name] = image_path
                print(f"已写入字符串字段: {var_name} = {image_path}")
            else:
                print(f"文件不存在: {path}")

    with output_file.open('w', encoding='utf-8') as f:
        json.dump(image_data, f, ensure_ascii=False, indent=2)

    print(f"已保存: {output_file}")


if __name__ == "__main__":
    package_name = "艾罗"  # 修改资源包名称
    images = {
        'PACK_NAME': package_name,
        'LOGO_PNG': 'logo.png',
        'DEFAULT_PNG': f'resources/PetArt/{package_name}/default.png',
        'DEFAULT2_PNG': f'resources/PetArt/{package_name}/default2.png',
        'JUMP_PNG': f'resources/PetArt/{package_name}/jump.png',
        'PICKUP_PNG': f'resources/PetArt/{package_name}/pickup.png',
        'WALK_PNG': f'resources/PetArt/{package_name}/walk.png',
        'WALK2_PNG': f'resources/PetArt/{package_name}/walk2.png',
        'WALK3_PNG': f'resources/PetArt/{package_name}/walk3.png',
        'WALK4_PNG': f'resources/PetArt/{package_name}/walk4.png',
        'NONE_PNG': f'resources/PetArt/{package_name}/None.png',
        'HIDE_GIF': f'resources/PetArt/{package_name}/hide.gif',
        "SLEEP_PNG": f'resources/PetArt/{package_name}/sleep.png',
        "SLEEP2_PNG": f'resources/PetArt/{package_name}/sleep2.png',
        "DYING_PNG": f'resources/PetArt/{package_name}/dying.png',
        "DIE_PNG": f'resources/PetArt/{package_name}/die.png'
    }

    convert_images_to_json(images, output_path=f"resources/{package_name}.json")
