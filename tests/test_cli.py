import pytest

from dutchbay_v13 import cli

def test_cli_missing_mode():
    assert cli.main([]) == 2

def test_cli_valid_report():
    assert cli.main(["--mode", "report"]) == 0

def test_cli_valid_scenarios(tmp_path):
    in_dir = tmp_path / "sc"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    # minimal YAML
    (in_dir / "s1.yaml").write_text("tariff_usd_per_kwh: 0.1\n", encoding="utf-8")
    rc = cli.main(["--mode", "scenarios", "--scenarios-dir", str(in_dir), "--outputs-dir", str(out_dir), "--format", "jsonl"])
    assert rc == 0
    assert (out_dir / "scenarios.jsonl").exists()

def test_cli_invalid_mode_exits_2():
    # argparse enforces choices; simulate by calling parse directly and catching SystemExit
    with pytest.raises(SystemExit) as ei:
        cli.parse_args(["--mode", "nope"])
    assert ei.value.code == 2 or ei.value.code == 1
