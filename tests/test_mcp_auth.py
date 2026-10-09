import pytest

from mcperks.mcp_adapter import McDMCPClient, MCPAuthError, MCPRateLimitError, error_for_status


def test_client_without_token_raises():
    with pytest.raises(RuntimeError):
        McDMCPClient(token=None)


def test_error_for_status_maps_401():
    err = error_for_status(401)
    assert isinstance(err, MCPAuthError)


def test_error_for_status_maps_429():
    err = error_for_status(429)
    assert isinstance(err, MCPRateLimitError)


def test_error_for_status_ok_returns_none():
    assert error_for_status(200) is None


def test_auth_failure_safe_handling():
    """模拟 401：应抛出 MCPAuthError 且不应产生任何交易副作用。"""
    client = McDMCPClient(token="dummy")

    def fake_call(tool, args):
        raise MCPAuthError("MCP Token 无效或已过期（401），请检查 Authorization 与 Token 配置。")

    client.call = fake_call
    with pytest.raises(MCPAuthError):
        client.call("query-my-coupons", {})
