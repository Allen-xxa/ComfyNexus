"""network_utils 代理配置的离线测试。

替代原 test_proxy_support.py（无断言、依赖真实环境代理变量、async 未加标记）。
所有用例都在临时目录写 settings.json，不读取用户真实配置，也不建立网络连接。
"""

import json

import pytest

from backend.src.core.ai.providers import network_utils
from backend.src.utils import paths as paths_mod


def use_config_dir(monkeypatch, tmp_path):
    """让 get_config_dir 指向临时目录（生产代码在函数内 import，patch 模块属性即可）"""
    monkeypatch.setattr(paths_mod, "get_config_dir", lambda *a, **k: tmp_path)


def write_proxy_settings(tmp_path, proxy_config: dict):
    (tmp_path / "settings.json").write_text(
        json.dumps({"proxy": proxy_config}), encoding="utf-8"
    )


@pytest.mark.unit
def test_代理启用且配置完整时返回代理地址(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": True, "host": "127.0.0.1", "port": "7890"})

    assert network_utils.get_proxy_from_settings() == "http://127.0.0.1:7890"


@pytest.mark.unit
def test_代理未启用时返回_none(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": False, "host": "127.0.0.1", "port": "7890"})

    assert network_utils.get_proxy_from_settings() is None


@pytest.mark.unit
def test_force_enable_false_优先于已启用的设置(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": True, "host": "127.0.0.1", "port": "7890"})

    assert network_utils.get_proxy_from_settings(force_enable=False) is None


@pytest.mark.unit
def test_force_enable_true_忽略未启用状态(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": False, "host": "10.0.0.1", "port": "8118"})

    assert network_utils.get_proxy_from_settings(force_enable=True) == "http://10.0.0.1:8118"


@pytest.mark.unit
@pytest.mark.parametrize("host,port", [("", "7890"), ("127.0.0.1", ""), ("", "")])
def test_配置不完整时返回_none(monkeypatch, tmp_path, host, port):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": True, "host": host, "port": port})

    assert network_utils.get_proxy_from_settings() is None


@pytest.mark.unit
def test_配置文件不存在时返回_none(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)

    assert network_utils.get_proxy_from_settings() is None


@pytest.mark.unit
def test_配置文件损坏时返回_none_且不抛异常(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    (tmp_path / "settings.json").write_text("{这不是合法 JSON", encoding="utf-8")

    assert network_utils.get_proxy_from_settings() is None


@pytest.mark.unit
def test_websocket_代理与设置读取结果一致(monkeypatch, tmp_path):
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": True, "host": "127.0.0.1", "port": "7890"})

    assert network_utils.get_websocket_proxy() == "http://127.0.0.1:7890"


@pytest.mark.unit
def test_连接器强制关闭且不覆盖_ssl(monkeypatch):
    captured = {}

    def fake_connector(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(network_utils.aiohttp, "TCPConnector", fake_connector)

    network_utils.create_proxy_connector(use_proxy=True)

    assert captured["force_close"] is True
    assert captured["enable_cleanup_closed"] is True
    assert captured["ssl"] is None


@pytest.mark.unit
def test_本地服务会话不读取代理设置(monkeypatch):
    called = []
    created = {}

    def fake_session(**kwargs):
        created.update(kwargs)
        return object()

    def fail_if_called(**kwargs):
        called.append(kwargs)
        raise AssertionError("use_proxy=False 时不应读取代理设置")

    monkeypatch.setattr(network_utils.aiohttp, "TCPConnector", lambda **k: object())
    monkeypatch.setattr(network_utils.aiohttp, "ClientSession", fake_session)
    monkeypatch.setattr(network_utils, "get_proxy_from_settings", fail_if_called)

    network_utils.create_client_session(
        network_utils.aiohttp.ClientTimeout(total=5), use_proxy=False
    )

    assert called == []
    assert created["trust_env"] is False


@pytest.mark.unit
def test_会话读取代理设置的结果不影响会话参数(monkeypatch, tmp_path):
    """记录现状：create_client_session 计算了 proxy_url，但没有传给 ClientSession。

    aiohttp 的代理需要在每次请求上传入，Provider 确实是这样做的
    （见 test_use_proxy_为真时把代理地址传给请求）。此用例锁定会话参数契约，
    避免有人误以为 session 级别已带代理。
    """
    created = {}

    def fake_session(**kwargs):
        created.update(kwargs)
        return object()

    monkeypatch.setattr(network_utils.aiohttp, "TCPConnector", lambda **k: object())
    monkeypatch.setattr(network_utils.aiohttp, "ClientSession", fake_session)
    use_config_dir(monkeypatch, tmp_path)
    write_proxy_settings(tmp_path, {"enabled": True, "host": "127.0.0.1", "port": "7890"})

    network_utils.create_client_session(network_utils.aiohttp.ClientTimeout(total=5))

    assert created["trust_env"] is False
    assert "proxy" not in created
