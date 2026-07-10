"""测试通用 LLM 客户端（OpenAI 兼容接口，用 mock SDK）。"""

from unittest.mock import MagicMock, patch

from app.services.llm import LlmClient


@patch("app.services.llm.OpenAI")
def test_generate_returns_full_text(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="建议正文"))]
    mock_client.chat.completions.create.return_value = mock_resp

    llm = LlmClient(api_key="fake", base_url="http://test/v1", model="glm-4-plus")
    text = llm.generate(messages=[{"role": "user", "content": "hi"}])
    assert text == "建议正文"
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "glm-4-plus"
    assert kwargs["stream"] is False


@patch("app.services.llm.OpenAI")
def test_stream_yields_delta_chunks(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    def fake_stream(*_args, **_kwargs):
        for chunk_text in ["你", "好", "呀"]:
            m = MagicMock()
            m.choices = [MagicMock(delta=MagicMock(content=chunk_text))]
            yield m

    mock_client.chat.completions.create.side_effect = fake_stream

    llm = LlmClient(api_key="fake", base_url="http://test/v1", model="glm-4-plus")
    chunks = list(llm.stream(messages=[{"role": "user", "content": "hi"}]))
    assert "".join(chunks) == "你好呀"


@patch("app.services.llm.OpenAI")
def test_stream_skips_empty_deltas(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    def fake_stream(*_args, **_kwargs):
        for chunk_text in ["a", "", None, "b"]:
            m = MagicMock()
            m.choices = [MagicMock(delta=MagicMock(content=chunk_text))]
            yield m

    mock_client.chat.completions.create.side_effect = fake_stream

    llm = LlmClient(api_key="fake", base_url="http://test/v1", model="glm-4-plus")
    chunks = list(llm.stream(messages=[{"role": "user", "content": "hi"}]))
    assert chunks == ["a", "b"]
