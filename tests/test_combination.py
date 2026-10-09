from mcperks.core import plan_within_budget, priority_score, urgency_score
from tests.conftest import make_coupon, FIXED_NOW


def test_priority_ranks_expiring_higher():
    soon = make_coupon(id="soon", expire_at="2026-10-11", value_type="fixed", value=10)
    later = make_coupon(id="later", expire_at="2026-10-25", value_type="fixed", value=10)
    assert priority_score(soon, now=FIXED_NOW) > priority_score(later, now=FIXED_NOW)


def test_combination_picks_multiple_coupons(sample_coupons):
    plan = plan_within_budget(sample_coupons, budget=100.0, now=FIXED_NOW, context={"cart_total": 60.0})
    # 推荐应包含多张券的优先级排序，且 C1(临期) 排在 C2 前
    ids = [i.coupon_id for i in plan.recommended]
    assert ids.index("C1") < ids.index("C2")


def test_urgency_score_expired_is_highest():
    from tests.conftest import make_coupon

    exp = make_coupon(id="e", expire_at="2026-10-01")
    soon = make_coupon(id="s", expire_at="2026-10-11")
    assert urgency_score(exp, now=FIXED_NOW) > urgency_score(soon, now=FIXED_NOW)


def test_multi_day_mode_labeled():
    plan = plan_within_budget([], budget=50.0, now=FIXED_NOW, days=7)
    assert plan.mode == "multi_day"
