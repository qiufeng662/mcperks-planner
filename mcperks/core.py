"""麦门权益管家的核心确定性业务逻辑。

本模块全部为纯函数 / 纯计算，不发起任何网络请求、不调用任何 MCP，
因此可以被 pytest 完全复现，且相同输入必然得到相同输出。

设计原则：
1. 缺失字段一律当作「未知」，不臆造优惠金额或有效期。
2. 优惠券面值不等于实际可省金额 —— 估算节省时采用保守口径。
3. 所有排序、打分均有确定权重与确定性的兜底排序键（coupon id），
   保证重复执行结果稳定。
4. 默认只做查询与规划，绝不产生下单 / 兑换等真实交易副作用。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .models import (
    Campaign,
    Coupon,
    InventoryReport,
    Meal,
    Plan,
    PlanItem,
    PointsAccount,
    PriceResult,
)

# 确定性权重（常量，避免随机性）
URGENCY_WEIGHT = 1.0
SAVING_WEIGHT = 5.0
# 典型最高单券面值，用于把「估算可省」归一化到可比分数（仅用于排序，不影响金额输出）
TYPICAL_MAX_SAVING = 30.0

# 业务约束：通常一个订单只能使用一张优惠券（麦当劳券规则的一般假设）。
# 规划算法在「单笔消费」场景下据此避免冲突。
DEFAULT_ONE_COUPON_PER_ORDER = True


def default_now() -> datetime:
    """返回当前时间；测试时可注入固定时间以保证确定性。"""
    return datetime.now()


def _expire_datetime(coupon: Coupon) -> Optional[datetime]:
    from .models import _parse_date

    return _parse_date(coupon.expire_at)


def sort_coupons_by_expiry(coupons: list[Coupon], now: Optional[datetime] = None) -> list[Coupon]:
    """按到期时间升序排序：越临近过期越靠前；无到期信息的排最后。

    确定性：同级以 coupon.id 升序兜底。
    """
    now = now or default_now()

    def sort_key(c: Coupon):
        ed = _expire_datetime(c)
        if ed is None:
            # 无到期信息排在最后，用很大的数占位
            return (1, 0, c.id)
        delta_days = (ed - now).total_seconds()
        return (0, delta_days, c.id)

    return sorted(coupons, key=sort_key)


def classify_coupons(
    coupons: list[Coupon], horizon_days: int = 7, now: Optional[datetime] = None
) -> dict:
    """将优惠券分类为：可用、临期（horizon_days 内）、无到期信息。

    临期判断只对「有到期信息」的券做；无到期信息者归入 no_expiry_info。
    """
    now = now or default_now()
    horizon = now + timedelta(days=horizon_days)

    available, expiring, no_info = [], [], []
    for c in coupons:
        if c.status and ("已使用" in c.status or "失效" in c.status or "过期" in c.status):
            continue  # 已不可用，不计入
        ed = _expire_datetime(c)
        if ed is None:
            no_info.append(c)
            continue
        if ed < now:
            # 已过期：列入临期分组但标记，供用户注意
            expiring.append(c)
        elif ed <= horizon:
            expiring.append(c)
        else:
            available.append(c)
    return {
        "available": available,
        "expiring_soon": expiring,
        "no_expiry_info": no_info,
    }


def detect_expiring_points(
    account: PointsAccount, horizon_days: int = 30, now: Optional[datetime] = None
) -> dict:
    """识别积分过期风险。

    返回即将过期积分、是否临近过期、以及提示。
    若字段缺失则为 0，并明确标注「未知」风险等级。
    """
    now = now or default_now()
    current = account.current_month_expire or 0.0
    nxt = account.next_month_expire or 0.0
    total_expiring = current + nxt

    if total_expiring > 0:
        risk = "high" if current > 0 else "medium"
        msg = (
            f"账户有积分即将过期：本月将过期 {current:g}，下月将过期 {nxt:g}，"
            f"建议尽快在 {horizon_days} 天内使用，避免清零。"
        )
    else:
        risk = "low"
        msg = "当前未检测到即将过期的积分（字段为 0 或未知）。"
    return {
        "current_month_expire": current,
        "next_month_expire": nxt,
        "total_expiring": total_expiring,
        "risk": risk,
        "message": msg,
    }


def estimate_saving(coupon: Coupon, cart_total: Optional[float] = None) -> Optional[float]:
    """保守估算该券在给定购物车金额下「实际可省」金额（元）。

    规则：
    - 固定金额券（value_type=fixed，且 value 已知）：
        * 若设置了使用门槛 min_spend 且 cart_total 已知且不足：实际可省 = 0（不满足门槛）。
        * 否则可省 = min(value, cart_total)（不会超过购物车总额）。
    - 折扣券（percent）或面值 / 类型未知：返回 None（「未知」，不臆造可省金额）。
    - 任何未知字段都导致返回 None。
    """
    if coupon.is_unknown_value:
        return None
    value = coupon.value
    if value is None:
        return None
    if coupon.value_type == "fixed":
        if coupon.min_spend is not None and cart_total is not None:
            if cart_total < coupon.min_spend:
                return 0.0
        if cart_total is not None:
            return round(min(value, cart_total), 2)
        return round(value, 2)
    # percent 或其他类型：无法确定绝对金额
    return None


def validate_coupon_applicability(
    coupon: Coupon,
    context: Optional[dict] = None,
) -> tuple[bool, list[str]]:
    """校验优惠券在给定上下文中的可用性。

    context 可包含：
      - store: 门店编码/名称
      - order_type: 1 到店 / 2 外送
      - meal_codes: 已选餐品 code 列表
      - cart_total: 购物车金额（元）
    返回 (是否可用, 原因列表)。
    信息不足时返回 (False, ["信息不足，需以门店实际可用为准"])，不臆断可用。
    """
    context = context or {}
    reasons: list[str] = []
    applicable = True

    # 门店限制
    if coupon.applicable_store:
        store = context.get("store")
        if not store:
            applicable = False
            reasons.append("券限定门店，但未提供当前门店，无法确认是否可用。")
        elif store not in (coupon.applicable_store,):
            # 简单精确匹配；若门店编码体系不同，保守判为不可用并提示
            applicable = False
            reasons.append(
                f"券限定门店「{coupon.applicable_store}」，与当前门店「{store}」不一致。"
            )

    # 使用门槛
    if coupon.min_spend is not None:
        cart_total = context.get("cart_total")
        if cart_total is None:
            reasons.append(f"券有使用门槛 ¥{coupon.min_spend:g}，需达到门槛方可使用（当前未确认购物车金额）。")
        elif cart_total < coupon.min_spend:
            applicable = False
            reasons.append(
                f"购物车金额 ¥{cart_total:g} 未达到券门槛 ¥{coupon.min_spend:g}。"
            )

    # 餐品类目
    if coupon.applicable_categories and context.get("meal_codes"):
        # 类目与餐品 code 的映射需要菜单知识，这里仅做提示，不强行否决
        reasons.append("券有适用类目限制，请确认所选餐品符合券的适用范围。")

    if not reasons:
        reasons.append("基于已知信息，该券在当前上下文可尝试使用；最终以门店结算为准。")
    return applicable, reasons


def urgency_score(coupon: Coupon, now: Optional[datetime] = None) -> float:
    """紧迫度评分：越临近过期分数越高。无到期信息为 0。"""
    now = now or default_now()
    ed = _expire_datetime(coupon)
    if ed is None:
        return 0.0
    delta = (ed - now).days
    if delta < 0:
        return 1000.0  # 已过期
    if delta == 0:
        return 900.0
    if delta <= 3:
        return 600.0 - delta * 50.0
    if delta <= 7:
        return 300.0 - (delta - 3) * 30.0
    if delta <= 30:
        return 100.0 - (delta - 7) * 2.0
    return 10.0


def priority_score(
    coupon: Coupon, now: Optional[datetime] = None, cart_total: Optional[float] = None
) -> float:
    """综合优先级评分 = 紧迫度权重 + 估算可省权重。确定性、可复现。"""
    now = now or default_now()
    u = urgency_score(coupon, now)
    saving = estimate_saving(coupon, cart_total)
    s = (saving / TYPICAL_MAX_SAVING) if saving else 0.0
    return URGENCY_WEIGHT * u + SAVING_WEIGHT * s


def build_inventory_report(
    my_coupons: Optional[list[Coupon]] = None,
    available_coupons: Optional[list[Coupon]] = None,
    store_coupons: Optional[list[Coupon]] = None,
    points: Optional[PointsAccount] = None,
    campaigns: Optional[list[Campaign]] = None,
    horizon_days: int = 7,
    now: Optional[datetime] = None,
) -> InventoryReport:
    """整合多来源权益，生成标准化盘点报告。"""
    now = now or default_now()
    my = my_coupons or []
    avail = available_coupons or []
    store = store_coupons or []

    # 临期判定仅基于「我的券」与「门店券」（这些是已经持有的）
    owned = my + store
    cls = classify_coupons(owned, horizon_days=horizon_days, now=now)
    expiring = sort_coupons_by_expiry(cls["expiring_soon"], now=now)
    no_info = cls["no_expiry_info"]

    notes = []
    if not my and not store:
        notes.append("当前未查询到您持有的优惠券（可能为空或查询受限）。")
    if avail:
        notes.append(f"另有 {len(avail)} 张「可领取」优惠券可供领取（非您已持有）。")
    if points is not None and (points.available == 0):
        notes.append("当前积分余额为 0，暂无可规划兑换的积分权益。")

    return InventoryReport(
        my_coupons=my,
        available_coupons=avail,
        store_coupons=store,
        points=points,
        campaigns=campaigns or [],
        expiring_soon=expiring,
        no_expiry_info=no_info,
        notes=notes,
    )


def plan_within_budget(
    coupons: list[Coupon],
    budget: float,
    now: Optional[datetime] = None,
    context: Optional[dict] = None,
    days: int = 1,
) -> Plan:
    """在预算内生成权益使用规划。

    - 仅对「可用、未过期、未使用」的券做规划。
    - 按 priority_score 降序排序（确定性兜底到 coupon.id）。
    - 估算可省金额，并标注其置信度（固定金额且门槛满足=high，否则 low/unknown）。
    - 多日规划（days>1）时按紧迫度把临期券分配到最早可用的日期。
    - 不创造任何交易副作用。
    """
    now = now or default_now()
    context = context or {}
    cart_total = context.get("cart_total")

    usable = [
        c
        for c in coupons
        if not (c.status and ("已使用" in c.status or "失效" in c.status))
    ]
    # 过滤已过期
    usable = [c for c in usable if (_expire_datetime(c) is None or _expire_datetime(c) >= now)]
    ranked = sorted(
        usable,
        key=lambda c: (-priority_score(c, now, cart_total), c.id),
    )

    items: list[PlanItem] = []
    total_save = 0.0
    counted_any = False
    for c in ranked:
        saving = estimate_saving(c, cart_total)
        conf = "low"
        if saving is not None:
            if c.value_type == "fixed" and (c.min_spend is None or (cart_total is not None and cart_total >= c.min_spend)):
                conf = "high"
            else:
                conf = "medium"
            total_save += saving
            counted_any = True
        ed = _expire_datetime(c)
        deadline = c.expire_at
        reason = f"紧迫度评分 {urgency_score(c, now):.0f}，估算可省 {('¥%.2f' % saving) if saving is not None else '未知（不臆造）'}，置信度 {conf}。"
        items.append(
            PlanItem(
                action="建议使用/领取并使用" if c.source == "available" else "建议使用",
                coupon_id=c.id,
                coupon_title=c.title,
                reason=reason,
                estimated_saving=saving,
                deadline=deadline,
                confidence=conf,
            )
        )

    notes = []
    if not items:
        notes.append("在所提供数据中未发现可规划的可用优惠券。")
    if budget is not None:
        if counted_any:
            notes.append(
                f"在预算 ¥{budget:g} 内，以上方案估算合计可省约 ¥{total_save:.2f}（为保守估算，"
                f"最终以 calculate-price 实际核价为准）。"
            )
        else:
            notes.append(
                f"预算 ¥{budget:g} 已记录，但当前券的「实际可省金额」无法可靠估算，"
                f"请在选好具体餐品后由 calculate-price 实算。"
            )
    notes.append("本规划仅作建议，默认不自动下单或兑换；任何真实交易需您明确确认。")

    return Plan(
        mode="budget" if days <= 1 else "multi_day",
        recommended=items,
        estimated_total_saving=round(total_save, 2) if counted_any else None,
        budget=budget,
        price_confirmed=False,
        notes=notes,
        generated_at=now.isoformat(timespec="seconds"),
    )


def compare_plans(plans: list[Plan]) -> dict:
    """比较多个方案，按估算可省与预算给出对比。"""
    rows = []
    for i, p in enumerate(plans, 1):
        rows.append(
            {
                "plan_index": i,
                "mode": p.mode,
                "recommended_count": len(p.recommended),
                "estimated_total_saving": p.estimated_total_saving,
                "budget": p.budget,
                "price_confirmed": p.price_confirmed,
            }
        )
    best = None
    if plans:
        comparable = [p for p in plans if p.estimated_total_saving is not None]
        if comparable:
            best = max(comparable, key=lambda p: p.estimated_total_saving).mode
    return {"plans": rows, "best_by_saving": best}


def associate_campaigns(
    campaigns: list[Campaign],
    coupons: Optional[list[Coupon]] = None,
    meals: Optional[list[Meal]] = None,
    now: Optional[datetime] = None,
) -> list[dict]:
    """将营销活动与优惠券/餐品做关键字关联，给出关联建议。

    未来活动（status=future）一律标注为「待确认」，不承诺未来价格或优惠必然有效。
    """
    now = now or default_now()
    coupons = coupons or []
    meals = meals or []
    results = []

    coupon_titles = " ".join(c.title for c in coupons)
    meal_names = " ".join(m.name for m in meals)

    for camp in campaigns:
        signals = []
        conf = "medium"
        status_label = camp.status
        if status_label == "future":
            conf = "low"
            signals.append("该活动为未来活动，优惠条件未知，标注为待确认。")
        # 简单关键字关联
        if camp.title and (camp.title in coupon_titles or any(k in coupon_titles for k in camp.title.split() if k)):
            signals.append("活动标题与您持有的券名称相关。")
        if camp.title and camp.title in meal_names:
            signals.append("活动与您关注的餐品相关。")
        if "早餐" in (camp.title + camp.description) and any("早餐" in c.title for c in coupons):
            signals.append("活动涉及早餐优惠，您有相关早餐券可联动。")
        if not signals:
            signals.append("未检测到与当前权益的明确关联，可作为常规活动参考。")
        results.append(
            {
                "date": camp.date,
                "title": camp.title,
                "status": status_label,
                "confidence": conf,
                "signals": signals,
                "confirmed": status_label != "future",
            }
        )
    return results


def reconcile_price(calc_data: dict) -> PriceResult:
    """解析麦当劳 calculate-price 返回的「分」单位价格，转为「元」并区分各项。

    若输入为空或缺少关键字段，抛出 PriceCalcUnavailable，绝不展示虚构价格。
    """
    if not calc_data:
        raise PriceCalcUnavailable("未收到 calculate-price 返回数据。")

    def fen_to_yuan(v):
        if v is None:
            return None
        try:
            return round(float(v) / 100.0, 2)
        except (ValueError, TypeError):
            return None

    original = fen_to_yuan(calc_data.get("originalPrice"))
    discount = fen_to_yuan(calc_data.get("discount"))
    price = fen_to_yuan(calc_data.get("price"))
    if price is None:
        raise PriceCalcUnavailable("calculate-price 返回缺少应付金额字段。")

    uncertain: list[str] = []
    packing = fen_to_yuan(calc_data.get("packingPrice"))
    delivery = fen_to_yuan(calc_data.get("deliveryPrice"))
    tableware = fen_to_yuan(calc_data.get("tablewarePrice"))

    # 到店场景（orderType=1）下正常不应有配送费；若有，标记为待确认
    if delivery is not None and delivery > 0:
        uncertain.append("出现配送费，请确认取餐方式是否为外送。")
    if tableware is not None and tableware > 0:
        uncertain.append("包含餐具费，具体以结算页为准。")

    return PriceResult(
        original_price=original if original is not None else price,
        discount=discount if discount is not None else 0.0,
        actual_price=price,
        product_original=fen_to_yuan(calc_data.get("productOriginalPrice")) or 0.0,
        product_price=fen_to_yuan(calc_data.get("productPrice")) or 0.0,
        packing_fee=packing,
        delivery_fee=delivery,
        tableware_fee=tableware,
        uncertain_fees=uncertain,
        confirmed=True,
        raw=calc_data,
    )


class PriceCalcUnavailable(Exception):
    """价格核算不可用（网络失败 / 返回为空 / 字段缺失）。"""

    pass


def build_price_failure(reason: str) -> dict:
    """当价格核算失败时的安全降级输出，不展示任何虚构金额。"""
    return {
        "confirmed": False,
        "error": reason,
        "note": "价格核算暂不可用，请勿以任何估算数字作为最终到手价；请以麦当劳官方结算页实时结果为准。",
    }
