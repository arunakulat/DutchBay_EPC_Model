from __future__ import annotations
import json, os, sys, subprocess
from pathlib import Path

SCENARIO = Path("dutchbay_v13/inputs/scenarios/release_case.yaml")
BASELINE = Path("tests/golden/summary.json")
OUTDIR   = Path("_out_golden_test")

# Keys we freeze for drift detection
FROZEN_KEYS = ("equity_irr", "project_irr", "npv_12")

def test_release_case_is_stable():
    assert SCENARIO.exists(), f"Missing scenario {SCENARIO} – add it, or update the path in this test."

    # Run via CLI to exercise the public surface and artifact writing
    OUTDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["VALIDATION_MODE"] = "relaxed"  # Force non-strict for reproducibility
    cmd = [
        sys.executable, "-m", "dutchbay_v13",
        "--mode", "irr",
        "--config", str(SCENARIO),
        "--out", str(OUTDIR),
        "--fmt", "csv",
    ]
    subprocess.run(cmd, check=True, env=env)

    # Artifacts must exist
    sj = OUTDIR / "summary.json"
    assert sj.exists() and sj.stat().st_size > 0, "Expected _out_golden_test/summary.json"
    any_csv = list(OUTDIR.glob("*results*.csv"))
    assert any_csv, "Expected at least one results CSV file"

    # Baseline must exist; if not, instruct to refresh
    assert BASELINE.exists(), (
        "Golden baseline missing. Run:\n"
        "  python scripts/golden_refresh.py\n"
        "and commit tests/golden/summary.json"
    )

    got = json.loads(sj.read_text(encoding="utf-8"))
    want = json.loads(BASELINE.read_text(encoding="utf-8"))

    # Compare only frozen keys with a small tolerance
    for k in FROZEN_KEYS:
        assert k in got, f"Missing '{k}' in summary.json"
        assert k in want, f"Missing '{k}' in baseline"
        diff = abs(float(got[k]) - float(want[k]))
        assert diff < 1e-9, f"{k} drifted: got={got[k]} want={want[k]} (|Δ|={diff})"

        