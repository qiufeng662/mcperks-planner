from mcperks.core import plan_within_budget
from tests.conftest import FIXED_NOW


def test_budget_plan_respects_estimate_and_ranks(sample_coupons):
    plan = plan_within_budget(sample_coupons, budget=80.0, now=FIXED_NOW, context={"cart_total": 60.0}, days=1)
    # 已过期(C5)与已使用(C6)被过滤
    ids = [i.coupon_id for i in plan.recommended]
    assert "C5" not in ids
    assert "C6" not in ids
    # 估算可省 = 15(C1,满足门槛) + 20(C2,满足门槛) + 10(C4) = 45，C3折扣券未知不计入
    assert plan.estimated_total_saving == 45.0


def test_budget_too_low_for_min_spend_zeroes_saving():
    from tests.conftest import make_coupon

    c = make_coupon(id="m", value_type="fixed", value=15, min_spend=30)
    plan = plan_within_budget([c], budget=10.0, now=FIXED_NOW, context={"cart_total": 10.0})
    # 购物车 10 元 < 门槛 30，估算可省为 0
    assert plan.recommended[0].estimated_saving == 0.0


def test_budget_note_present(sample_coupons):
    plan = plan_within_budget(sample_coupons, budget=80.0, now=FIXED_NOW, context={"cart_total": 60.0})
    assert any("预算" in n for n in plan.notes)
    # 默认不自动下单提示
    assert any("不自动下单" in n for n in plan.notes)
