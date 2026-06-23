"""生成建议（同步）+ 追问（SSE 流式）+ 清空历史 路由。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import get_llm, get_session_store, get_suggest_service
from app.prompts import SYSTEM_PROMPT
from app.schemas import SuggestRequest, SuggestResponse
from app.services.llm import LlmClient
from app.services.session import SessionStore
from app.services.suggest import CURRENT_TURN_PREFIX, SuggestService

router = APIRouter(prefix="/api")


@router.post("/suggest", response_model=SuggestResponse)
def suggest_endpoint(
    req: SuggestRequest,
    store: SessionStore = Depends(get_session_store),
    svc: SuggestService = Depends(get_suggest_service),
) -> SuggestResponse:
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    question_snapshot = session.current_turn_text
    try:
        suggestion = svc.suggest(req.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")
    return SuggestResponse(
        session_id=req.session_id,
        suggestion=suggestion,
        question=question_snapshot,
    )


@router.post("/clear")
def clear_endpoint(
    req: SuggestRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.clear_history()
    return {"session_id": req.session_id, "cleared": True}


@router.get("/ask")
def ask_endpoint(
    session_id: str,
    message: str,
    store: SessionStore = Depends(get_session_store),
    llm: LlmClient = Depends(get_llm),
) -> StreamingResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    # 组装追问的 messages：system + 历史轮次 + 用户追问
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in session.history_turns:
        messages.append({"role": "user", "content": CURRENT_TURN_PREFIX + turn.question})
        messages.append({"role": "assistant", "content": turn.suggestion})
    messages.append({"role": "user", "content": message})

    async def event_stream():
        try:
            for delta in llm.stream(messages):
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
