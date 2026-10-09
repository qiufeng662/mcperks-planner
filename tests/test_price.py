import os
import json

import pytest

from mcperks.core import reconcile_price, PriceCalcUnavailable, build_price_failure
from mcperks.mcp_adapter import parse_calculate_price

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")


def test_real_price_converts_fen_to_yuan():
    with open(os.path.join(FIXTURES, "sample_price_calc.json"), encoding="utf-8") as f:
        data = json.load(f)
    # 2550 分 = 25.50 元
    result = reconcile_price(data)
    assert result.actual_price == 25.5
    assert result.original_price == 25.5
    assert result.discount == 0.0
    assert result.confirmed is True


def test_price_separates_components():
    data = {
        "originalPrice": 4650,
        "discount": 1050,
        "price": 3600,
        "productOriginalPrice": 4650,
        "productPrice": 3600,
        "packingPrice": 0,
        "deliveryPrice": 0,
        "tablewarePrice": 0,
    }
    r = reconcile_price(data)
    assert r.original_price == 46.5
    assert r.discount == 10.5
    assert r.actual_price == 36.0


def test_price_missing_field_raises():
    with pytest.raises(PriceCalcUnavailable):
        reconcile_price({"originalPrice": 100})


def test_price_empty_raises():
    with pytest.raises(PriceCalcUnavailable):
        reconcile_price({})


def test_build_price_failure_no_fabricated_number():
    out = build_price_failure("网络超时")
    assert out["confirmed"] is False
    assert "error" in out
    # 不应包含任何虚构的金额数字
    assert "¥" not in out["note"]


def test_parse_calculate_price_from_data_wrapper():
    wrapped = {"success": True, "code": 200, "data": {"price": 2550, "originalPrice": 2550, "discount": 0}}
    r = parse_calculate_price(wrapped)
    assert r.actual_price == 25.5
