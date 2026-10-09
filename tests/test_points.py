from mcperks.core import detect_expiring_points


def test_points_zero_no_risk(expiring_points, zero_points):
    # zero_points has 0 expiring -> low risk
    r = detect_expiring_points(zero_points)
    assert r["risk"] == "low"
    assert r["total_expiring"] == 0


def test_points_expiring_this_month_high_risk(expiring_points):
    r = detect_expiring_points(expiring_points)
    assert r["current_month_expire"] == 300
    assert r["next_month_expire"] == 200
    assert r["risk"] == "high"
    assert "300" in r["message"]


def test_points_missing_fields_safe():
    from mcperks.models import PointsAccount

    acc = PointsAccount.from_dict({})  # 全部缺失
    r = detect_expiring_points(acc)
    assert r["total_expiring"] == 0
    assert r["risk"] == "low"
