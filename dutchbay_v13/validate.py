from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# Public API expected by the rest of the codebase/tests
__all__ = ["validate_params_dict", "load_params_from_file"]

# Top-level keys we recognize in strict mode (relaxed mode allows extras)
_ALLOWED_TOP_KEYS = {
    "name",
    "project",
    "capex",
    "opex",
    "fx",
    "Financing_Terms",
    "metrics",
    "scenarios",  # optional
}


# -----------------------
# YAML loading utilities
# -----------------------
def _read_yaml_file(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # lazy import to avoid hard dependency during test collection
    except Exception as exc:
        print("ERROR: PyYAML is required to read configuration files. Please install pyyaml.", file=sys.stderr)
        raise SystemExit(2) from exc

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Failed to parse YAML: {path} -> {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if not isinstance(data, dict):
        print(f"ERROR: YAML root must be a mapping (dict). Got: {type(data).__name__}", file=sys.stderr)
        raise SystemExit(2)
    return data


def load_params_from_file(path: Path) -> Dict[str, Any]:
    """Load and return the parameter mapping from YAML."""
    return _read_yaml_file(Path(path))


# -----------------------------------------
# Optional JSON Schema validation (scoped)
# -----------------------------------------
def _find_schema_paths() -> Iterable[Path]:
    """Discover schema roots. Built-in + optional extra paths."""
    roots: list[Path] = []
    # Local package schema folder: dutchbay_v13/inputs/schema
    pkg_root = Path(__file__).resolve().parent
    default_schema_root = pkg_root / "inputs" / "schema"
    if default_schema_root.is_dir():
        roots.append(default_schema_root)

    # Optional: allow extension via module-level EXTRA_SCHEMA_PATHS (if present)
    try:
        from . import schema as _schema_mod  # type: ignore
        extra = getattr(_schema_mod, "EXTRA_SCHEMA_PATHS", None)
        if isinstance(extra, (list, tuple)):
            for p in extra:
                pp = Path(str(p)).expanduser()
                if pp.is_dir():
                    roots.append(pp)
    except Exception:
        pass  # no schema extension available

    # Optional: env override (colon-separated)
    env_extra = os.environ.get("EXTRA_SCHEMA_PATHS")
    if env_extra:
        for token in env_extra.split(os.pathsep):
            pp = Path(token).expanduser()
            if pp.is_dir():
                roots.append(pp)

    # Deduplicate while preserving order
    seen = set()
    out: list[Path] = []
    for r in roots:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


def _maybe_validate_financing_terms(params: Dict[str, Any], *, strict: bool) -> None:
    """
    If jsonschema + financing_terms.schema.yaml are available, validate
    params['Financing_Terms'] against it. On error: strict -> SystemExit; relaxed -> warn.
    """
    ft = params.get("Financing_Terms")
    if not isinstance(ft, dict):
        return  # nothing to validate or not a mapping

    try:
        import yaml
        import jsonschema
        from jsonschema import Draft202012Validator as _Validator  # use modern draft if present
    except Exception:
        return  # schema validation is optional; skip quietly

    # Locate the specific schema file by name in any known schema root
    schema_doc: Optional[Dict[str, Any]] = None
    for root in _find_schema_paths():
        cand = root / "financing_terms.schema.yaml"
        if cand.is_file():
            try:
                schema_doc = yaml.safe_load(cand.read_text(encoding="utf-8"))
            except Exception:
                schema_doc = None
            if isinstance(schema_doc, dict):
                break

    if not isinstance(schema_doc, dict):
        return  # no schema found; skip

    try:
        _Validator.check_schema(schema_doc)  # early sanity
        validator = _Validator(schema_doc)
        validator.validate(ft)
    except Exception as exc:
        msg = f"Schema validation error for Financing_Terms: {exc}"
        if strict:
            print(f"ERROR: {msg}", file=sys.stderr)
            raise SystemExit(2)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)


# -------------------------------
# Core validation entry point
# -------------------------------
def validate_params_dict(p: Dict[str, Any], mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate a parameter mapping.

    - Strict: reject unknown TOP-LEVEL keys (exact match to _ALLOWED_TOP_KEYS).
              Also applies schema validation to Financing_Terms if available.
    - Relaxed (default): allow extras; schema validation warnings only.

    Returns the same mapping (pass-through) when successful.
    Raises SystemExit(2) on fatal validation errors (strict unknown keys or schema errors).
    """
    m = (mode or os.environ.get("VALIDATION_MODE") or "relaxed").strip().lower()
    strict = (m == "strict")

    if strict:
        unknown = sorted(set(p.keys()) - _ALLOWED_TOP_KEYS)
        if unknown:
            print(f"ERROR: unknown top-level keys (strict mode): {unknown}", file=sys.stderr)
            raise SystemExit(2)

    # Optional JSON Schema check focused on Financing_Terms
    _maybe_validate_financing_terms(p, strict=strict)
    return p


# -------------------------------
# Tiny CLI for local validation
# -------------------------------
def _build_parser():
    import argparse

    ap = argparse.ArgumentParser(prog="dutchbay_v13.validate")
    ap.add_argument("file", help="Path to YAML parameters file")
    ap.add_argument(
        "--mode",
        choices=["strict", "relaxed"],
        default=os.environ.get("VALIDATION_MODE", "relaxed"),
        help="Validation mode (default from $VALIDATION_MODE or 'relaxed').",
    )
    return ap


def _main(argv: Optional[list[str]] = None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)
    params = load_params_from_file(Path(args.file))
    validate_params_dict(params, mode=args.mode)
    print("OK: validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

    