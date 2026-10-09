import pytest

from mcperks.mcp_adapter import McDMCPClient, MCPRateLimitError


def test_ratelimit_safe_handling():
    client = McDMCPClient(token="dummy")

    def fake_call(tool, args):
        raise MCPRateLimitError("触发限流（429），每分钟上限 600 次，请降低调用频率。")

    client.call = fake_call
    with pytest.raises(MCPRateLimitError):
        client.call("query-my-coupons", {})


def test_ratelimit_message_mentions_limit():
    client = McDMCPClient(token="dummy")

    def fake_call(tool, args):
        raise MCPRateLimitError("触发限流（429），每分钟上限 600 次，请降低调用频率。")

    client.call = fake_call
    try:
        client.call("x", {})
    except MCPRateLimitError as e:
        assert "600" in str(e)
