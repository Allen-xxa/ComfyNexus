"""一键替换应用图标

用法：
    python scripts/set_app_icon.py                          # 用默认的 v4 设计重新生成
    python scripts/set_app_icon.py assets/icons/xxx.png     # 换成指定图片
    python scripts/set_app_icon.py D:/design/new.png --keep-name

生成两份产物：
    source-code/icon.ico           窗口图标 + PyInstaller 打包图标
    source-code/assets/icon.png    系统托盘图标

若换了新设计并希望长期使用，把图片放进 assets/icons/ 并在此处改 DEFAULT_SOURCE。
"""

import argparse
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SOURCE_ROOT))

from backend.src.utils.icon_builder import build_app_icons, describe_ico  # noqa: E402

DEFAULT_SOURCE = SOURCE_ROOT / "assets" / "icons" / "comfynexus-v4.png"
ICO_PATH = SOURCE_ROOT / "icon.ico"
PNG_PATH = SOURCE_ROOT / "assets" / "icon.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 ComfyNexus 应用图标")
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help="源图路径（正方形，建议 1024px 以上）",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()

    try:
        ico, png = build_app_icons(source, ICO_PATH, PNG_PATH)
    except Exception as e:
        print(f"生成失败: {e}")
        return 1

    print(f"源图: {source}")
    print(f"已生成: {ico}  尺寸 {describe_ico(ico)}")
    print(f"已生成: {png}")
    print("重启应用后生效；打包时 PyInstaller 会使用同一份 icon.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
