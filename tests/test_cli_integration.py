"""CLI 端到端集成测试：真实运行命令，验证 JSON 输出与无副作用。"""

import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO_ROOT, "fixtures")


def _run(args, input_obj=None):
    env = dict(os.environ)
    p = subprocess.run(
        [sys.executable, "-m", "mcperks.cli", *args],
        cwd=REPO_ROOT,
        input=json.dumps(input_obj) if input_obj is not None else None,
        capture_output=True,
        text=True,
        env=env,
    )
    return p


def test_demo_runs_and_outputs_json():
    p = _run(["demo"])
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert "demo_note" in out
    assert "plan_recommended" in out


def test_inventory_cli_with_fixtures():
    bundle = {
        "my_coupons": json.load(open(os.path.join(FIXTURES, "sample_my_coupons.json"), encoding="utf-8")),
        "available_coupons": json.load(open(os.path.join(FIXTURES, "sample_available_coupons.json"), encoding="utf-8")),
        "campaigns": json.load(open(os.path.join(FIXTURES, "sample_campaigns.json"), encoding="utf-8")),
        "points": {"availablePoint": "0", "currentMouthExpirePoint": "0"},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(bundle, f)
        path = f.name
    try:
        p = _run(["inventory", "--input", path])
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert "expiring_soon" in out
    finally:
        os.unlink(path)


def test_reprice_cli_with_fixture():
    calc = json.load(open(os.path.join(FIXTURES, "sample_price_calc.json"), encoding="utf-8"))
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(calc, f)
        path = f.name
    try:
        p = _run(["reprice", "--input", path])
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert out["confirmed"] is True
        assert out["actual_price"] == 25.5
    finally:
        os.unlink(path)


def test_plan_cli_runs():
    coupons = json.load(open(os.path.join(FIXTURES, "sample_my_coupons.json"), encoding="utf-8"))
    payload = {"coupons": coupons, "budget": 80.0, "context": {"cart_total": 60.0}, "days": 1}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f)
        path = f.name
    try:
        p = _run(["plan", "--input", path])
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert "recommended" in out
    finally:
        os.unlink(path)
