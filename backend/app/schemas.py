"""Pydantic 数据模型（请求/响应/内部）。

简化后的模型：所有交互都是"在对话历史里加一条消息"。
"""

from pydantic import BaseModel


class Message(BaseModel):
    """对话历史中的一条消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """发送一条消息给 LLM（流式回复）。

    - send_subtitles=True 时：把字幕区全部内容作为这条 user 消息，
      并清空字幕区。message 字段忽略。
    - 否则：用 message 作为这条 user 消息（手打的）。
    """

    session_id: str
    message: str = ""
    send_subtitles: bool = False


class ResetRequest(BaseModel):
    """清空整个对话历史。"""

    session_id: str


class RemoveSubtitleLineRequest(BaseModel):
    """删除字幕区某一行。"""

    session_id: str
    line_index: int


class ClearSubtitleRequest(BaseModel):
    """清空字幕区。"""

    session_id: str


class RenameSessionRequest(BaseModel):
    """重命名会话。"""

    session_id: str
    title: str


class SessionMessage(BaseModel):
    """会话详情里的一条消息（给前端回显历史用）。"""

    role: str
    content: str


class SessionDetail(BaseModel):
    """会话详情（切换会话时加载）。"""

    session_id: str
    title: str | None
    messages: list[SessionMessage]
    subtitle_lines: list[str]


class DocumentInfo(BaseModel):
    """文档元信息（列表/响应用，不含全文）。"""

    id: str
    filename: str
    doc_type: str  # "resume" | "qa"
    size_bytes: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
