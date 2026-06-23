"""测试生成建议 / 追问 / 清空 路由。"""

import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.deps import get_llm, get_session_store, get_suggest_service
from app.main import app
from app.services.session import SessionStore
from app.services.suggest import SuggestService


def _setup_session_with_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("讲讲项目")
    app.dependency_overrides[get_session_store] = lambda: store
    return store, s


def test_suggest_endpoint_returns_suggestion():
    store, s = _setup_session_with_turn()
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "用 STAR 回答"
    svc = SuggestService(llm=fake_llm, store=store)
    app.dependency_overrides[get_suggest_service] = lambda: svc

    client = TestClient(app)
    resp = client.post("/api/suggest", json={"session_id": s.session_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggestion"] == "用 STAR 回答"
    assert body["question"] == "讲讲项目"
    # 轮次已结转
    assert s.current_turn_text == ""
    app.dependency_overrides.clear()


def test_suggest_unknown_session_returns_404():
    _setup_session_with_turn()
    client = TestClient(app)
    resp = client.post("/api/suggest", json={"session_id": "nonexistent"})
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_clear_endpoint_clears_history_only():
    store, s = _setup_session_with_turn()
    s.finalize_turn(suggestion="a")
    s.append_final("当前")

    client = TestClient(app)
    resp = client.post("/api/clear", json={"session_id": s.session_id})
    assert resp.status_code == 200
    assert s.history_turns == []
    # 当前进行中的轮次不动
    assert s.current_turn_text == "当前"
    app.dependency_overrides.clear()


def test_ask_endpoint_streams_chunks():
    store, s = _setup_session_with_turn()
    s.finalize_turn(suggestion="原始建议")
    fake_llm = MagicMock()
    fake_llm.stream.return_value = iter(["你", "好"])
    app.dependency_overrides[get_llm] = lambda: fake_llm

    client = TestClient(app)
    with client.stream(
        "GET",
        "/api/ask",
        params={"session_id": s.session_id, "message": "再详细"},
    ) as resp:
        assert resp.status_code == 200
        deltas = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                deltas.append(json.loads(line[6:])["delta"])
    assert "".join(deltas) == "你好"
    app.dependency_overrides.clear()


def test_ask_unknown_session_returns_404():
    _setup_session_with_turn()
    client = TestClient(app)
    resp = client.get(
        "/api/ask", params={"session_id": "nonexistent", "message": "hi"}
    )
    assert resp.status_code == 404
    app.dependency_overrides.clear()
