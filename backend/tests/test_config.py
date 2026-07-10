from app.config import get_settings


def test_default_model_is_glm_4_plus():
    s = get_settings()
    assert s.llm_model == "glm-4-plus"


def test_default_sample_rates():
    s = get_settings()
    assert s.input_sample_rate == 48000
    assert s.output_sample_rate == 16000
