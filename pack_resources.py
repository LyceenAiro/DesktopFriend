import base64
import json
from pathlib import Path

_SUPPORTED_EXTENSIONS = {".png", ".gif", ".jpg", ".jpeg", ".bmp", ".webp"}


def pack_petart_folder(petart_dir: Path, output_dir: Path) -> None:
    """将 PetArt 下的一个角色文件夹打包为 resources/{name}.json"""
    package_name = petart_dir.name
    image_data: dict[str, str] = {}
    image_data["PACK_NAME"] = package_name

    # 收集所有支持的图片文件
    image_files: list[Path] = []
    for ext in _SUPPORTED_EXTENSIONS:
        image_files.extend(sorted(petart_dir.glob(f"*{ext}")))

    if not image_files:
        print(f"  跳过（无图片文件）: {package_name}")
        return

    for img_path in image_files:
        key = img_path.stem.upper()  # default.png → DEFAULT, hide.gif → HIDE
        # 根据扩展名添加后缀标识
        if img_path.suffix.lower() == ".gif":
            key = f"{key}_GIF"
        else:
            key = f"{key}_PNG"
        with img_path.open("rb") as f:
            image_data[key] = base64.b64encode(f.read()).decode("utf-8")
        print(f"  已转换: {img_path.name} -> {key}")

    # LOGO_PNG 复用 DEFAULT_PNG
    if "DEFAULT_PNG" in image_data:
        image_data["LOGO_PNG"] = image_data["DEFAULT_PNG"]
        print(f"  LOGO_PNG <- DEFAULT_PNG")

    output_file = output_dir / f"{package_name}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(image_data, f, ensure_ascii=False, indent=2)
    print(f"  已输出: {output_file}  ({len(image_data)} 个资源)")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    petart_root = base_dir / "resources" / "PetArt"
    output_dir = base_dir / "resources"

    if not petart_root.exists():
        print(f"PetArt 目录不存在: {petart_root}")
        print("请在 resources/PetArt/ 下创建角色文件夹，并放入图片文件。")
    else:
        pack_dirs = sorted([d for d in petart_root.iterdir() if d.is_dir()])
        if not pack_dirs:
            print(f"PetArt 目录为空: {petart_root}")
            print("请在 resources/PetArt/ 下创建角色文件夹，并放入图片文件。")
        else:
            print(f"发现 {len(pack_dirs)} 个资源包:")
            for pack_dir in pack_dirs:
                print(f"\n=== {pack_dir.name} ===")
                pack_petart_folder(pack_dir, output_dir)
            print(f"\n完成！共打包 {len(pack_dirs)} 个资源包")

