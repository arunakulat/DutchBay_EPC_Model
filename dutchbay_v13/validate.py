# dutchbay_v13/validate.py
from __future__ import annotations
import os, sys, json
from pathlib import Path
from typing import Any, Dict, Iterable, List
import yaml

def _mode_from_env_or_flag(flag: str | None) -> str:
    if flag in ("strict", "relaxed"):
        return flag
    env = (os.environ.get("VALIDATION_MODE") or "").lower()
    return env if env in ("strict", "relaxed") else "relaxed"

def validate_params_dict(data: Dict[str, Any], *, mode: str = "relaxed") -> None:
    """
    Minimal guardrails:
      - relaxed: require {project, capex}
      - strict : require {project, capex, metrics} and reject unknown top-level keys
    """
    required_base = {"project", "capex"}
    required = set(required_base)
    if mode == "strict":
        required |= {"metrics"}

    missing = [k for k in required if k not in data]
    if missing:
        raise SystemExit(f"missing required keys: {missing}")

    if mode == "strict":
        allowed = required | {"Financing_Terms", "annual"}
        unknown = [k for k in data.keys() if k not in allowed]
        if unknown:
            raise SystemExit(f"unknown top-level keys (strict mode): {unknown}")

    # basic value checks (mode-agnostic)
    capex_total = float(data.get("capex", {}).get("usd_total", 0.0))
    if capex_total < 0:
        raise SystemExit("capex.usd_total must be >= 0")

    ft = data.get("Financing_Terms")
    if ft is not None:
        dr = float(ft.get("debt_ratio", 0.0))
        if not (0.0 <= dr <= 1.0):
            raise SystemExit("Financing_Terms.debt_ratio must be in [0,1]")

def validate_debt_dict(data: Dict[str, Any], *, mode: str = "relaxed") -> None:
    ft = data.get("Financing_Terms") or {}
    if mode == "strict" and "debt_ratio" not in ft:
        raise SystemExit("Financing_Terms missing required keys: ['debt_ratio']")
    dr = float(ft.get("debt_ratio", 0.0))
    if not (0.0 <= dr <= 1.0):
        raise SystemExit("Financing_Terms.debt_ratio must be in [0,1]")

def load_params_from_file(path: Path) -> Dict[str, Any]:
    p = Path(path)
    if p.is_dir():
        # scenario_runner handles directories; keep this function file-only
        raise SystemExit(f"{p} is a directory (expected a file)")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    return json.loads(text or "{}")

def _iter_input_files(p: Path) -> Iterable[Path]:
    if p.is_file():
        yield p
    elif p.is_dir():
        for ext in ("*.yaml", "*.yml", "*.json"):
            yield from sorted(p.rglob(ext))

def _main(argv: List[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="dutchbay_v13.validate", add_help=True)
    parser.add_argument("paths", nargs="+", help="YAML/JSON files or directories to validate")
    parser.add_argument("--mode", choices=["strict", "relaxed"], default=None, help="validation mode")
    args = parser.parse_args(argv)

    mode = _mode_from_env_or_flag(args.mode)
    had_error = False

    for raw in args.paths:
        target = Path(raw)
        any_seen = False
        try:
            for f in _iter_input_files(target):
                if not f.is_file():
                    continue
                any_seen = True
                try:
                    data = load_params_from_file(f)
                    validate_params_dict(data, mode=mode)
                    print(f"OK: {f}")
                except SystemExit as e:
                    print(f"{f}: {e}", file=sys.stderr)
                    had_error = True
                except Exception as e:
                    print(f"{f}: ERROR: {e}", file=sys.stderr)
                    had_error = True
            if not any_seen:
                print(f"{target}: no YAML/JSON files found", file=sys.stderr)
                had_error = True
        except SystemExit as e:
            print(str(e), file=sys.stderr)
            had_error = True

    return 1 if had_error else 0

if __name__ == "__main__":
    raise SystemExit(_main())