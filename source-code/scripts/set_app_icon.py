"""一键替换应用图标

用法：
    python scripts/set_app_icon.py                          # 用默认的 v4 设计重新生成
    python scripts/set_app_icon.py assets/icons/xxx.png     # 换成指定图片
    python scripts/set_app_icon.py D:/design/new.png --no-transparent

生成四份产物：
    source-code/icon.ico                     窗口图标 + PyInstaller 打包图标
    source-code/assets/icon.png              系统托盘图标
    source-code/frontend/public/favicon.ico  浏览器标签页图标
    source-code/frontend/public/app-icon.png 侧边栏与关于页的 logo

默认会把纯白背景抠成透明（`--no-transparent` 可关闭）。AI 出图的图标基本都是
不透明白底，不抠的话任务栏上会显示成一个白方块。

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
FAVICON_PATH = SOURCE_ROOT / "frontend" / "public" / "favicon.ico"
APP_ICON_PATH = SOURCE_ROOT / "frontend" / "public" / "app-icon.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 ComfyNexus 应用图标")
    parser.add_argument(
        "source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help="源图路径（正方形，建议 1024px 以上）",
    )
    parser.add_argument(
        "--no-transparent",
        action="store_true",
        help="保留原始背景，不做透明处理",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=10,
        help="抠图容差（0-255，默认 10）。背景不干净时可调大",
    )
    parser.add_argument(
        "--dim-whites",
        type=float,
        default=0.84,
        help="近白色主体的压暗系数（默认 0.84）。1.0 表示保持原白色；"
        "图标主体为白色时，在浅色任务栏上会没有对比度",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()

    transparent = not args.no_transparent
    dim_whites = None if args.dim_whites >= 1.0 else args.dim_whites

    try:
        ico, png = build_app_icons(
            source,
            ICO_PATH,
            PNG_PATH,
            transparent=transparent,
            tolerance=args.tolerance,
            dim_whites=dim_whites,
        )
        # favicon 只需要 ico，复用同一张源图
        build_app_icons(
            source,
            FAVICON_PATH,
            FAVICON_PATH.with_suffix(".tmp.png"),
            ico_sizes=(16, 32, 48),
            transparent=transparent,
            tolerance=args.tolerance,
            dim_whites=dim_whites,
        )
        FAVICON_PATH.with_suffix(".tmp.png").unlink(missing_ok=True)
        # 侧边栏 / 关于页的 logo，尺寸固定 256
        build_app_icons(
            source,
            APP_ICON_PATH.with_suffix(".tmp.ico"),
            APP_ICON_PATH,
            ico_sizes=(256,),
            png_size=256,
            transparent=transparent,
            tolerance=args.tolerance,
            dim_whites=dim_whites,
        )
        APP_ICON_PATH.with_suffix(".tmp.ico").unlink(missing_ok=True)
    except Exception as e:
        print(f"生成失败: {e}")
        return 1

    print(f"源图: {source}")
    print(f"透明背景: {'是' if transparent else '否'}")
    print(f"白色主体压暗: {dim_whites if dim_whites else '否'}")
    print(f"已生成: {ico}  尺寸 {describe_ico(ico)}")
    print(f"已生成: {png}")
    print(f"已生成: {FAVICON_PATH}")
    print(f"已生成: {APP_ICON_PATH}")
    print("重启应用后生效；打包时 PyInstaller 会使用同一份 icon.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
