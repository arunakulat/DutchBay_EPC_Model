# dutchbay_v13/cli.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Only imports the thin runner; heavy math stays behind scenario_runner
from .scenario_runner import run_dir  # run_dir(Path|str, Path, mode="irr", fmt="csv", save_annual=False)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="dutchbay_v13",
        description="Dutch Bay EPC high-level financial model CLI",
    )
    p.add_argument(
        "--mode",
        default="irr",
        choices=["irr", "sensitivity", "montecarlo", "optimize"],
        help="Execution mode (default: irr).",
    )
    p.add_argument(
        "--config",
        required=False,
        default=None,
        help="Path to a single YAML, or a directory of scenarios/overrides. If omitted, defaults to package demos.",
    )
    p.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory to write result files (default: outputs). Will be created if missing.",
    )
    p.add_argument(
        "--format",
        dest="fmt",
        default="csv",
        choices=["csv", "jsonl"],
        help="Output format for summary/result files (default: csv).",
    )
    p.add_argument(
        "--save-annual",
        action="store_true",
        help="If set, write per-year (annual) rows alongside summary results.",
    )
    v = p.add_mutually_exclusive_group()
    v.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation (unknown keys raise).",
    )
    v.add_argument(
        "--relaxed",
        action="store_true",
        help="Enable relaxed validation (unknown keys ignored if harmless).",
    )
    return p.parse_args(argv)


def _apply_validation_mode(ns: argparse.Namespace) -> None:
    # Default: leave env as-is; flags override explicitly.
    if ns.strict:
        os.environ["VALIDATION_MODE"] = "strict"
    elif ns.relaxed:
        os.environ["VALIDATION_MODE"] = "relaxed"
    # else: respect existing environment


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    _apply_validation_mode(ns)

    # Resolve paths
    outputs_dir = Path(ns.outputs_dir).resolve()
    cfg_path: Path | None = Path(ns.config).resolve() if ns.config else None

    # Ensure outputs directory exists
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Delegate to the scenario runner. It accepts either a YAML file or a directory.
    try:
        rc = run_dir(cfg_path or "", outputs_dir, mode=ns.mode, fmt=ns.fmt, save_annual=ns.save_annual)
    except SystemExit as e:
        # Propagate strict-validation exit codes cleanly through CLI
        return int(e.code) if isinstance(e.code, int) else 2
    except Exception as e:
        # Fail noisily with non-zero; keep traceback for debugging
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # run_dir may return None or an int; normalize to shell-friendly code
    return int(rc) if isinstance(rc, int) else 0


__all__ = ["main"]

