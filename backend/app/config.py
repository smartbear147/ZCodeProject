"""配置加载：从环境变量 / .env 读取。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 阿里云 NLS
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_nls_app_key: str = ""
    aliyun_nls_region: str = "cn-shanghai"

    # 智谱 GLM
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-plus"

    # 音频
    input_sample_rate: int = 48000
    output_sample_rate: int = 16000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


def get_settings() -> Settings:
    return Settings()
