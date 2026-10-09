"""MCP 接入适配层。

本模块做两件事：

1. 把麦当劳 MCP 真实返回的 JSON（即 WorkBuddy 调用工具后展示的「Original Response」）
   解析 / 归一化为本项目内部模型，便于后续确定性计算。
   已通过真实返回结构验证的字段见各函数 docstring。

2. 提供一个可选的「直连 MCP」客户端 McDMCPClient（Streamable HTTP），
   供非 WorkBuddy 的 Agent 平台复用。该客户端依赖环境变量 MCD_MCP_TOKEN，
   在本项目中并非必须（WorkBuddy 通过内置 MCP 工具调用），
   且其网络行为不在 pytest 覆盖范围内（标记为「尚未在自动化测试中实跑」）。

注意：所有解析函数都对缺失字段返回 None / 空，绝不臆造数据。
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .models import (
    Campaign,
    Coupon,
    Meal,
    PointsAccount,
    _parse_date,
)
from .core import reconcile_price, PriceCalcUnavailable


def _dig(data: dict, *path, default=None):
    """安全地按路径取嵌套字段。"""
    cur: Any = data
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def parse_account(raw: dict) -> PointsAccount:
    """解析 query-my-account 的真实返回。

    已验证真实返回结构（2026-10-09 实调）：
    {"success":true,"code":200,"data":{
        "availablePoint":"0","accountId":"...","accumulativePoint":"0",
        "currency":"麦享会积分","currentMouthExpirePoint":"0",
        "expiredPoint":"0","frozenPoint":"0","lastMouthExpirePoint":"0",
        "nextMouthExpirePoint":"0","usedPoint":"0"}}

    accountId 属于敏感信息，这里直接丢弃，不进入任何模型。
    """
    d = _dig(raw, "data", default=raw)
    return PointsAccount.from_dict(
        {
            "available": d.get("availablePoint"),
            "accumulative": d.get("accumulativePoint"),
            "frozen": d.get("frozenPoint"),
            "expired": d.get("expiredPoint"),
            "current_month_expire": d.get("currentMouthExpirePoint"),
            "next_month_expire": d.get("nextMouthExpirePoint"),
            "currency": d.get("currency"),
            "account_id_masked": None,  # 敏感字段，不保留
        }
    )


def parse_calculate_price(raw: dict) -> dict:
    """解析 calculate-price 的真实返回（data 段）。

    已验证真实返回含（单位均为「分」）：
    productOriginalPrice, productPrice, deliveryOriginalPrice, deliveryPrice,
    packingOriginalPrice, packingPrice, tablewarePrice, originalPrice,
    discount, price, productList, takeWayList, mealAssistanceList, enjoyed, enjoyable

    直接复用 core.reconcile_price 转换为「元」。
    """
    data = _dig(raw, "data", default=raw)
    return reconcile_price(data)


def coupon_from_dict(d: dict, source: str = "unknown") -> Coupon:
    """从规范化 dict 构造 Coupon（WorkBuddy 调用 MCP 后提取的结构）。"""
    d = dict(d)
    d.setdefault("source", source)
    return Coupon.from_dict(d)


def campaign_from_dict(d: dict) -> Campaign:
    return Campaign.from_dict(d)


def meal_from_dict(d: dict) -> Meal:
    return Meal.from_dict(d)


def classify_campaign_status(campaign_date: str, now=None) -> str:
    """依据活动日期相对今天的关系给出状态。"""
    from datetime import datetime, timedelta

    now = now or datetime.now()
    cd = _parse_date(campaign_date)
    if cd is None:
        return "unknown"
    if cd.date() < now.date():
        return "past"
    if cd.date() == now.date():
        return "today"
    if cd.date() <= (now + timedelta(days=7)).date():
        return "future"
    return "future"


class McDMCPClient:
    """可选的直连麦当劳 MCP 客户端（Streamable HTTP）。

    仅当环境变量 MCD_MCP_TOKEN 存在时可用。WorkBuddy 场景下一般无需使用——
    由 WorkBuddy 的 MCP 工具直接调用。此客户端的网络调用不在 pytest 覆盖范围内。

    使用方式：
        client = McDMCPClient()  # 自动读取 MCD_MCP_TOKEN 与 MCD_MCP_URL
        resp = client.call("query-my-account", {})
    """

    DEFAULT_URL = "https://mcp.mcd.cn"

    def __init__(self, token: Optional[str] = None, url: Optional[str] = None):
        self.token = token or os.environ.get("MCD_MCP_TOKEN")
        self.url = url or os.environ.get("MCD_MCP_URL", self.DEFAULT_URL)
        if not self.token:
            raise RuntimeError(
                "未提供 MCP Token：请设置环境变量 MCD_MCP_TOKEN，"
                "或在 WorkBuddy 中直接通过内置 mcd-mcp 工具调用。"
            )

    def call(self, tool_name: str, arguments: dict) -> dict:
        """通过 Streamable HTTP 调用 MCP 工具（最小实现，依赖 requests）。"""
        try:
            import requests  # type: ignore
        except ImportError as e:  # pragma: no cover - 依赖可选
            raise RuntimeError("直连客户端需要 requests 库：pip install requests") from e

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = requests.post(self.url, headers=headers, json=payload, timeout=20)
        err = error_for_status(resp.status_code)
        if err:
            raise err
        resp.raise_for_status()
        return resp.json()


def error_for_status(status_code: int) -> Optional[Exception]:
    """将 HTTP 状态码映射为对应的 MCP 异常；非错误返回 None。"""
    if status_code == 401:
        return MCPAuthError("MCP Token 无效或已过期（401），请检查 Authorization 与 Token 配置。")
    if status_code == 429:
        return MCPRateLimitError("触发限流（429），每分钟上限 600 次，请降低调用频率。")
    return None


class MCPAuthError(Exception):
    pass


class MCPRateLimitError(Exception):
    pass


def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
