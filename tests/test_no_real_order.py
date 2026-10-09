"""安全断言：Skill 默认绝不产生下单 / 兑换等真实交易副作用。"""

import os
import inspect

from mcperks import core, mcp_adapter
from mcperks.core import plan_within_budget
from tests.conftest import make_coupon, FIXED_NOW


def test_plan_explicitly_states_no_auto_order():
    plan = plan_within_budget([make_coupon(id="c")], budget=50.0, now=FIXED_NOW)
    assert any("不自动下单" in n for n in plan.notes)
    assert plan.price_confirmed is False


def test_core_module_never_references_create_order():
    """核心计算模块源码中不得出现任何下单/兑换工具的调用。"""
    for mod in (core, mcp_adapter):
        source = inspect.getsource(mod)
        assert "create_order" not in source
        assert "create-order" not in source
        assert "cancel_order" not in source
        assert "auto-bind-coupons" not in source
        assert "mall-create-order" not in source


def test_plan_output_has_no_order_fields():
    import json

    plan = plan_within_budget([make_coupon(id="c")], budget=50.0, now=FIXED_NOW)
    dumped = json.dumps(plan.__dict__, ensure_ascii=False, default=str)
    assert "create_order" not in dumped
    assert "order_id" not in dumped
