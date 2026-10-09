from mcperks.core import build_inventory_report, plan_within_budget
from mcperks.mcp_adapter import parse_account, parse_calculate_price
from mcperks.core import PriceCalcUnavailable
from tests.conftest import FIXED_NOW


def test_empty_my_coupons_inventory_notes():
    report = build_inventory_report(my_coupons=[], available_coupons=[], now=FIXED_NOW)
    assert report.expiring_soon == []
    assert any("未查询到" in n for n in report.notes)


def test_empty_coupons_plan_has_no_recommendation():
    plan = plan_within_budget([], budget=80.0, now=FIXED_NOW)
    assert plan.recommended == []
    assert any("未发现" in n for n in plan.notes)


def test_parse_account_empty_data_safe():
    acc = parse_account({"success": True, "code": 200, "data": {}})
    assert acc.available == 0.0
    # 敏感字段不进入模型
    assert acc.account_id_masked is None


def test_parse_calculate_price_empty_raises():
    try:
        parse_calculate_price({})
    except PriceCalcUnavailable:
        pass
    else:
        raise AssertionError("空 calculate-price 应抛出 PriceCalcUnavailable")
