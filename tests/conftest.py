"""共享测试 fixtures。固定 now 以保证确定性。"""

from datetime import datetime

import pytest

from mcperks.models import Coupon, PointsAccount

FIXED_NOW = datetime(2026, 10, 9, 15, 30, 0)


@pytest.fixture
def now():
    return FIXED_NOW


def make_coupon(**kw) -> Coupon:
    base = dict(
        id="X",
        title="券",
        source="my",
        status="可用",
        expire_at=None,
        value_type="unknown",
        value=None,
        min_spend=None,
        applicable_categories=[],
        applicable_store=None,
        conditions="",
    )
    base.update(kw)
    return Coupon.from_dict(base)


@pytest.fixture
def sample_coupons():
    return [
        make_coupon(id="C1", title="满30减15", expire_at="2026-10-12", value_type="fixed", value=15, min_spend=30),
        make_coupon(id="C2", title="满40减20", expire_at="2026-10-15", value_type="fixed", value=20, min_spend=40),
        make_coupon(id="C3", title="8折券", expire_at="2026-10-20", value_type="percent", value=0.8),
        make_coupon(id="C4", title="无门槛10元", expire_at=None, value_type="fixed", value=10),
        make_coupon(id="C5", title="过期30元", expire_at="2026-10-05", value_type="fixed", value=30, min_spend=50),
        make_coupon(id="C6", title="已使用5元", expire_at="2026-10-18", status="已使用", value_type="fixed", value=5),
    ]


@pytest.fixture
def zero_points():
    return PointsAccount.from_dict(
        {
            "availablePoint": "0",
            "accumulativePoint": "0",
            "currency": "麦享会积分",
            "currentMouthExpirePoint": "0",
            "nextMouthExpirePoint": "0",
        }
    )


@pytest.fixture
def expiring_points():
    return PointsAccount.from_dict(
        {
            "availablePoint": "1200",
            "currency": "麦享会积分",
            "currentMouthExpirePoint": "300",
            "nextMouthExpirePoint": "200",
        }
    )
