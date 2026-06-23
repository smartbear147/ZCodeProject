"""依赖注入：全局单例服务。

用 lru_cache 保证进程内单例。测试时可通过 app.dependency_overrides 覆盖。
"""

from functools import lru_cache

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.llm import LlmClient
from app.services.session import SessionStore
from app.services.suggest import SuggestService
from app.services.token_provider import NlsTokenProvider


@lru_cache
def get_session_store() -> SessionStore:
    return SessionStore()


@lru_cache
def get_llm(settings: Settings = Depends(get_settings)) -> LlmClient:
    return LlmClient(api_key=settings.zhipu_api_key, model=settings.zhipu_model)


@lru_cache
def get_token_provider(
    settings: Settings = Depends(get_settings),
) -> NlsTokenProvider:
    return NlsTokenProvider(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
        region=settings.aliyun_nls_region,
    )


@lru_cache
def get_suggest_service(
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
) -> SuggestService:
    llm = get_llm(settings)
    return SuggestService(llm=llm, store=store)
