import importlib
import inspect
from pathlib import Path


def _param_names(fn):
    return [p.name for p in inspect.signature(fn).parameters.values()]


def test_finance_irr_public_api_is_stable():
    """Lock down that IRR/NPV live in finance.irr with a stable entrypoint."""
    m = importlib.import_module("dutchbay_v13.finance.irr")
    assert hasattr(m, "irr") and callable(m.irr)
    assert hasattr(m, "npv") and callable(m.npv)

    # Keep the first parameter name stable to avoid accidental API churn.
    irr_params = _param_names(m.irr)
    assert len(irr_params) >= 1
    assert irr_params[0] == "cashflows"

    # Guard against accidental coupling/import creep in the thin math module.
    # (Only block real code deps; ignore comments/docstrings.)
    src = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("from dutchbay_v13", "apply_debt_layer"):
        assert forbidden not in src, f"Unexpected dependency '{forbidden}' inside finance/irr.py"


def test_adapters_run_irr_api_and_result_shape():
    """Adapters.run_irr must exist and return a mapping with core keys."""
    a = importlib.import_module("dutchbay_v13.adapters")
    assert hasattr(a, "run_irr") and callable(a.run_irr)

    params = {
        "project": {"capacity_mw": 1, "timeline": {"lifetime_years": 1}},
        "capex": {"usd_total": 1.0},
        "Financing_Terms": {"debt_ratio": 0.0},
        "metrics": {"npv_discount_rate": 0.12},
    }
    res = a.run_irr(params, [{"year": 1, "cfads_usd": 0.0}])
    assert isinstance(res, dict)
    for k in ("equity_irr", "project_irr", "npv_12", "annual"):
        assert k in res


def test_validate_exports_are_stable():
    """validate module must expose these helpers (names kept stable)."""
    v = importlib.import_module("dutchbay_v13.validate")
    for name in ("validate_params_dict", "load_params_from_file"):
        obj = getattr(v, name, None)
        assert callable(obj), f"Missing or non-callable export: {name}"


def test_scenario_runner_run_dir_api_minimal(tmp_path):
    """run_dir must accept (cfg_path, out_dir, ...) and return a summary-like object."""
    r = importlib.import_module("dutchbay_v13.scenario_runner")
    assert hasattr(r, "run_dir") and callable(r.run_dir)

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "project: { capacity_mw: 1, timeline: { lifetime_years: 1 } }\n"
        "capex: { usd_total: 1 }\n"
        "Financing_Terms: { debt_ratio: 0.0 }\n"
        "metrics: { npv_discount_rate: 0.12 }\n",
        encoding="utf-8",
    )
    out = tmp_path / "o"
    out.mkdir(parents=True, exist_ok=True)

    res = r.run_dir(cfg, out, mode="irr", fmt="jsonl", save_annual=False)
    # Support either a dataclass-like with .summary or a plain dict
    summary = getattr(res, "summary", res)
    assert isinstance(summary, dict)
    assert "npv_12" in summary
