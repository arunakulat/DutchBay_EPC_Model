from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

SCENARIO = Path("dutchbay_v13/inputs/scenarios/release_case.yaml")
OUTDIR   = Path("_out_golden_baseline")
BASELINE = Path("tests/golden/summary.json")
FROZEN_KEYS = ("equity_irr", "project_irr", "npv_12")

def main() -> int:
    if not SCENARIO.exists():
        print(f"[x] Missing scenario: {SCENARIO}", file=sys.stderr)
        return 2

    OUTDIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["VALIDATION_MODE"] = "relaxed"

    cmd = [
        sys.executable, "-m", "dutchbay_v13",
        "--mode", "irr",
        "--config", str(SCENARIO),
        "--out", str(OUTDIR),
        "--fmt", "csv",
    ]
    subprocess.run(cmd, check=True, env=env)

    sj = OUTDIR / "summary.json"
    if not sj.exists():
        print("[x] summary.json not produced; check CLI/run_dir", file=sys.stderr)
        return 3

    data = json.loads(sj.read_text(encoding="utf-8"))
    # Ensure we only store known keys to keep the baseline slim & stable
    minimal = {k: float(data[k]) for k in FROZEN_KEYS if k in data}
    if set(minimal) != set(FROZEN_KEYS):
        print(f"[x] summary.json missing keys {set(FROZEN_KEYS)-set(minimal)}", file=sys.stderr)
        return 4

    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(minimal, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[ok] Wrote baseline {BASELINE}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

    