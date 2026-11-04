# -*- mode: python ; coding: utf-8 -*-
"""ComfyNexus PyInstaller spec (onedir 模式)

- 入口: source-code/backend/main.py
- exe 图标: source-code/icon.ico
- 数据文件:
    backend/config      -> backend/config            (onedir 下落到 _internal/backend/config，首次运行由 main.py 迁移)
    source-code/dist    -> dist                       (onedir 下落到 _internal/dist，main.py 已做 _internal 回退)
    source-code/icon.ico-> .                          (onedir 下落到 _internal/icon.ico，main.py 已做 _internal 回退)
    source-code/assets  -> assets                     (onedir 下落到 _internal/assets)
- 依赖: pythonnet / webview 用 collect_all 收集 native 依赖
"""
import os
from PyInstaller.utils.hooks import collect_all

ROOT = r'E:\project\ComfyNexus\source-code'
BACKEND = os.path.join(ROOT, 'backend')

pythonnet_datas, pythonnet_bins, pythonnet_hiddenimports = collect_all('pythonnet')
webview_datas, webview_bins, webview_hiddenimports = collect_all('webview')

a = Analysis(
    [os.path.join(BACKEND, 'main.py')],
    pathex=[BACKEND, ROOT],
    binaries=[*pythonnet_bins, *webview_bins],
    datas=[
        (os.path.join(BACKEND, 'config'), 'backend/config'),
        (os.path.join(ROOT, 'dist'), 'dist'),
        (os.path.join(ROOT, 'icon.ico'), '.'),
        (os.path.join(ROOT, 'assets'), 'assets'),
    ],
    hiddenimports=[
        'pythonnet', 'clr',
        *pythonnet_hiddenimports,
        *webview_hiddenimports,
        'backend', 'backend.src',
    ],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ComfyNexus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 先保留控制台便于排查打包问题；验证通过后改为 False 可隐藏黑窗口
    console=True,
    icon=os.path.join(ROOT, 'icon.ico'),
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ComfyNexus',
)
