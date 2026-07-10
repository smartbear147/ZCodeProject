"""测试会话状态管理（单对话历史模型）。"""

import pytest

from app.services.session import SessionStore


def test_new_session_has_empty_state():
    store = SessionStore()
    s = store.create()
    assert s.messages == []
    assert s.subtitle_lines == []


def test_add_message_appends_to_history():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "你好")
    s.add_message("assistant", "你好，有什么可以帮你")
    assert len(s.messages) == 2
    assert s.messages[0].role == "user"
    assert s.messages[0].content == "你好"


def test_add_message_ignores_empty():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "   ")
    assert s.messages == []


def test_clear_messages_empties_history_only():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "hi")
    s.add_subtitle("字幕A")
    s.clear_messages()
    assert s.messages == []
    # 字幕不受影响
    assert s.subtitle_lines == ["字幕A"]


# ---- 字幕区 ----
def test_add_subtitle_appends():
    store = SessionStore()
    s = store.create()
    s.add_subtitle("第一句")
    s.add_subtitle("第二句")
    assert s.subtitle_lines == ["第一句", "第二句"]
    assert s.subtitle_text == "第一句\n第二句"


def test_add_subtitle_ignores_empty():
    store = SessionStore()
    s = store.create()
    s.add_subtitle("有效")
    s.add_subtitle("   ")
    assert s.subtitle_lines == ["有效"]


def test_remove_subtitle_line_deletes_specific():
    store = SessionStore()
    s = store.create()
    s.add_subtitle("第一句")
    s.add_subtitle("第二句")
    s.add_subtitle("第三句")
    assert s.remove_subtitle_line(1) is True
    assert s.subtitle_lines == ["第一句", "第三句"]
    assert s.remove_subtitle_line(1) is True
    assert s.subtitle_lines == ["第一句"]


def test_remove_subtitle_line_out_of_range_returns_false():
    store = SessionStore()
    s = store.create()
    s.add_subtitle("只有一句")
    assert s.remove_subtitle_line(5) is False
    assert s.remove_subtitle_line(-1) is False


def test_clear_subtitles_empties_subtitle_only():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "对话历史")
    s.add_subtitle("字幕1")
    s.add_subtitle("字幕2")
    s.clear_subtitles()
    assert s.subtitle_lines == []
    # 对话历史不受影响
    assert len(s.messages) == 1


def test_consume_subtitles_returns_text_and_clears():
    store = SessionStore()
    s = store.create()
    s.add_subtitle("第一句")
    s.add_subtitle("第二句")
    text = s.consume_subtitles()
    assert text == "第一句\n第二句"
    assert s.subtitle_lines == []


def test_consume_empty_subtitles_returns_empty():
    store = SessionStore()
    s = store.create()
    assert s.consume_subtitles() == ""


def test_store_get_or_create():
    store = SessionStore()
    s = store.create()
    assert store.get_or_create(s.session_id) is s
    assert store.get_or_create("new-id") is not s


# ---- 多会话：标题 / 列表 / 删除 ----
def test_title_auto_set_from_first_user_message():
    store = SessionStore()
    s = store.create()
    assert s.title is None
    s.add_message("assistant", "你好")  # assistant 消息不设标题
    assert s.title is None
    s.add_message("user", "讲讲你做过的最有挑战的项目经历")
    # 短句不截断，整句作标题
    assert s.title == "讲讲你做过的最有挑战的项目经历"


def test_title_truncated_when_over_max_len():
    """超过 24 字的标题截断到 24 字。"""
    from app.services.session import TITLE_MAX_LEN

    store = SessionStore()
    s = store.create()
    long_msg = "这是一段非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的面试官提问内容要被截断"
    s.add_message("user", long_msg)
    assert len(s.title) == TITLE_MAX_LEN
    assert s.title == long_msg[:TITLE_MAX_LEN]


def test_title_set_only_once():
    """标题只在首条 user 消息设置，后续 user 消息不改标题。"""
    store = SessionStore()
    s = store.create()
    s.add_message("user", "第一个问题")
    s.add_message("user", "第二个问题")
    assert s.title == "第一个问题"


def test_list_summaries_sorted_by_updated_desc():
    store = SessionStore()
    a = store.create()
    a.add_message("user", "aaa")
    b = store.create()
    b.add_message("user", "bbb")
    summaries = store.list_summaries()
    assert len(summaries) == 2
    # b 后更新，应排在前
    assert summaries[0]["session_id"] == b.session_id
    assert summaries[0]["title"] == "bbb"
    # 摘要不含完整 messages
    assert "messages" not in summaries[0]


def test_list_summaries_uses_fallback_title_for_new_session():
    store = SessionStore()
    s = store.create()  # 没有任何消息
    summaries = store.list_summaries()
    assert summaries[0]["title"] == "新对话"


def test_delete_session():
    store = SessionStore()
    s = store.create()
    assert store.delete(s.session_id) is True
    assert store.get(s.session_id) is None
    assert store.delete(s.session_id) is False


def test_rename_session():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "原标题")
    s.rename("阿里面试")
    assert s.title == "阿里面试"
