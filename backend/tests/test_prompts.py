"""测试 system prompt 的文档拼接。"""

from app.prompts import BASE_SYSTEM_PROMPT, build_system_prompt


def test_no_documents_returns_base_prompt():
    prompt = build_system_prompt(resume_text="", qa_text="")
    assert prompt == BASE_SYSTEM_PROMPT
    # 无文档时不应出现文档区标题
    assert "你的简历" not in prompt
    assert "题库" not in prompt


def test_resume_only_appended():
    prompt = build_system_prompt(resume_text="张三的简历内容", qa_text="")
    assert "张三的简历内容" in prompt
    # 只有简历时不应出现题库区
    assert "你准备过的题库" not in prompt


def test_qa_only_appended():
    prompt = build_system_prompt(resume_text="", qa_text="常见问题及答案")
    assert "常见问题及答案" in prompt
    # 只有题库时不应出现简历区
    assert "你的简历（用这里的真实经历作答）" not in prompt


def test_both_appended_with_usage_notes():
    prompt = build_system_prompt(resume_text="简历X", qa_text="题库Y")
    assert "简历X" in prompt
    assert "题库Y" in prompt
    # 新文案：强调"当成我做过的事"和"优先用题库答案"
    assert "当成" in prompt
    assert "优先用题库里你已写好的答案" in prompt


def test_base_prompt_is_direct_answer_not_coaching():
    """基础 prompt 应定位为直接给答案，不是教练指导。

    用正向特征判断：要求"直接给答案""可以立刻念出来""第一人称"。
    """
    assert "直接给答案" in BASE_SYSTEM_PROMPT
    assert "可以立刻念出来" in BASE_SYSTEM_PROMPT
    assert "第一人称" in BASE_SYSTEM_PROMPT
