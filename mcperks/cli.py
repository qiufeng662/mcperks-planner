"""麦门权益管家命令行入口。

WorkBuddy 在调用麦当劳 MCP 拿到真实数据后，把结构化 JSON 喂给本 CLI，
由核心算法产出确定性的盘点 / 规划 / 核价结果。

典型用法：
  python -m mcperks.cli inventory --input bundle.json
  python -m mcperks.cli plan --input plan_input.json
  python -m mcperks.cli reprice --input calc.json
  python -m mcperks.cli campaigns --input camp.json
  python -m mcperks.cli demo

输出：stdout 为可解析的 JSON；同时向 stderr 打印人类可读摘要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Optional

from . import core
from .core import (
    PriceCalcUnavailable,
    associate_campaigns,
    build_inventory_report,
    build_price_failure,
    compare_plans,
)
from .models import Campaign, Coupon, Meal, PointsAccount
from .mcp_adapter import (
    campaign_from_dict,
    coupon_from_dict,
    meal_from_dict,
    parse_account,
    parse_calculate_price,
)


def _read_input(args) -> Any:
    if args.input == "-":
        return json.load(sys.stdin)
    with open(args.input, "r", encoding="utf-8") as f:
        return json.load(f)


def _coupons_from(raw_list, source="unknown"):
    return [coupon_from_dict(d, source=source) for d in (raw_list or [])]


def _emit(payload: dict, summary: str):
    sys.stderr.write(summary + "\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def cmd_inventory(args):
    data = _read_input(args)
    my = _coupons_from(data.get("my_coupons"), "my")
    avail = _coupons_from(data.get("available_coupons"), "available")
    store = _coupons_from(data.get("store_coupons"), "store")
    points = None
    if data.get("points"):
        points = parse_account(data["points"]) if "data" in data["points"] else PointsAccount.from_dict(data["points"])
    camps = [campaign_from_dict(c) for c in data.get("campaigns", [])]
    report = build_inventory_report(
        my_coupons=my, available_coupons=avail, store_coupons=store,
        points=points, campaigns=camps, horizon_days=args.horizon, now=_now(),
    )
    payload = {
        "expiring_soon": [
            {"id": c.id, "title": c.title, "expire_at": c.expire_at, "value_type": c.value_type, "value": c.value}
            for c in report.expiring_soon
        ],
        "no_expiry_info": [{"id": c.id, "title": c.title, "source": c.source} for c in report.no_expiry_info],
        "available_count": len(report.available_coupons),
        "points": (
            {
                "available": report.points.available,
                "current_month_expire": report.points.current_month_expire,
                "next_month_expire": report.points.next_month_expire,
                "currency": report.points.currency,
            }
            if report.points
            else None
        ),
        "campaigns_count": len(report.campaigns),
        "notes": report.notes,
    }
    summary = (
        f"[盘点] 临期券 {len(report.expiring_soon)} 张，无到期信息 {len(report.no_expiry_info)} 张，"
        f"活动 {len(report.campaigns)} 个。"
    )
    _emit(payload, summary)


def cmd_plan(args):
    data = _read_input(args)
    coupons = _coupons_from(data.get("coupons"))
    budget = data.get("budget")
    context = data.get("context", {}) or {}
    days = int(data.get("days", args.days))
    plan = core.plan_within_budget(coupons, budget=budget, now=_now(), context=context, days=days)
    payload = {
        "mode": plan.mode,
        "recommended": [vars(i) for i in plan.recommended],
        "estimated_total_saving": plan.estimated_total_saving,
        "budget": plan.budget,
        "price_confirmed": plan.price_confirmed,
        "notes": plan.notes,
    }
    summary = (
        f"[规划] 推荐 {len(plan.recommended)} 条，估算可省 "
        f"{('¥%.2f' % plan.estimated_total_saving) if plan.estimated_total_saving is not None else '未知'}。"
    )
    _emit(payload, summary)


def cmd_reprice(args):
    data = _read_input(args)
    calc = data.get("calc_data", data)
    try:
        result = parse_calculate_price(calc) if "data" in calc or "price" in calc else core.reconcile_price(calc)
        payload = {
            "confirmed": True,
            "original_price": result.original_price,
            "discount": result.discount,
            "actual_price": result.actual_price,
            "uncertain_fees": result.uncertain_fees,
            "note": "金额已按麦当劳返回（分）换算为元；最终以结算页为准。",
        }
        summary = (
            f"[核价] 原价 ¥{result.original_price:.2f}，优惠 ¥{result.discount:.2f}，"
            f"应付 ¥{result.actual_price:.2f}（已确认）。"
        )
    except (PriceCalcUnavailable, KeyError, TypeError) as e:
        payload = build_price_failure(str(e))
        summary = f"[核价] 核算失败：{e}"
    _emit(payload, summary)


def cmd_campaigns(args):
    data = _read_input(args)
    camps = [campaign_from_dict(c) for c in data.get("campaigns", [])]
    coupons = _coupons_from(data.get("coupons"))
    meals = [meal_from_dict(m) for m in data.get("meals", [])]
    assoc = associate_campaigns(camps, coupons=coupons, meals=meals, now=_now())
    payload = {"associations": assoc}
    summary = f"[活动] 关联分析 {len(assoc)} 个活动。"
    _emit(payload, summary)


def cmd_compare(args):
    data = _read_input(args)
    plans_raw = data.get("plans", [])
    plans = []
    for p in plans_raw:
        from .models import Plan, PlanItem

        plans.append(
            Plan(
                mode=p.get("mode", "budget"),
                recommended=[PlanItem(**i) for i in p.get("recommended", [])],
                estimated_total_saving=p.get("estimated_total_saving"),
                budget=p.get("budget"),
                price_confirmed=p.get("price_confirmed", False),
            )
        )
    result = compare_plans(plans)
    _emit(result, f"[比较] 共 {len(plans)} 个方案，最省：{result['best_by_saving']}")


def cmd_demo(args):
    """使用随仓库附带的示例数据演示（含真实抓取的「可领取券/活动」与明确标注的模拟「我的券」）。"""
    import os

    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
    my = _coupons_from(_load(base, "sample_my_coupons.json"), "my")
    avail = _coupons_from(_load(base, "sample_available_coupons.json"), "available")
    camps = [campaign_from_dict(c) for c in _load(base, "sample_campaigns.json")]
    points = PointsAccount.from_dict(_load(base, "sample_account.json"))

    report = build_inventory_report(
        my_coupons=my, available_coupons=avail, points=points, campaigns=camps, now=_now()
    )
    plan = core.plan_within_budget(my + avail, budget=80.0, now=_now(), context={"cart_total": 60.0}, days=7)

    payload = {
        "demo_note": "本示例数据：可领取券与活动为真实抓取（已脱敏），我的券为演示用模拟数据。",
        "expiring_soon": [{"id": c.id, "title": c.title, "expire_at": c.expire_at} for c in report.expiring_soon],
        "points": {"available": points.available, "current_month_expire": points.current_month_expire},
        "plan_recommended": [vars(i) for i in plan.recommended],
        "estimated_total_saving": plan.estimated_total_saving,
    }
    summary = (
        f"[Demo] 临期券 {len(report.expiring_soon)} 张；预算 ¥80 规划推荐 "
        f"{len(plan.recommended)} 条，估算可省 "
        f"{('¥%.2f' % plan.estimated_total_saving) if plan.estimated_total_saving is not None else '未知'}。"
    )
    _emit(payload, summary)


def _load(base, name):
    with open(os.path.join(base, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _now():
    return datetime.now()


def build_parser():
    p = argparse.ArgumentParser(prog="mcperks", description="麦门权益管家 McPerks Planner")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("inventory", help="权益盘点")
    pi.add_argument("--input", required=True)
    pi.add_argument("--horizon", type=int, default=7)
    pi.set_defaults(func=cmd_inventory)

    pp = sub.add_parser("plan", help="权益使用规划")
    pp.add_argument("--input", required=True)
    pp.add_argument("--days", type=int, default=1)
    pp.set_defaults(func=cmd_plan)

    pr = sub.add_parser("reprice", help="价格核算")
    pr.add_argument("--input", required=True)
    pr.set_defaults(func=cmd_reprice)

    pc = sub.add_parser("campaigns", help="活动关联")
    pc.add_argument("--input", required=True)
    pc.set_defaults(func=cmd_campaigns)

    pcmp = sub.add_parser("compare", help="多方案比较")
    pcmp.add_argument("--input", required=True)
    pcmp.set_defaults(func=cmd_compare)

    pd = sub.add_parser("demo", help="示例演示")
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
