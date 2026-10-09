from mcperks.core import validate_coupon_applicability, estimate_saving
from tests.conftest import make_coupon, FIXED_NOW


def test_store_mismatch_not_applicable():
    c = make_coupon(id="s", applicable_store="1450713")
    ok, reasons = validate_coupon_applicability(c, {"store": "9999999"})
    assert ok is False
    assert any("门店" in r for r in reasons)


def test_store_unknown_is_not_assumed_applicable():
    c = make_coupon(id="s", applicable_store="1450713")
    ok, reasons = validate_coupon_applicability(c, {})  # 未提供门店
    assert ok is False
    assert any("未提供当前门店" in r for r in reasons)


def test_min_spend_not_met_not_applicable():
    c = make_coupon(id="m", value_type="fixed", value=15, min_spend=30)
    ok, reasons = validate_coupon_applicability(c, {"cart_total": 20})
    assert ok is False
    assert any("未达到" in r for r in reasons)


def test_applicable_when_known_ok():
    c = make_coupon(id="ok", value_type="fixed", value=15, min_spend=30)
    ok, reasons = validate_coupon_applicability(c, {"cart_total": 40})
    assert ok is True


def test_estimate_saving_fixed_capped_by_cart():
    c = make_coupon(id="f", value_type="fixed", value=50, min_spend=None)
    assert estimate_saving(c, cart_total=30) == 30.0


def test_estimate_saving_percent_is_unknown():
    c = make_coupon(id="p", value_type="percent", value=0.8)
    assert estimate_saving(c, cart_total=100) is None


def test_estimate_saving_unknown_value_is_unknown():
    c = make_coupon(id="u", value_type="unknown", value=None)
    assert estimate_saving(c, cart_total=100) is None
