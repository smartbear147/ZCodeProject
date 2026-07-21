"""配置加载：从环境变量 / .env 读取。"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ASR 引擎切换：aliyun（阿里云 NLS 流式）/ mimo（小米 MiMo 分块转写）
    # Literal 校验：拼错（如 Mimo）会在启动时直接报错，而不是静默回落 aliyun
    asr_provider: Literal["aliyun", "mimo"] = "aliyun"

    # 阿里云 NLS
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_nls_app_key: str = ""
    aliyun_nls_region: str = "cn-shanghai"

    # 小米 MiMo ASR（OpenAI 兼容接口）
    mimo_api_key: str = ""
    mimo_asr_model: str = "mimo-v2.5-asr"
    mimo_asr_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_asr_language: str = "auto"
    mimo_asr_chunk_seconds: float = 4.0

    # LLM（OpenAI 兼容接口，适用于智谱/小米 MiMo/DeepSeek/本地 Ollama 等）
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-plus"

    # 音频
    input_sample_rate: int = 48000
    output_sample_rate: int = 16000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


def get_settings() -> Settings:
    return Settings()
