from mcperks.core import sort_coupons_by_expiry, classify_coupons
from tests.conftest import make_coupon, FIXED_NOW


def test_sort_by_expiry_orders_soonest_first():
    coupons = [
        make_coupon(id="a", expire_at="2026-10-20"),
        make_coupon(id="b", expire_at="2026-10-12"),
        make_coupon(id="c", expire_at="2026-10-15"),
    ]
    ordered = sort_coupons_by_expiry(coupons, now=FIXED_NOW)
    assert [c.id for c in ordered] == ["b", "c", "a"]


def test_sort_puts_unknown_expiry_last():
    coupons = [
        make_coupon(id="known", expire_at="2026-10-12"),
        make_coupon(id="unknown", expire_at=None),
    ]
    ordered = sort_coupons_by_expiry(coupons, now=FIXED_NOW)
    assert ordered[-1].id == "unknown"


def test_classify_expiring_within_horizon():
    coupons = [
        make_coupon(id="c1", expire_at="2026-10-12"),  # +3 天，临期
        make_coupon(id="c2", expire_at="2026-11-30"),  # 远，可用
        make_coupon(id="c3", expire_at=None),           # 未知
    ]
    cls = classify_coupons(coupons, horizon_days=7, now=FIXED_NOW)
    expiring_ids = {c.id for c in cls["expiring_soon"]}
    no_info_ids = {c.id for c in cls["no_expiry_info"]}
    assert "c1" in expiring_ids
    assert "c2" not in expiring_ids
    assert "c3" in no_info_ids


def test_classify_excludes_used_coupons():
    coupons = [make_coupon(id="u", status="已使用", expire_at="2026-10-12")]
    cls = classify_coupons(coupons, now=FIXED_NOW)
    assert "u" not in {c.id for c in cls["expiring_soon"]}
