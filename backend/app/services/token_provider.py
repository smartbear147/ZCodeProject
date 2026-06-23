"""阿里云 NLS Token 获取与刷新。

NLS 实时识别需要一个临时 Token（通过 AccessKey 换取），有效期约一段时间。
这里做缓存，并在过期前 REFRESH_AHEAD_SECONDS 提前刷新。
"""

import json
import time

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

REFRESH_AHEAD_SECONDS = 60


def create_token(access_key_id: str, access_key_secret: str, region: str) -> tuple[str, int]:
    """调用阿里云元数据接口换 NLS Token。返回 (token, expire_timestamp)。"""
    client = AcsClient(access_key_id, access_key_secret, region)
    request = CommonRequest()
    request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
    request.set_version("2019-02-28")
    request.set_action_name("CreateToken")
    request.set_method("POST")
    response = client.do_action_with_exception(request)
    data = json.loads(response)
    token = data["Token"]["Id"]
    expire = data["Token"]["ExpireTime"]
    return token, expire


class NlsTokenProvider:
    def __init__(self, access_key_id: str, access_key_secret: str, region: str) -> None:
        self._ak = access_key_id
        self._sk = access_key_secret
        self._region = region
        self._token: str | None = None
        self._expire_at: float = 0.0

    def get_token(self) -> str:
        """返回有效 token；过期或临近过期则刷新。"""
        now = time.time()
        if self._token is None or now >= self._expire_at - REFRESH_AHEAD_SECONDS:
            self._token, expire = create_token(self._ak, self._sk, self._region)
            self._expire_at = float(expire)
        return self._token
