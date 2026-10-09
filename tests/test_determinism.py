from mcperks.core import plan_within_budget, build_inventory_report, sort_coupons_by_expiry
from tests.conftest import make_coupon, FIXED_NOW


def test_same_input_stable_output():
    coupons = [
        make_coupon(id="z", expire_at="2026-10-15", value_type="fixed", value=12),
        make_coupon(id="a", expire_at="2026-10-12", value_type="fixed", value=12),
        make_coupon(id="m", expire_at="2026-10-20", value_type="fixed", value=12),
    ]
    p1 = plan_within_budget(coupons, budget=50.0, now=FIXED_NOW, context={"cart_total": 40.0})
    p2 = plan_within_budget(coupons, budget=50.0, now=FIXED_NOW, context={"cart_total": 40.0})
    assert [i.coupon_id for i in p1.recommended] == [i.coupon_id for i in p2.recommended]
    assert p1.estimated_total_saving == p2.estimated_total_saving


def test_deterministic_tie_break_by_id():
    coupons = [
        make_coupon(id="b", expire_at="2026-10-15"),
        make_coupon(id="a", expire_at="2026-10-15"),
        make_coupon(id="c", expire_at="2026-10-15"),
    ]
    ordered = sort_coupons_by_expiry(coupons, now=FIXED_NOW)
    assert [c.id for c in ordered] == ["a", "b", "c"]


def test_inventory_report_deterministic(sample_coupons):
    r1 = build_inventory_report(my_coupons=sample_coupons, now=FIXED_NOW)
    r2 = build_inventory_report(my_coupons=sample_coupons, now=FIXED_NOW)
    assert [c.id for c in r1.expiring_soon] == [c.id for c in r2.expiring_soon]
