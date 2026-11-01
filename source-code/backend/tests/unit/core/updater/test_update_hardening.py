"""更新器 / 更新控制的加固测试（Phase 1.3）

覆盖整改点：
- 更新包解压的 zip-slip 防御：`..`、绝对路径、盘符、反斜杠、NUL、软链接逃逸
- 校验失败时**一个字节都不落盘**（先整体校验再解压）
- 解压体积与成员数上限（zip bomb 兜底）
- 官方通道强制 SHA256：version.json 缺少或格式不对时拒绝下载；开发通道允许缺省

说明：`backend/updater/updater.py` 是独立打包的单文件脚本，导入时会初始化
.NET/WebView 运行时。这里在导入前用桩替换 `pythonnet` / `webview`，只测纯逻辑。
"""

import importlib.util
import sys
import types
import zipfile
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UPDATER_PATH = _BACKEND_DIR / "updater" / "updater.py"


@pytest.fixture(scope="module")
def updater():
    """以桩依赖加载 updater.py，避免真的去初始化 .NET / WebView。"""
    stubs = {}
    if "pythonnet" not in sys.modules:
        pythonnet_stub = types.ModuleType("pythonnet")
        pythonnet_stub._LOADED = True  # _init_coreclr_for_updater() 直接返回
        pythonnet_stub.load = lambda *a, **k: None
        stubs["pythonnet"] = pythonnet_stub

    if "clr" not in sys.modules:
        clr_stub = types.ModuleType("clr")
        clr_stub.AddReference = lambda *a, **k: None
        stubs["clr"] = clr_stub

    if "webview" not in sys.modules:
        stubs["webview"] = types.ModuleType("webview")

    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("comfynexus_updater_under_test", UPDATER_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        for name in stubs:
            sys.modules.pop(name, None)


def _write_zip(zip_path: Path, members: dict) -> Path:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return zip_path


def _extract(updater, zip_path: Path, target_dir: Path):
    api = updater.UpdaterAPI()
    api._extract_update(zip_path, target_dir)


# ==================== 合法包仍然可解压 ====================


def test_合法更新包正常解压到目标目录(updater, tmp_path):
    zip_path = _write_zip(
        tmp_path / "ok.zip",
        {
            "ComfyNexus/ComfyNexus.exe": b"exe",
            "ComfyNexus/_internal/app.py": b"print(1)",
            "ComfyNexus/sub/dir/data.txt": b"data",
        },
    )
    target = tmp_path / "app"
    target.mkdir()

    _extract(updater, zip_path, target)

    assert (target / "ComfyNexus.exe").read_bytes() == b"exe"
    assert (target / "_internal" / "app.py").read_bytes() == b"print(1)"
    assert (target / "sub" / "dir" / "data.txt").read_bytes() == b"data"


def test_顶层无根目录的包也按原样解压(updater, tmp_path):
    """只有一个顶层文件时识别不出根目录，旧行为是直接解到目标目录，保持兼容。"""
    zip_path = _write_zip(tmp_path / "flat.zip", {"readme.txt": b"hi"})
    target = tmp_path / "app"
    target.mkdir()

    _extract(updater, zip_path, target)

    assert (target / "readme.txt").read_bytes() == b"hi"


# ==================== zip-slip ====================


@pytest.mark.parametrize(
    "member",
    [
        "ComfyNexus/../evil.txt",
        "ComfyNexus/../../evil.txt",
        "../evil.txt",
        "ComfyNexus/a/../../../evil.txt",
        "C:/Windows/evil.txt",
        "ComfyNexus/sub\\..\\..\\evil.txt",
        # 注意：成员名里的 NUL 无法通过 zipfile 往返构造（读取时会被截断成合法名），
        # 这条路径由 `_member_relative_path` 的函数级用例覆盖。
    ],
)
def test_越界成员直接中止且不落盘(updater, tmp_path, member):
    zip_path = _write_zip(
        tmp_path / "bad.zip",
        {
            "ComfyNexus/ComfyNexus.exe": b"exe",  # 正常成员也不能先被写出来
            member: b"pwned",
        },
    )
    target = tmp_path / "app"
    target.mkdir()
    marker = tmp_path / "evil.txt"

    with pytest.raises(Exception) as excinfo:
        _extract(updater, zip_path, target)

    assert "解压" in str(excinfo.value)
    assert not marker.exists()
    assert list(tmp_path.rglob("evil.txt")) == []
    # 先整体校验再解压：正常成员也不应该被提前写出来
    assert not (target / "ComfyNexus.exe").exists()


def test_成员数超限时中止(updater, tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "MAX_ARCHIVE_MEMBERS", 2)
    zip_path = _write_zip(
        tmp_path / "many.zip",
        {f"ComfyNexus/f{i}.txt": b"x" for i in range(3)},
    )
    target = tmp_path / "app"
    target.mkdir()

    with pytest.raises(Exception):
        _extract(updater, zip_path, target)

    assert not any(target.iterdir())


def test_单文件解压超限时中止(updater, tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "MAX_SINGLE_FILE_BYTES", 8)
    zip_path = _write_zip(
        tmp_path / "big.zip",
        {"ComfyNexus/big.bin": b"x" * 64},
    )
    target = tmp_path / "app"
    target.mkdir()

    with pytest.raises(Exception):
        _extract(updater, zip_path, target)

    assert not (target / "big.bin").exists()


def test_解压总量超限时中止(updater, tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "MAX_SINGLE_FILE_BYTES", 1024)
    monkeypatch.setattr(updater, "MAX_TOTAL_EXTRACT_BYTES", 100)
    zip_path = _write_zip(
        tmp_path / "total.zip",
        {f"ComfyNexus/part{i}.bin": b"x" * 60 for i in range(3)},
    )
    target = tmp_path / "app"
    target.mkdir()

    with pytest.raises(Exception):
        _extract(updater, zip_path, target)

    assert not any(target.iterdir())


def test_软链接目录不会被当成合法落点(updater, tmp_path):
    """目标目录里已有指向外部的软链接时，解析后越界必须拒绝（Windows 无权限时跳过）。    """
    target = tmp_path / "app"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = target / "linkdir"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境无法创建目录软链接")

    zip_path = _write_zip(tmp_path / "link.zip", {"ComfyNexus/linkdir/file.txt": b"x"})

    with pytest.raises(Exception):
        _extract(updater, zip_path, target)

    assert not (outside / "file.txt").exists()


# ==================== 成员名转换 ====================


@pytest.mark.parametrize(
    "member, root, expected",
    [
        ("ComfyNexus/a/b.txt", "ComfyNexus", "a/b.txt"),
        ("a/b.txt", None, "a/b.txt"),
        ("ComfyNexus/a/b.txt", None, "ComfyNexus/a/b.txt"),
        ("ComfyNexus", "ComfyNexus", None),          # 剥离后为空
        ("../a", None, None),
        ("/etc/passwd", None, None),
        ("c:/x", None, None),
        ("a\\b", None, None),
        ("a//b", None, None),
        ("a/./b", None, None),
        ("a\x00b", None, None),
        ("", None, None),
    ],
)
def test_成员相对路径判定(updater, member, root, expected):
    assert updater._member_relative_path(member, root) == expected


# ==================== 官方通道强制 SHA256 ====================


class _FakeChecker:
    def __init__(self, dev_token=None):
        self.dev_token = dev_token
        self.dev_repo_owner = None
        self.dev_repo_name = None


class _FakeDownloader:
    def __init__(self):
        self.calls = []

    def download(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"success": True, "zip_path": "x.zip", "from_local": False, "resumed": False}


def _make_controller(dev_token=None, **update_info):
    from backend.src.core.updater.update_controller import UpdateController

    controller = UpdateController.__new__(UpdateController)
    controller._checker = _FakeChecker(dev_token=dev_token)
    controller._downloader = _FakeDownloader()
    controller._settings_manager = None
    controller._update_info = {
        "download_url": "https://example.com/pkg.zip",
        "file_size": 123,
        "latest_version": "v9.9.9",
        **update_info,
    }
    controller._download_progress = {"downloaded": 0, "total": 0, "percentage": 0}
    controller._window = None
    return controller


@pytest.mark.parametrize(
    "file_hash",
    [None, "", "abc", "z" * 64, "6" * 63, "6" * 65],
)
def test_官方通道缺少有效SHA256时拒绝下载(file_hash):
    controller = _make_controller(file_hash=file_hash)

    result = controller.download_update()

    assert result["success"] is False
    assert "SHA256" in result["error"]
    assert controller._downloader.calls == []


def test_官方通道带合法SHA256时正常下载():
    valid_hash = "6ae10a056721662aa41e3b0322baf72ceaee45ada714fd5f3cd29188b4175dcb"
    controller = _make_controller(file_hash=valid_hash)

    result = controller.download_update()

    assert result["success"] is True
    assert len(controller._downloader.calls) == 1
    _, kwargs = controller._downloader.calls[0]
    assert kwargs["file_hash"] == valid_hash


def test_开发通道允许缺少SHA256():
    controller = _make_controller(dev_token="ghp_test", file_hash="")

    result = controller.download_update()

    assert result["success"] is True
    assert len(controller._downloader.calls) == 1


def test_开发通道提供SHA256时仍然传递校验值():
    valid_hash = "a" * 64
    controller = _make_controller(dev_token="ghp_test", file_hash=valid_hash)

    controller.download_update()

    _, kwargs = controller._downloader.calls[0]
    assert kwargs["file_hash"] == valid_hash


def test_sha256格式校验函数():
    from backend.src.core.updater.update_controller import _is_valid_sha256

    assert _is_valid_sha256("A" * 64)
    assert _is_valid_sha256("0" * 64)
    assert not _is_valid_sha256("g" * 64)
    assert not _is_valid_sha256("0" * 63)
    assert not _is_valid_sha256(None)
    assert not _is_valid_sha256(123)
