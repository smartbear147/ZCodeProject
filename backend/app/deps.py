"""依赖注入：全局单例服务。"""

from typing import Callable

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.asr_base import AsrSession
from app.services.chat_service import ChatService
from app.services.document_store import DEFAULT_PATH as DOC_PATH, DocumentStore
from app.services.llm import LlmClient  # noqa: F401
from app.services.session import DEFAULT_PATH as SESSION_PATH, SessionStore
from app.services.mimo_asr import MimoAsrSession
from app.services.nls_client import NlsAsrSession
from app.services.token_provider import NlsTokenProvider

# 进程级单例：会话存储，落盘到 data/sessions.json，重启不丢。
_session_store_singleton = SessionStore(path=SESSION_PATH)
# 进程级单例：文档存储（简历/题库），落盘到 data/documents.json，重启不丢。
_document_store_singleton = DocumentStore(path=DOC_PATH)


def get_session_store() -> SessionStore:
    return _session_store_singleton


def get_document_store() -> DocumentStore:
    return _document_store_singleton


def get_llm(settings: Settings = Depends(get_settings)) -> LlmClient:
    return LlmClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )


def get_asr_factory(
    settings: Settings = Depends(get_settings),
) -> Callable[..., AsrSession]:
    """返回一个按当前 ASR_PROVIDER 构造识别会话的工厂函数。

    工厂屏蔽 aliyun / mimo 两家的构造差异（NLS 需 token，MiMo 需 api_key），
    上层 audio.py 只面向 AsrSession 接口；重连时也调用本工厂，对 provider 透明。
    """
    if settings.asr_provider == "mimo":

        def make(on_partial, on_final, loop, on_error=None) -> MimoAsrSession:
            return MimoAsrSession(
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error,
                api_key=settings.mimo_api_key,
                model=settings.mimo_asr_model,
                base_url=settings.mimo_asr_base_url,
                language=settings.mimo_asr_language,
                chunk_seconds=settings.mimo_asr_chunk_seconds,
                loop=loop,
            )

    else:  # aliyun
        # 提到工厂外：首次建连与自动重连共享同一实例，重连复用 token 缓存，
        # 否则每次重连都要重新请求一次 CreateToken（有频控，延长无字幕窗口）。
        token_provider = NlsTokenProvider(
            access_key_id=settings.aliyun_access_key_id,
            access_key_secret=settings.aliyun_access_key_secret,
            region=settings.aliyun_nls_region,
        )

        def make(on_partial, on_final, loop, on_error=None) -> NlsAsrSession:
            token = token_provider.get_token()
            return NlsAsrSession(
                on_partial=on_partial,
                on_final=on_final,
                app_key=settings.aliyun_nls_app_key,
                token=token,
                on_error=on_error,
            )

    return make


def get_chat_service(
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
    doc_store: DocumentStore = Depends(get_document_store),
) -> ChatService:
    return ChatService(llm=get_llm(settings), store=store, doc_store=doc_store)
