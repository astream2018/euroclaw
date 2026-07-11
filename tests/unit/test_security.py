from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.security import get_current_user


@patch("src.security.get_public_keys")
@patch("src.security.jwt.decode")
def test_get_current_user_returns_claims(mock_decode, mock_public_keys):
    mock_public_keys.return_value = {"keys": []}
    mock_decode.return_value = {
        "sub": "user-123",
        "realm_access": {"roles": ["admin"]},
        "email": "ops@example.com",
    }

    result = get_current_user("sample-token")

    assert result["user_id"] == "user-123"
    assert result["roles"] == ["admin"]
    assert result["email"] == "ops@example.com"


@patch("src.security.get_public_keys")
@patch("src.security.jwt.decode")
def test_get_current_user_rejects_invalid_token(mock_decode, mock_public_keys):
    mock_public_keys.return_value = {"keys": []}
    mock_decode.side_effect = Exception("invalid token")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user("bad-token")

    assert exc_info.value.status_code == 401
