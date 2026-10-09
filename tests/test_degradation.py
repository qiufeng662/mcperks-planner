from mcperks.core import estimate_saving, validate_coupon_applicability, build_inventory_report
from mcperks.models import Coupon, PointsAccount
from tests.conftest import FIXED_NOW


def test_missing_value_not_fabricated():
    c = Coupon.from_dict({"id": "x", "value_type": "unknown", "value": None})
    assert estimate_saving(c, cart_total=100) is None


def test_missing_expiry_safe_classify():
    coupons = [Coupon.from_dict({"id": "n", "expire_at": None})]
    report = build_inventory_report(my_coupons=coupons, now=FIXED_NOW)
    assert report.no_expiry_info and report.no_expiry_info[0].id == "n"


def test_missing_store_not_assumed():
    c = Coupon.from_dict({"id": "s", "applicable_store": "123"})
    ok, reasons = validate_coupon_applicability(c, {})
    assert ok is False


def test_partial_account_fields_default_to_zero():
    acc = PointsAccount.from_dict({"availablePoint": "500"})  # 其余缺失
    assert acc.available == 500.0
    assert acc.current_month_expire == 0.0
    assert acc.next_month_expire == 0.0
