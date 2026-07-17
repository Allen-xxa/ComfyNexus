# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# ============================================
# .NET 8 coreclr 源码预处理（必须在 Analysis 之前执行）
# PyInstaller 在 Analysis() 阶段就会收集 pywebview 的 lib DLL，并把
# winforms.py 编译为字节码放入 PYZ。此前这两段处理位于 Analysis 之后，
# 修改只落在磁盘源文件上，首次构建（全新环境或 --clean 后缓存失效）的
# 产物内嵌的仍是未修补版本：OpenFolderDialog 反射 .NET Framework 内部
# 类型，在 .NET 8 下 import winforms 阶段即抛 AttributeError，应用启动
# 直接崩溃；从第二次构建起才恰好正确。移到 Analysis 之前彻底消除该时序问题。
# ============================================

# 确保 pywebview lib 目录里是 netcoreapp3.0 版本的 WebView2 DLL
# 直接替换源文件，让 PyInstaller hook 自然收集正确的版本
import shutil as _shutil

_netcore_dir = os.path.join('backend', 'lib', 'webview2_netcore')
_webview_lib = os.path.join(os.path.abspath('.'), '.venv', 'Lib', 'site-packages', 'webview', 'lib')

if os.path.isdir(_webview_lib) and os.path.isdir(_netcore_dir):
    for _dll in ['Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll']:
        _src = os.path.join(_netcore_dir, _dll)
        _dst = os.path.join(_webview_lib, _dll)
        if os.path.exists(_src):
            _shutil.copy2(_src, _dst)
            print(f"[spec] .NET 8: copied netcoreapp3.0 {_dll} to pywebview lib")

    # 清理 .bak 备份文件
    for _f in os.listdir(_webview_lib):
        if _f.endswith('.bak'):
            os.remove(os.path.join(_webview_lib, _f))
            print(f"[spec] .NET 8: removed {_f}")

# 直接 patch venv 中 pywebview 的 winforms.py
# 该类的 OpenFolderDialog 使用反射访问 .NET Framework 内部类型，在 .NET 8 下不存在
# 必须在打包前 patch 源文件，因为 PyInstaller 会编译 .pyc 打包进去
import site
_winforms_candidates = [
    os.path.join(os.path.abspath('.'), '.venv', 'Lib', 'site-packages', 'webview', 'platforms', 'winforms.py'),
]
# 也搜索 site-packages
for sp in site.getsitepackages() if hasattr(site, 'getsitepackages') else []:
    _winforms_candidates.append(os.path.join(sp, 'webview', 'platforms', 'winforms.py'))

for _wf_path in _winforms_candidates:
    if os.path.exists(_wf_path):
        with open(_wf_path, 'r', encoding='utf-8') as _f:
            _wf_content = _f.read()
        
        if '# PATCHED_FOR_DOTNET8' in _wf_content:
            print(f"[spec] .NET 8: winforms.py already patched: {_wf_path}")
            break
        
        _modified = False

        # Patch 1: 修复 _is_chromium 检测（精简版 Windows 没有 .NET Framework 注册表键）
        _old_is_chromium = "is_chromium = not is_cef and _is_chromium() and forced_gui_ != 'mshtml'"
        _new_is_chromium = "is_chromium = not is_cef and (forced_gui_ == 'edgechromium' or _is_chromium()) and forced_gui_ != 'mshtml'  # PATCHED_FOR_DOTNET8"
        if _old_is_chromium in _wf_content:
            _wf_content = _wf_content.replace(_old_is_chromium, _new_is_chromium)
            _modified = True
            print(f"[spec] .NET 8: Patched _is_chromium detection")

        # Patch 2: 替换 OpenFolderDialog
        if 'FileDialogNative+IFileDialog' in _wf_content:
            _marker = "class OpenFolderDialog:"
            if _marker in _wf_content:
                _idx = _wf_content.index(_marker)
                _rest = _wf_content[_idx:]
                _lines = _rest.split('\n')
                _end = len(_lines)
                for _li, _ln in enumerate(_lines[1:], 1):
                    _s = _ln.strip()
                    if _ln and not _ln[0].isspace() and _s and not _s.startswith('#'):
                        _end = _li
                        break
                
                _repl = '''class OpenFolderDialog:  # PATCHED_FOR_DOTNET8
    """Folder dialog compatible with .NET 8"""
    foldersFilter = 'Folders|\\n'

    @classmethod
    def show(cls, parent=None, initialDirectory=None, allow_multiple=False, title=None):
        dialog = WinForms.FolderBrowserDialog()
        if initialDirectory:
            dialog.SelectedPath = initialDirectory
        if title:
            dialog.Description = title
        result = dialog.ShowDialog()
        if result == WinForms.DialogResult.OK:
            return (dialog.SelectedPath,)
        return None

'''
                _wf_content = _wf_content[:_idx] + _repl + '\n'.join(_lines[_end:])
                _modified = True
                print(f"[spec] .NET 8: Patched OpenFolderDialog")

        if _modified:
            with open(_wf_path, 'w', encoding='utf-8') as _f:
                _f.write(_wf_content)
            _pycache = os.path.join(os.path.dirname(_wf_path), '__pycache__')
            if os.path.exists(_pycache):
                import shutil
                shutil.rmtree(_pycache, ignore_errors=True)
            print(f"[spec] .NET 8: winforms.py patched: {_wf_path}")
        break

a = Analysis(
    ['backend/main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('dist', 'dist'),
        ('assets', 'assets'),
        ('comfy_nexus_version.py', '.'),
        ('backend/__init__.py', 'backend'),
        (os.path.join('backend', 'src'), os.path.join('backend', 'src')),
        (os.path.join('backend', 'models', 'nsfw.onnx'), os.path.join('models')),
        (os.path.join('backend', 'lib', 'LibreHardwareMonitor'), os.path.join('lib', 'LibreHardwareMonitor')),
        (os.path.join('backend', 'lib', 'librehardwaremonitorlib', 'runtimes'), os.path.join('lib', 'librehardwaremonitorlib', 'runtimes')),
        (os.path.join('backend', 'lib', 'webview2_netcore'), os.path.join('backend', 'lib', 'webview2_netcore')),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'comfy_nexus_version',
        'backend',
        'backend.src',
        'backend.src.bridge',
        'backend.src.bridge.api',
        'backend.src.bridge.controllers',
        'backend.src.core',
        'backend.src.core.config',
        'backend.src.core.env',
        'backend.src.core.monitor',
        'backend.src.core.process',
        'backend.src.core.ai',
        'backend.src.core.ai.providers',
        'backend.src.core.ai.search',
        'backend.src.core.ai.migrations',
        'backend.src.core.plugin',
        'backend.src.core.marketplace',
        'backend.src.core.dependency',
        'backend.src.core.lora',
        'backend.src.core.prompt_library',
        'backend.src.core.updater',
        'backend.src.utils',
        'backend.src.ui',
        'backend.src.gallery',
        'backend.src.gallery.nsfw',
        'onnxruntime',
        'yaml',
        'dotenv',
        'aiofiles',
        'httpx',
        'websockets',
        'psutil',
        'pathlib',
        'json',
        'asyncio',
        'subprocess',
        'socket',
        'cv2',
    ],
    hookspath=[os.path.join(os.path.abspath('.'), 'hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

def filter_googleapiclient_datas(datas_list):
    filtered = []
    excluded_count = 0
    for item in datas_list:
        source = item[0] if isinstance(item, tuple) else str(item)
        source_lower = source.lower().replace('\\', '/')
        if 'googleapiclient' in source_lower and 'discovery_cache/documents' in source_lower:
            if 'customsearch.v1.json' in source_lower:
                filtered.append(item)
            else:
                excluded_count += 1
        else:
            filtered.append(item)
    print(f"[spec] googleapiclient: 排除了 {excluded_count} 个不需要的 discovery documents")
    return filtered

def filter_cv2_datas(datas_list):
    filtered = []
    excluded_count = 0
    for item in datas_list:
        source = item[0] if isinstance(item, tuple) else str(item)
        source_lower = source.lower()
        if 'haarcascade' in source_lower:
            excluded_count += 1
        else:
            filtered.append(item)
    print(f"[spec] cv2: 排除了 {excluded_count} 个 haarcascade 文件")
    return filtered

a.datas = filter_googleapiclient_datas(a.datas)
a.datas = filter_cv2_datas(a.datas)

# ============================================
# 打包瘦身：排除不需要的大文件
# ============================================
def filter_bloat(items_list, item_type='datas'):
    """统一过滤 datas 和 binaries 中的冗余文件"""
    filtered = []
    excluded = {}
    
    exclude_patterns = [
        # cv2: 类型提示文件，运行时不需要
        ('cv2/__init__.pyi', 'cv2 类型提示'),
        ('cv2\\__init__.pyi', 'cv2 类型提示'),
        # Pillow: AVIF 格式支持（7.5MB），项目不使用 AVIF
        ('_avif.cp', 'Pillow AVIF 插件'),
        # LibreHardwareMonitor: 调试符号和文档
        ('.pdb', 'PDB 调试符号'),
        # fake_useragent: 浏览器数据库（2.5MB）
        ('fake_useragent/data/browsers.jsonl', 'fake_useragent 数据库'),
        ('fake_useragent\\data\\browsers.jsonl', 'fake_useragent 数据库'),
        # onnxruntime: 排除不需要的子模块（只保留 capi 推理核心）
        ('onnxruntime/transformers', 'onnxruntime transformers'),
        ('onnxruntime\\transformers', 'onnxruntime transformers'),
        ('onnxruntime/quantization', 'onnxruntime quantization'),
        ('onnxruntime\\quantization', 'onnxruntime quantization'),
        ('onnxruntime/tools', 'onnxruntime tools'),
        ('onnxruntime\\tools', 'onnxruntime tools'),
        ('onnxruntime/datasets', 'onnxruntime datasets'),
        ('onnxruntime\\datasets', 'onnxruntime datasets'),
        # onnx: collect_all 带进来的多余依赖，推理不需要
        ('onnxscript', 'onnxscript'),
        # LibreHardwareMonitorLib: 只保留 win-x64，排除其他架构
        ('librehardwaremonitorlib/runtimes/win-x86', 'LibreHardwareMonitorLib win-x86'),
        ('librehardwaremonitorlib\\runtimes\\win-x86', 'LibreHardwareMonitorLib win-x86'),
        ('librehardwaremonitorlib/runtimes/win-arm64', 'LibreHardwareMonitorLib win-arm64'),
        ('librehardwaremonitorlib\\runtimes\\win-arm64', 'LibreHardwareMonitorLib win-arm64'),
    ]
    
    for item in items_list:
        source = item[0] if isinstance(item, tuple) else str(item)
        source_lower = source.lower().replace('\\', '/')
        
        should_exclude = False
        for pattern, reason in exclude_patterns:
            if pattern.lower() in source_lower:
                excluded[reason] = excluded.get(reason, 0) + 1
                should_exclude = True
                break
        
        if not should_exclude:
            filtered.append(item)
    
    total_excluded = sum(excluded.values())
    if total_excluded > 0:
        print(f"[spec] 瘦身过滤 ({item_type}): 共排除 {total_excluded} 个文件")
        for reason, count in sorted(excluded.items()):
            print(f"  - {reason}: {count} 个")
    
    return filtered

a.datas = filter_bloat(a.datas, 'datas')
a.binaries = filter_bloat(a.binaries, 'binaries')

# 排除 .bak 文件（以防万一）
a.binaries = [item for item in a.binaries if not item[0].endswith('.bak')]
a.datas = [item for item in a.datas if not item[0].endswith('.bak')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    uac_admin=True,
    manifest='backend/uac.manifest',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ComfyNexus',
)
