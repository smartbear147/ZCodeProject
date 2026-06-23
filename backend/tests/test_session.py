"""测试会话状态管理。"""

from app.services.session import SessionStore


def test_new_session_has_empty_state():
    store = SessionStore()
    s = store.create()
    assert s.current_turn_text == ""
    assert s.history_turns == []


def test_append_final_accumulates_into_current_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("你好")
    s.append_final("请自我介绍")
    assert s.current_turn_text == "你好\n请自我介绍"


def test_append_final_ignores_empty_text():
    store = SessionStore()
    s = store.create()
    s.append_final("你好")
    s.append_final("   ")
    assert s.current_turn_text == "你好"


def test_finalize_turn_moves_to_history_and_clears_current():
    store = SessionStore()
    s = store.create()
    s.append_final("讲讲项目")
    s.finalize_turn(suggestion="用 STAR 讲...")
    assert s.current_turn_text == ""
    assert len(s.history_turns) == 1
    assert s.history_turns[0].question == "讲讲项目"
    assert s.history_turns[0].suggestion == "用 STAR 讲..."


def test_clear_history_empties_history_only():
    store = SessionStore()
    s = store.create()
    s.append_final("q1")
    s.finalize_turn(suggestion="a1")
    s.append_final("q2 current")
    s.clear_history()
    assert s.history_turns == []
    # 当前进行中的轮次不动
    assert s.current_turn_text == "q2 current"


def test_store_get_or_create_returns_same_session():
    store = SessionStore()
    s = store.create()
    again = store.get_or_create(s.session_id)
    assert again is s
