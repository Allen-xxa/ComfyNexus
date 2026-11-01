"""静态文件服务器安全边界测试（Phase 1.2）

覆盖整改点：
- `_resolve_within()`：绝对路径、盘符、`..`、编码穿越、反斜杠、NUL、软链接逃逸全部拒绝
- Flask test client：越界请求返回 404，且响应体不回显入参与本机绝对路径
- 合法静态文件与前端路由回退（SPA fallback）行为不变
- CORS 只回显回环地址来源，其它站点拿不到 `Access-Control-Allow-Origin`
- 绑定地址固定为回环，不会误监听对外网卡
"""

import os
import socket
import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.utils import http_server as http_server_module  # noqa: E402
from backend.src.utils.http_server import (  # noqa: E402
    ALLOWED_CORS_ORIGINS,
    LOOPBACK_HOST,
    StaticFileServer,
    _resolve_within,
    find_available_port,
)

TRAVERSAL_INPUTS = [
    "C:/Windows/win.ini",              # 盘符绝对路径：pathlib 的 `/` 会直接替换整条路径
    "../outside.txt",                  # 目录穿越
    "../../outside.txt",
    "assets/../../outside.txt",        # 合法前缀后再穿越
    "..\\..\\Windows\\win.ini",        # 反斜杠（Windows 分隔符）
    "\\\\server\\share\\file.txt",     # UNC
    "nul.txt\x00.png",                 # NUL 字节
    "././././x",                       # `.` 段
    "a//b",                            # 空段
    "/etc/passwd",                     # 前导斜杠（路由里拿不到，但直接调用要挡住）
    "",
]


# ==================== 路径收敛函数 ====================


def test_合法相对路径收敛到目录内(tmp_path):
    base = tmp_path / "dist"
    (base / "assets").mkdir(parents=True)
    (base / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")

    resolved = _resolve_within(base, "assets/index-abc.js")

    assert resolved is not None
    assert resolved.is_file()
    assert resolved.read_text(encoding="utf-8") == "console.log(1)"


@pytest.mark.parametrize("unsafe", TRAVERSAL_INPUTS)
def test_越界路径一律拒绝(tmp_path, unsafe):
    base = tmp_path / "dist"
    base.mkdir(parents=True)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    assert _resolve_within(base, unsafe) is None


def test_绝对路径不会被静默改写成本机文件(tmp_path):
    """`Path(base) / 绝对路径` 会得到那个绝对路径，正是漏洞根源，必须挡住。"""
    base = tmp_path / "dist"
    base.mkdir(parents=True)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    assert _resolve_within(base, str(outside)) is None


@pytest.mark.skipif(os.name != "posix", reason="POSIX 软链接创建需要符号链接权限")
def test_软链接指向目录外时拒绝(tmp_path):
    base = tmp_path / "dist"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (base / "link.txt").symlink_to(outside)

    assert _resolve_within(base, "link.txt") is None


def test_base_dir_本身允许解析(tmp_path):
    base = tmp_path / "dist"
    base.mkdir()

    assert _resolve_within(base, "index.html") == (base.resolve() / "index.html")


# ==================== Flask test client ====================


@pytest.fixture
def dist_client(tmp_path, monkeypatch):
    """构造一个只服务临时目录的服务器实例（不启动线程），用 test client 打请求。"""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>APP</html>", encoding="utf-8")
    (dist / "assets" / "main-abc123.js").write_text("console.log(1)", encoding="utf-8")
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("OUTSIDE-SECRET-CONTENT", encoding="utf-8")

    # 把各图片路由的根目录指到临时目录
    monkeypatch.setattr("backend.src.utils.paths.get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "backend.src.utils.paths.get_prompt_images_dir", lambda: tmp_path / "prompt_images"
    )
    monkeypatch.setattr(
        "backend.src.utils.paths.get_data_dir", lambda sub=None: tmp_path / "data"
    )
    (tmp_path / "lora_data" / "preview").mkdir(parents=True)
    (tmp_path / "prompt_images").mkdir(parents=True)

    server = StaticFileServer(dist, port=0)
    return server.app.test_client(), dist, secret


def test_合法静态文件正常返回(dist_client):
    client, _, _ = dist_client

    resp = client.get("/assets/main-abc123.js")

    assert resp.status_code == 200
    assert b"console.log(1)" in resp.data


def test_首页返回index_html(dist_client):
    client, _, _ = dist_client

    resp = client.get("/")

    assert resp.status_code == 200
    assert b"APP" in resp.data


def test_前端路由回退index_html(dist_client):
    client, _, _ = dist_client

    resp = client.get("/settings/api-config")

    assert resp.status_code == 200
    assert b"APP" in resp.data


def test_缺失的js文件返回404不回退首页(dist_client):
    client, _, _ = dist_client

    resp = client.get("/assets/does-not-exist.js")

    assert resp.status_code == 404
    assert b"APP" not in resp.data
    assert b"does-not-exist.js" not in resp.data


@pytest.mark.parametrize(
    "target",
    [
        "/../outside-secret.txt",
        "/..%2Foutside-secret.txt",
        "/%2e%2e/outside-secret.txt",
        "/assets/../../outside-secret.txt",
        "/..%5c..%5coutside-secret.txt",
    ],
)
def test_静态路由穿越请求不返回越界文件(dist_client, target):
    client, _, secret = dist_client

    resp = client.get(target)

    assert b"OUTSIDE-SECRET-CONTENT" not in resp.data
    assert resp.status_code in (200, 404)  # 200 只可能是 SPA 回退的 index.html
    if resp.status_code == 404:
        assert resp.data == b"Not Found"
    else:
        assert b"APP" in resp.data


def test_绝对路径请求不返回外部文件(dist_client):
    client, _, secret = dist_client

    resp = client.get("/" + str(secret).replace("\\", "/"))

    assert b"OUTSIDE-SECRET-CONTENT" not in resp.data


@pytest.mark.parametrize(
    "path",
    [
        "/images/../../outside-secret.txt",
        "/images/..%2F..%2Foutside-secret.txt",
        "/images/..%5c..%5coutside-secret.txt",
        "/images/nul\x00.png",
        "/prompt/images/../../outside-secret.txt",
        "/lora/preview/../../outside-secret.txt/x.png",
    ],
)
def test_图片路由越界请求返回404且不回显路径(dist_client, path):
    client, dist, secret = dist_client

    resp = client.get(path)
    body = resp.data.decode("utf-8", errors="replace")

    assert b"OUTSIDE-SECRET-CONTENT" not in resp.data
    # 拒绝时既不泄露文件内容，也不把本机绝对路径回显给请求方
    assert "outside-secret" not in body
    assert str(secret) not in body
    assert str(dist) not in body
    assert resp.status_code in (200, 404)
    if resp.status_code == 404:
        assert resp.data == b"Not Found"


def test_图片路由合法文件仍可访问(dist_client, tmp_path):
    client, _, _ = dist_client
    images_dir = tmp_path / "data" / "workflows" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "shot.png").write_bytes(b"\x89PNGfake")

    resp = client.get("/images/shot.png")

    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


# ==================== CORS 来源白名单 ====================


def test_回环来源获得跨域头(dist_client):
    client, _, _ = dist_client

    resp = client.get("/assets/main-abc123.js", headers={"Origin": "http://127.0.0.1:5000"})

    assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5000"


def test_任意站点不再获得跨域头(dist_client):
    client, _, _ = dist_client

    resp = client.get("/assets/main-abc123.js", headers={"Origin": "https://evil.example.com"})

    assert resp.headers.get("Access-Control-Allow-Origin") is None


def test_回环但不合法的来源写法被拒(dist_client):
    client, _, _ = dist_client

    for origin in [
        "http://127.0.0.1.evil.example",
        "https://127.0.0.1:5000",   # 协议不是本机在用的 http
        "http://evil.example/?x=http://localhost",
    ]:
        resp = client.get("/assets/main-abc123.js", headers={"Origin": origin})
        assert resp.headers.get("Access-Control-Allow-Origin") is None, origin


def test_白名单只覆盖回环地址():
    allowed = [
        "http://127.0.0.1",
        "http://127.0.0.1:5000",
        "http://localhost:8123",
    ]
    denied = [
        "http://0.0.0.0:5000",
        "http://192.168.1.7:5000",
        "https://evil.example.com",
        "http://localhost.evil.example.com",
    ]
    for origin in allowed:
        assert any(p.match(origin) for p in ALLOWED_CORS_ORIGINS), origin
    for origin in denied:
        assert not any(p.match(origin) for p in ALLOWED_CORS_ORIGINS), origin


# ==================== 回环绑定 ====================


def test_常量_绑定地址是回环():
    assert LOOPBACK_HOST == "127.0.0.1"


def test_查找端口只绑定回环地址(monkeypatch):
    recorded = []

    class FakeSocket:
        def bind(self, addr):
            recorded.append(addr)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(http_server_module.socket, "socket", lambda *a, **kw: FakeSocket())

    port = find_available_port(start_port=5050, max_attempts=3)

    assert port == 5050
    assert recorded == [("127.0.0.1", 5050)]


def test_服务地址始终是回环URL(tmp_path):
    server = StaticFileServer(tmp_path, port=4321)

    assert server.get_url() == "http://127.0.0.1:4321"


def test_运行服务器绑定回环地址(tmp_path, monkeypatch):
    """`_run_server` 里唯一一次 bind 必须使用 LOOPBACK_HOST，不能退化成 0.0.0.0。"""
    captured = {}

    def fake_make_server(host, port, app, **kwargs):
        captured["host"] = host
        captured["port"] = port

        class _NoopServer:
            def serve_forever(self):
                pass

            def shutdown(self):
                pass

        return _NoopServer()

    monkeypatch.setattr(http_server_module, "make_server", fake_make_server)

    server = StaticFileServer(tmp_path, port=4321)
    server._run_server()

    assert captured == {"host": "127.0.0.1", "port": 4321}
