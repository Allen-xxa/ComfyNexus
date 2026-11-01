"""OpenAIProvider.chat_stream 的离线回归测试。

用假的 aiohttp 会话替换真实网络请求，验证请求构造、深度思考提示注入、
SSE 解析与错误处理。不访问任何外部 API，不依赖任何真实密钥。

替代原有的 4 个直连 api.xflow.cc 的探针脚本（test_glm_response /
test_glm_response_detail / test_glm_reasoning_control / test_xflow_api）。
"""

import json

import pytest

from backend.src.core.ai.providers import openai_provider as provider_mod
from backend.src.core.ai.providers.openai_provider import OpenAIProvider
from backend.src.core.ai.providers._deep_thinking_prompt import DEEP_THINKING_PROMPT

DONE_LINE = b"data: [DONE]\n"


def sse_line(delta: dict, finish_reason=None) -> bytes:
    """构造一行 SSE 数据，格式与 OpenAI 兼容接口一致"""
    payload = {"choices": [{"delta": delta, "finish_reason": finish_reason}]}
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class FakeResponse:
    """模拟 aiohttp 响应：可异步上下文管理，content 按块产出字节"""

    class _Content:
        def __init__(self, chunks):
            self._chunks = chunks

        async def iter_any(self):
            for chunk in self._chunks:
                yield chunk

    def __init__(self, status: int = 200, body_chunks=(), error_text: str = ""):
        self.status = status
        self._chunks = list(body_chunks)
        self._error_text = error_text
        self.content = FakeResponse._Content(self._chunks)

    async def text(self):
        return self._error_text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    """模拟 aiohttp.ClientSession，记录每次 post 的入参"""

    def __init__(self, response_factory, **kwargs):
        self.closed = False
        self.session_kwargs = kwargs
        self.calls = []
        self._response_factory = response_factory

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self._response_factory()

    async def close(self):
        self.closed = True


def make_provider(**overrides) -> OpenAIProvider:
    config = {
        "api_key": "sk-unit-test-key",
        "base_url": "https://unit.test/v1",
        "model": "unit-model",
        "temperature": 0.3,
    }
    config.update(overrides)
    return OpenAIProvider(config)


def patch_transport(monkeypatch, response_factory):
    """替换 Provider 内部的连接器/代理/会话依赖，返回会话记录列表"""
    sessions = []

    def session_factory(**kwargs):
        session = FakeSession(response_factory, **kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(provider_mod.aiohttp, "ClientSession", session_factory)
    monkeypatch.setattr(provider_mod, "create_proxy_connector", lambda *a, **k: None)
    monkeypatch.setattr(provider_mod, "get_proxy_from_settings", lambda **k: None)
    return sessions


async def collect(provider, messages, **kwargs) -> list:
    chunks = []
    async for chunk in provider.chat_stream(messages, **kwargs):
        chunks.append(chunk)
    return chunks


@pytest.mark.unit
@pytest.mark.asyncio
async def test_请求按配置构造_url_模型_温度与鉴权头(monkeypatch):
    sessions = patch_transport(
        monkeypatch,
        lambda: FakeResponse(200, [sse_line({"content": "ok"}, "stop")]),
    )
    provider = make_provider()

    await collect(provider, [{"role": "user", "content": "你好"}])

    call = sessions[0].calls[0]
    assert call["url"] == "https://unit.test/v1/chat/completions"
    body = call["json"]
    assert body["model"] == "unit-model"
    assert body["temperature"] == 0.3
    assert body["stream"] is True
    assert "max_tokens" not in body
    assert body["messages"] == [{"role": "user", "content": "你好"}]
    assert call["headers"]["Authorization"] == "Bearer sk-unit-test-key"
    assert call["proxy"] is None
    # 会话必须被关闭，否则会泄漏连接
    assert sessions[0].closed is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_仅在配置了_max_tokens_时写入请求体(monkeypatch):
    sessions = patch_transport(monkeypatch, lambda: FakeResponse(200, [DONE_LINE]))
    provider = make_provider(max_tokens=64)

    await collect(provider, [{"role": "user", "content": "hi"}])

    assert sessions[0].calls[0]["json"]["max_tokens"] == 64


@pytest.mark.unit
@pytest.mark.asyncio
async def test_深度思考开启且无系统提示时插入提示词(monkeypatch):
    sessions = patch_transport(monkeypatch, lambda: FakeResponse(200, [DONE_LINE]))
    provider = make_provider()

    await collect(provider, [{"role": "user", "content": "hi"}], deep_thinking=True)

    messages = sessions[0].calls[0]["json"]["messages"]
    assert messages[0] == {"role": "system", "content": DEEP_THINKING_PROMPT}
    assert messages[-1] == {"role": "user", "content": "hi"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_深度思考开启时追加到已有系统提示之后(monkeypatch):
    sessions = patch_transport(monkeypatch, lambda: FakeResponse(200, [DONE_LINE]))
    provider = make_provider()

    await collect(
        provider,
        [{"role": "user", "content": "hi"}],
        system_prompt="你是 ComfyUI 助手",
        deep_thinking=True,
    )

    messages = sessions[0].calls[0]["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith("你是 ComfyUI 助手")
    assert DEEP_THINKING_PROMPT in messages[0]["content"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_深度思考关闭时不注入提示词(monkeypatch):
    sessions = patch_transport(monkeypatch, lambda: FakeResponse(200, [DONE_LINE]))
    provider = make_provider()

    await collect(provider, [{"role": "user", "content": "hi"}], deep_thinking=False)

    messages = sessions[0].calls[0]["json"]["messages"]
    assert [m["role"] for m in messages] == ["user"]
    assert all(DEEP_THINKING_PROMPT not in m["content"] for m in messages)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_use_proxy_为真时把代理地址传给请求(monkeypatch):
    sessions = patch_transport(monkeypatch, lambda: FakeResponse(200, [DONE_LINE]))
    monkeypatch.setattr(
        provider_mod,
        "get_proxy_from_settings",
        lambda **k: "http://127.0.0.1:7890",
    )
    provider = OpenAIProvider(
        {"api_key": "sk-unit-test-key", "model": "unit-model"},
        use_proxy=True,
    )

    await collect(provider, [{"role": "user", "content": "hi"}])

    assert sessions[0].calls[0]["proxy"] == "http://127.0.0.1:7890"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_流式内容按序产出并携带结束原因(monkeypatch):
    body = [
        sse_line({"content": "你"}),
        sse_line({"content": "好"}),
        sse_line({"content": ""}, "stop"),
        DONE_LINE,
    ]
    patch_transport(monkeypatch, lambda: FakeResponse(200, body))
    provider = make_provider()

    chunks = await collect(provider, [{"role": "user", "content": "hi"}])

    assert [c.content for c in chunks] == ["你", "好", ""]
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_非_200_响应抛出包含接口错误信息的异常(monkeypatch):
    error_text = json.dumps({"error": {"message": "invalid api key"}})
    patch_transport(
        monkeypatch,
        lambda: FakeResponse(401, [], error_text=error_text),
    )
    provider = make_provider()

    with pytest.raises(ValueError) as exc_info:
        await collect(provider, [{"role": "user", "content": "hi"}])

    assert "invalid api key" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_http_200_但响应体为空时按风控拦截报错(monkeypatch):
    patch_transport(monkeypatch, lambda: FakeResponse(200, []))
    provider = make_provider()

    with pytest.raises(ValueError, match="风控"):
        await collect(provider, [{"role": "user", "content": "hi"}])
