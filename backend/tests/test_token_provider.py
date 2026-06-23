"""测试阿里云 NLS Token Provider（mock create_token）。"""

import time
from unittest.mock import patch

from app.services.token_provider import NlsTokenProvider, REFRESH_AHEAD_SECONDS


@patch("app.services.token_provider.create_token")
def test_get_token_caches_until_expiry(mock_create):
    mock_create.return_value = ("TOKEN_ABC", int(time.time()) + 3600)
    provider = NlsTokenProvider(
        access_key_id="ak", access_key_secret="sk", region="cn-shanghai"
    )
    assert provider.get_token() == "TOKEN_ABC"
    # 第二次应命中缓存，不再调 create_token
    assert provider.get_token() == "TOKEN_ABC"
    assert mock_create.call_count == 1


@patch("app.services.token_provider.create_token")
def test_get_token_refreshes_when_near_expiry(mock_create):
    # 过期时间只剩很少（小于 REFRESH_AHEAD_SECONDS 提前量）
    mock_create.return_value = ("TOKEN_OLD", int(time.time()) + (REFRESH_AHEAD_SECONDS - 10))
    provider = NlsTokenProvider(
        access_key_id="ak", access_key_secret="sk", region="cn-shanghai"
    )
    assert provider.get_token() == "TOKEN_OLD"
    mock_create.return_value = ("TOKEN_NEW", int(time.time()) + 3600)
    assert provider.get_token() == "TOKEN_NEW"
    assert mock_create.call_count == 2


@patch("app.services.token_provider.create_token")
def test_get_token_refreshes_when_expired(mock_create):
    mock_create.return_value = ("TOKEN_OLD", int(time.time()) - 100)  # 已过期
    provider = NlsTokenProvider(
        access_key_id="ak", access_key_secret="sk", region="cn-shanghai"
    )
    provider.get_token()
    mock_create.return_value = ("TOKEN_FRESH", int(time.time()) + 3600)
    assert provider.get_token() == "TOKEN_FRESH"
    assert mock_create.call_count == 2
