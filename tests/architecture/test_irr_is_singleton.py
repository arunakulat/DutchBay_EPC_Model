import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
IRR = ROOT / "dutchbay_v13" / "finance" / "irr.py"

EXCLUDE_DIRS = {
    ".venv", "venv", ".venv311", ".git", ".pytest_cache", "build",
    "dist", "__pycache__", ".mypy_cache", ".tox", ".eggs"
}

def _skip(p: Path) -> bool:
    parts = set(p.parts)
    if "site-packages" in parts or "dist-packages" in parts:
        return True
    if any(d in parts for d in EXCLUDE_DIRS):
        return True
    return False

def test_only_irr_module_defines_irr_and_npv():
    hits = []
    for p in ROOT.rglob("*.py"):
        if _skip(p):
            continue
        if p == IRR:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\bdef\s+irr\s*\(", text) or re.search(r"\bdef\s+npv\s*\(", text):
            hits.append(str(p))
    assert not hits, f"Found IRR/NPV defs outside finance/irr.py: {hits}"
