"""测试 deps.get_asr_factory：按 ASR_PROVIDER 选择实现 + NLS token 缓存复用。

aliyun 分支的 NlsTokenProvider 必须在工厂外只建一次（回归防护）：
首次建连与 _on_asr_close 自动重连共享同一实例，重连直接命中内存缓存，
不会每次重连都发起一次 CreateToken 网络请求（有频控，延长无字幕窗口）。
"""

from app.config import Settings
from app.deps import get_asr_factory
from app.services.mimo_asr import MimoAsrSession
from app.services.nls_client import NlsAsrSession


def test_factory_mimo_branch():
    settings = Settings(asr_provider="mimo", mimo_api_key="k")
    factory = get_asr_factory(settings)
    session = factory(on_partial=None, on_final=None, loop=None)
    assert isinstance(session, MimoAsrSession)


def test_factory_aliyun_branch_shares_token_provider(monkeypatch):
    calls = []

    class FakeProvider:
        def __init__(self, **kwargs):
            calls.append("init")

        def get_token(self):
            calls.append("get")
            return "fake-token"

    monkeypatch.setattr("app.deps.NlsTokenProvider", FakeProvider)

    settings = Settings(asr_provider="aliyun", aliyun_nls_app_key="app-key")
    factory = get_asr_factory(settings)
    assert calls == ["init"]  # provider 在拿到工厂时就已建好，且只建一次

    s1 = factory(on_partial=None, on_final=None, loop=None)
    s2 = factory(on_partial=None, on_final=None, loop=None)  # 模拟自动重连

    assert isinstance(s1, NlsAsrSession) and isinstance(s2, NlsAsrSession)
    # provider 没有重复构造；两次 make 都走同一实例的 get_token（内部有缓存）
    assert calls == ["init", "get", "get"]
