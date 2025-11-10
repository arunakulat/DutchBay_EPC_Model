from __future__ import annotations

from typing import Any, Dict, Tuple
import os
import io
import yaml


def _parse_yaml_fallback(text: str) -> Dict[str, Any]:
    """
    Super-tolerant parser for key: value lines (only for emergencies).
    Booleans and numbers are coerced when obvious.
    """
    data: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        try:
            if v.lower() in ("true", "false"):
                data[k] = v.lower() == "true"
            else:
                data[k] = float(v) if "." in v else int(v)
        except Exception:
            data[k] = v
    return data


def _flatten_grouped(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten shallow groups like {'finance': {...}, 'plant': {...}} into one level.
    Prefers top-level keys if collisions occur.
    """
    flat: Dict[str, Any] = dict(cfg)
    for k, v in list(cfg.items()):
        if isinstance(v, dict) and k not in ("cashflows",):
            for sk, sv in v.items():
                flat.setdefault(sk, sv)
    return flat


def _split_power_and_debt(d: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    debt = d.pop("debt", {}) if isinstance(d, dict) else {}
    return d, debt


def load_model_config(
    source: str | os.PathLike | io.StringIO,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load YAML from a path or text stream. If YAML fails, use a tolerant fallback.
    Returns (flat_config, debt_section).
    """
    text: str
    if hasattr(source, "read"):
        text = str(source.read())
    else:
        p = os.fspath(source)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()

    try:
        cfg = yaml.safe_load(text) or {}
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = _parse_yaml_fallback(text)

    flat = _flatten_grouped(cfg)
    return _split_power_and_debt(flat)
