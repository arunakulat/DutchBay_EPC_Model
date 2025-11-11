import os
import subprocess
import sys
from pathlib import Path
import pytest

from dutchbay_v13.scenario_runner import run_dir

MIN_CFG = """\
project:
  capacity_mw: 150
  timeline: { lifetime_years: 25 }
capex: { usd_total: 225000000 }
Financing_Terms: { debt_ratio: 0.0 }
metrics: { npv_discount_rate: 0.12 }
"""

def _write(p: Path, name: str, text: str) -> Path:
    f = p / name
    f.write_text(text, encoding="utf-8")
    return f

def test_strict_requires_annual_in_runner(tmp_path: Path, monkeypatch):
    cfg = _write(tmp_path, "no_annual.yaml", MIN_CFG)
    out = tmp_path / "out"
    monkeypatch.setenv("VALIDATION_MODE", "strict")
    with pytest.raises(SystemExit):
        run_dir(cfg, out, mode="irr", fmt="csv", save_annual=False)

def test_cli_flag_requires_annual(tmp_path: Path):
    cfg = _write(tmp_path, "no_annual.yaml", MIN_CFG)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(
            [sys.executable, "-m", "dutchbay_v13", "--mode", "irr", "--config", str(cfg), "--out", str(out), "--require-annual"]
        )