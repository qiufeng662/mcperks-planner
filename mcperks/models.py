"""数据模型定义。

这些模型是麦门权益管家（McPerks Planner）内部使用的规范化数据结构。
它们既可以由 WorkBuddy 在调用麦当劳 MCP 后提取生成，也可以由单元测试直接构造。

所有从外部（如 MCP 返回）进入的数据都先归一化为这些模型，
缺失的字段一律置为 None 并标记为「未知」，绝不臆造。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _to_float(value: Any) -> Optional[float]:
    """将可能为字符串/None 的字段安全地转为 float；无法转换返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _to_int(value: Any) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


@dataclass
class Coupon:
    """一张优惠券（来源可以是：我的卡包 / 可领取 / 指定门店可用）。"""

    id: str
    title: str = ""
    source: str = "unknown"  # my | available | store | unknown
    status: str = ""  # 可用 | 可领取 | 已使用 | 未知
    expire_at: Optional[str] = None  # ISO 日期 YYYY-MM-DD，未知为 None
    value_type: str = "unknown"  # fixed(满减/直减) | percent(折扣) | unknown
    value: Optional[float] = None  # 面值/折扣率，未知为 None
    min_spend: Optional[float] = None  # 使用门槛，未知为 None
    applicable_categories: list[str] = field(default_factory=list)
    applicable_store: Optional[str] = None  # 门店编码或名称，未知为 None
    conditions: str = ""  # 适用条件自由文本
    raw: dict = field(default_factory=dict)  # 原始数据，便于追溯

    @property
    def has_expiry(self) -> bool:
        return self.expire_at is not None

    @property
    def is_unknown_value(self) -> bool:
        return self.value is None or self.value_type == "unknown"

    @classmethod
    def from_dict(cls, d: dict) -> "Coupon":
        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            source=str(d.get("source", "unknown")),
            status=str(d.get("status", "")),
            expire_at=d.get("expire_at"),
            value_type=str(d.get("value_type", "unknown")),
            value=_to_float(d.get("value")),
            min_spend=_to_float(d.get("min_spend")),
            applicable_categories=list(d.get("applicable_categories", []) or []),
            applicable_store=d.get("applicable_store"),
            conditions=str(d.get("conditions", "")),
            raw=d.get("raw", d),
        )


@dataclass
class PointsAccount:
    """积分账户。account_id 等敏感字段在外部传入时应已脱敏。"""

    available: float = 0.0
    accumulative: float = 0.0
    frozen: float = 0.0
    expired: float = 0.0
    current_month_expire: float = 0.0  # 本月将过期
    next_month_expire: float = 0.0  # 下月将过期
    currency: str = ""
    account_id_masked: Optional[str] = None  # 已脱敏的账户标识，可为 None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "PointsAccount":
        return cls(
            available=_to_float(d.get("available", d.get("availablePoint"))) or 0.0,
            accumulative=_to_float(d.get("accumulative", d.get("accumulativePoint"))) or 0.0,
            frozen=_to_float(d.get("frozen", d.get("frozenPoint"))) or 0.0,
            expired=_to_float(d.get("expired", d.get("expiredPoint"))) or 0.0,
            current_month_expire=_to_float(
                d.get("current_month_expire", d.get("currentMouthExpirePoint"))
            ) or 0.0,
            next_month_expire=_to_float(
                d.get("next_month_expire", d.get("nextMouthExpirePoint"))
            ) or 0.0,
            currency=str(d.get("currency", "")),
            account_id_masked=d.get("account_id_masked"),
            raw=d,
        )


@dataclass
class Campaign:
    """营销活动（来自活动日历）。"""

    date: str = ""  # YYYY-MM-DD
    status: str = "unknown"  # past | today | future | ongoing | unknown
    title: str = ""
    description: str = ""
    image: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Campaign":
        return cls(
            date=str(d.get("date", "")),
            status=str(d.get("status", "unknown")),
            title=str(d.get("title", "")),
            description=str(d.get("description", "")),
            image=str(d.get("image", "")),
            raw=d,
        )


@dataclass
class Meal:
    """餐品（来自餐品列表/详情）。价格单位：元。"""

    code: str
    name: str = ""
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    discount_type: Optional[str] = None
    can_with_order: bool = False
    with_order: Optional[dict] = None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Meal":
        return cls(
            code=str(d.get("code", "")),
            name=str(d.get("name", "")),
            current_price=_to_float(d.get("current_price", d.get("currentPrice"))),
            original_price=_to_float(d.get("original_price", d.get("originalPrice"))),
            discount_type=d.get("discount_type", d.get("discountType")),
            can_with_order=bool(d.get("can_with_order", d.get("canWithOrder", False))),
            with_order=d.get("with_order", d.get("withOrder")),
            raw=d,
        )


@dataclass
class PriceResult:
    """价格核算结果。麦当劳 MCP 返回单位为「分」，此处统一转为「元」。"""

    original_price: float  # 原价（元）
    discount: float  # 优惠金额（元）
    actual_price: float  # 实际应付（元）
    product_original: float = 0.0
    product_price: float = 0.0
    packing_fee: Optional[float] = None  # 打包费（元），未知为 None
    delivery_fee: Optional[float] = None  # 配送费（元）
    tableware_fee: Optional[float] = None  # 餐具费（元）
    uncertain_fees: list[str] = field(default_factory=list)  # 尚未确认的费用说明
    confirmed: bool = True  # 是否来自真实 calculate-price
    raw: dict = field(default_factory=dict)


@dataclass
class PlanItem:
    """规划建议中的一条动作。"""

    action: str
    coupon_id: Optional[str] = None
    coupon_title: Optional[str] = None
    reason: str = ""
    estimated_saving: Optional[float] = None  # 保守估算可省金额（元），未知为 None
    deadline: Optional[str] = None  # 建议最晚使用日
    confidence: str = "medium"  # high | medium | low


@dataclass
class Plan:
    """一份权益使用规划结果。"""

    mode: str = "inventory"  # inventory | budget | multi_day
    recommended: list[PlanItem] = field(default_factory=list)
    estimated_total_saving: Optional[float] = None
    budget: Optional[float] = None
    price_confirmed: bool = False  # 是否经过真实 calculate-price 核对
    notes: list[str] = field(default_factory=list)
    generated_at: Optional[str] = None


@dataclass
class InventoryReport:
    """权益盘点报告。"""

    my_coupons: list[Coupon] = field(default_factory=list)
    available_coupons: list[Coupon] = field(default_factory=list)
    store_coupons: list[Coupon] = field(default_factory=list)
    points: Optional[PointsAccount] = None
    campaigns: list[Campaign] = field(default_factory=list)
    expiring_soon: list[Coupon] = field(default_factory=list)
    no_expiry_info: list[Coupon] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None
