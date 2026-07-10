"""对话（SSE 流式）+ 重置 + 字幕操作 路由。

简化后的模型：
- /api/chat：发一条消息给 LLM。可选手打 message，或 send_subtitles=True 把字幕区全发。
- /api/reset：清空整个对话历史。
- /api/subtitle/*：操作字幕区（删一行/清空）。
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import get_chat_service, get_session_store
from app.schemas import (
    ChatRequest,
    ClearSubtitleRequest,
    RemoveSubtitleLineRequest,
    RenameSessionRequest,
    ResetRequest,
    SessionDetail,
    SessionMessage,
)
from app.services.chat_service import ChatService
from app.services.session import SessionStore

router = APIRouter(prefix="/api")


@router.post("/session")
def create_session_endpoint(store: SessionStore = Depends(get_session_store)) -> dict:
    """创建一个新会话，返回 session_id。

    让对话/字幕不依赖音频采集：页面加载时即可创建会话。
    音频 WS 连接时会复用同一个 session_id（字幕进同一会话）。
    """
    session = store.create()
    return {"session_id": session.session_id}


@router.get("/sessions")
def list_sessions_endpoint(store: SessionStore = Depends(get_session_store)) -> dict:
    """列出所有会话摘要（id/title/updated_at），按更新时间倒序。"""
    return {"sessions": store.list_summaries()}


@router.get("/session/{session_id}", response_model=SessionDetail)
def get_session_endpoint(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
) -> SessionDetail:
    """获取某个会话的完整内容（切换会话时加载历史）。"""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionDetail(
        session_id=session.session_id,
        title=session.title,
        messages=[
            SessionMessage(role=m.role, content=m.content) for m in session.messages
        ],
        subtitle_lines=list(session.subtitle_lines),
    )


@router.delete("/session/{session_id}")
def delete_session_endpoint(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    """删除某个会话。"""
    ok = store.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "deleted": True}


@router.post("/session/rename")
def rename_session_endpoint(
    req: RenameSessionRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    """重命名某个会话。"""
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.rename(req.title)
    store.save(req.session_id)
    return {"session_id": req.session_id, "title": session.title or "新对话"}


@router.post("/chat")
def chat_endpoint(
    req: ChatRequest,
    store: SessionStore = Depends(get_session_store),
    svc: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """发一条消息，流式返回 LLM 回复。

    - send_subtitles=True：把字幕区全部内容打包为 user 消息，并清空字幕区。
    - 否则用 message 作为 user 消息内容。
    """
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    if req.send_subtitles:
        user_content = session.consume_subtitles()
        store.save(req.session_id)  # 字幕已消费，落盘
    else:
        user_content = req.message.strip()

    if not user_content:
        raise HTTPException(status_code=400, detail="没有可发送的内容")

    def event_stream():
        try:
            for delta in svc.chat_stream(req.session_id, user_content):
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/reset")
def reset_endpoint(
    req: ResetRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    """清空整个对话历史（字幕区不动）。"""
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.clear_messages()
    store.save(req.session_id)
    return {"session_id": req.session_id, "reset": True}


@router.post("/subtitle/remove-line")
def remove_line_endpoint(
    req: RemoveSubtitleLineRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    """删除字幕区某一行。"""
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    ok = session.remove_subtitle_line(req.line_index)
    if not ok:
        raise HTTPException(status_code=400, detail="行号越界")
    store.save(req.session_id)
    return {
        "session_id": req.session_id,
        "remaining_lines": list(session.subtitle_lines),
    }


@router.post("/subtitle/clear")
def clear_subtitle_endpoint(
    req: ClearSubtitleRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    """清空字幕区（不影响对话历史）。"""
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.clear_subtitles()
    store.save(req.session_id)
    return {"session_id": req.session_id, "cleared": True}
