"""依赖注入：全局单例服务。

用 lru_cache 保证进程内单例。测试时可通过 app.dependency_overrides 覆盖。
"""

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.llm import LlmClient
from app.services.session import SessionStore
from app.services.suggest import SuggestService
from app.services.token_provider import NlsTokenProvider

# 进程级单例：会话存储本身无配置依赖，直接复用。
_session_store_singleton = SessionStore()


def get_session_store() -> SessionStore:
    return _session_store_singleton


def get_llm(settings: Settings = Depends(get_settings)) -> LlmClient:
    return LlmClient(api_key=settings.zhipu_api_key, model=settings.zhipu_model)


def get_token_provider(
    settings: Settings = Depends(get_settings),
) -> NlsTokenProvider:
    return NlsTokenProvider(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
        region=settings.aliyun_nls_region,
    )


def get_suggest_service(
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
) -> SuggestService:
    return SuggestService(llm=get_llm(settings), store=store)
