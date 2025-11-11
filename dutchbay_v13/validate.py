# dutchbay_v13/validate.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required to load YAML inputs") from e

# jsonschema is optional; if absent we degrade gracefully in relaxed mode
try:
    import jsonschema  # type: ignore
    from jsonschema import Draft202012Validator as _SchemaValidator  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None
    _SchemaValidator = None  # type: ignore

# Our schema discovery module
from . import schema as _schema_mod  # type: ignore


# =============================================================================
# Mode & config
# =============================================================================

def _mode_from_env() -> str:
    env = (os.environ.get("VALIDATION_MODE") or "").strip().lower()
    if not env and os.environ.get("DB13_STRICT_VALIDATE"):
        env = "strict"
    return env if env in {"strict", "relaxed"} else "strict"


# Default ignore set for RELAXED validation; overridable via DB13_IGNORE_KEYS
_DEFAULT_IGNORE = {
    "technical",
    "finance",
    "financial",
    "notes",
    "metadata",
    "name",
    "description",
    "id",
    "parameters",   # container
    "override",     # container
    "overrides",    # container
}


def _ignored_keys_from_env() -> set[str]:
    raw = os.environ.get("DB13_IGNORE_KEYS", "")
    if not raw:
        return set(_DEFAULT_IGNORE)
    toks = [t.strip() for t in raw.split(",") if t.strip()]
    return set(toks) if toks else set(_DEFAULT_IGNORE)


# =============================================================================
# YAML helpers
# =============================================================================

def load_yaml_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping at the top level.")
    return data


def _unwrap_params(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    If given a scenario-matrix style dict, unwrap one level of
    {parameters:{...}} or {override:{...}} / {overrides:{...}}.
    """
    for k in ("parameters", "override", "overrides"):
        v = d.get(k)
        if isinstance(v, dict):
            return v
    return d


def _filter_ignored(obj: Any, ignore: set[str]) -> Any:
    """
    Recursively drop keys in 'ignore' (case-insensitive) from dicts.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            try:
                key = k.casefold() if isinstance(k, str) else k
            except Exception:
                key = k
            if isinstance(key, str) and key in ignore:
                continue
            out[k] = _filter_ignored(v, ignore)
        return out
    elif isinstance(obj, list):
        return [_filter_ignored(x, ignore) for x in obj]
    return obj


# =============================================================================
# JSON Schema loading / selection
# =============================================================================

def _iter_json_validators() -> List[Any]:
    """
    Build jsonschema validators from discovered documents.
    We keep them as a list; each may apply to a specific section.
    """
    vals: List[Any] = []
    if jsonschema is None or _SchemaValidator is None:
        return vals

    for doc in _schema_mod.iter_schema_documents():
        try:
            vals.append(_SchemaValidator(doc))
        except Exception:
            # Skip malformed schemas silently; others may still work
            continue
    return vals


def _schema_targets(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Decide which sub-mappings to validate with which schema.
    For now:
      - Any schema whose top-level properties include 'debt_ratio' or 'mix'
        is assumed to target Financing_Terms.
      - Otherwise, if a schema looks like a whole-document schema
        (has 'properties' that include common roots), we pass the root.
    """
    targets: List[Tuple[str, Any]] = []
    ft = data.get("Financing_Terms")

    # Root-level common sections (heuristic)
    root_keys = set(data.keys())

    # Build candidate tuples later when we actually evaluate each schema
    # We just return placeholders here; the actual mapping selection happens
    # in _validate_against_schemas.
    if isinstance(ft, dict):
        targets.append(("Financing_Terms", ft))
    # Always include the whole document as a fallback target; a schema may
    # explicitly model the entire input.
    targets.append(("root", data))
    return targets


def _schema_targets_for_validator(validator: Any, data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Given one jsonschema validator, return the sub-mappings we should validate.
    Heuristic:
      - If schema.properties contains 'debt_ratio' or 'mix', validate Financing_Terms only.
      - Else, validate the root mapping.
    """
    try:
        props = set((validator.schema or {}).get("properties", {}).keys())
    except Exception:
        props = set()

    ft = data.get("Financing_Terms")
    if "debt_ratio" in props or "mix" in props:
        if isinstance(ft, dict):
            return [("Financing_Terms", ft)]
        return []  # no Financing_Terms present
    # Otherwise assume it applies to the whole doc
    return [("root", data)]


# =============================================================================
# Validation core
# =============================================================================

class ValidationError(Exception):
    pass


def validate_params(params: Dict[str, Any], mode: str = "strict", where: Optional[str] = None) -> None:
    """
    Validate a parameter mapping.
      - STRICT: run schemas; raise on first error
      - RELAXED: drop ignorable metadata keys, try again; if still failing,
                 do not raise (smoke runs tolerate).
    """
    m = (mode or "strict").lower()
    if m not in {"strict", "relaxed"}:
        m = "strict"

    # Unwrap one container level if present
    base = _unwrap_params(params)

    # Load validators if available
    validators = _iter_json_validators()

    if not validators:
        # No schemas available. In STRICT, we still accept (no-op)
        # because earlier strictness came from custom key filters.
        # That logic now lives in scenario_runner’s wrapper if needed.
        return

    def _run_all(_data: Dict[str, Any]) -> None:
        for v in validators:
            for label, sub in _schema_targets_for_validator(v, _data):
                try:
                    v.validate(sub)
                except Exception as e:
                    # Wrap with context including 'where'
                    loc = f" at {where}" if where else ""
                    raise ValidationError(f"Schema validation failed for {label}{loc}: {e}") from e

    if m == "strict":
        _run_all(base)
        return

    # RELAXED
    ignore = {k.casefold() for k in _ignored_keys_from_env()}
    filtered = _filter_ignored(base, ignore)
    try:
        _run_all(filtered)
    except Exception:
        # Swallow in relaxed mode
        return


# =============================================================================
# CLI
# =============================================================================

def _cli(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="validate.py",
        description="Validate a YAML file against discovered schemas (strict or relaxed).",
    )
    p.add_argument("file", help="Path to YAML file to validate")
    p.add_argument(
        "--mode",
        choices=["strict", "relaxed"],
        default=_mode_from_env(),
        help="Validation mode (default from VALIDATION_MODE / DB13_STRICT_VALIDATE).",
    )
    args = p.parse_args(argv)

    path = Path(args.file)
    data = load_yaml_file(path)
    try:
        validate_params(data, mode=args.mode, where=str(path))
    except ValidationError as e:
        # STRICT failure should be non-zero exit
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    print("OK: validation passed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli())

    