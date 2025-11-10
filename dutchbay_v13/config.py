from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

def _parse_yaml_fallback(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        try:
            if v.lower() in ("true","false"):
                data[k] = (v.lower() == "true")
            elif "." in v or "e" in v.lower():
                data[k] = float(v)
            else:
                data[k] = int(v)
        except Exception:
            data[k] = v
    return data

def load_params(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix.lower() in (".yaml",".yml"):
        try:
            import yaml
            data = yaml.safe_load(text) or {}
        except Exception:
            data = _parse_yaml_fallback(text)
        return data
    elif p.suffix.lower() == ".json":
        import json
        return json.loads(text)
    else:
        raise ValueError(f"Unsupported params format: {p.suffix}")

def load_all_params(path: str | Path) -> tuple[dict, dict]:
    """Return (params_dict, debt_dict) from YAML/JSON.
    Accepts optional top-level 'debt' mapping.
    """
    d = load_params(path)
    debt = {}
    if isinstance(d, dict) and "debt" in d and isinstance(d["debt"], dict):
        debt = d.pop("debt")
    return d, debt
