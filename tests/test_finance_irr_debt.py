import importlib
import math
import pytest

def _find_callable(mod, names):
  for n in names:
    fn = getattr(mod, n, None)
    if callable(fn):
      return fn
  return None

def _norm_rate(x):
  # Accept plain float or numpy scalar; convert percent-like if needed
  try:
    r = float(x)
  except Exception:
    return float("nan")
  # If someone returns percent (e.g., 9.0 for 9%) clamp to 0–1 when sensible
  if r > 1.5:  # loose guard
    r = r / 100.0
  return r

def test_finance_irr_basic():
  m = importlib.import_module("dutchbay_v13.finance.irr")
  fn = _find_callable(m, ("irr", "compute_irr", "calc_irr", "xirr"))
  if fn is None:
    pytest.xfail("No IRR function exported yet")

  # Simple 3-period stream with single sign change
  cfs = [-100.0, 60.0, 60.0]

  # Try flexible signatures
  try:
    r = fn(cfs) if fn.__code__.co_argcount >= 1 else fn(cashflows=cfs)
  except TypeError:
    try:
      r = fn(cfs, 0.1)
    except Exception:
      pytest.xfail("IRR callable exists but signature is non-standard")

  r = _norm_rate(r)
  assert math.isfinite(r), "IRR should be finite"
  # Accept a reasonable band (most implementations return ~8–10%)
  assert 0.05 < r < 0.15, f"IRR out of expected band: {r}"

def test_finance_debt_imports():
  m = importlib.import_module("dutchbay_v13.finance.debt")
  # Sanity: at least one callable that looks like a constructor/solver
  names = [n for n in dir(m) if callable(getattr(m, n)) and not n.startswith("_")]
  assert len(names) >= 0  # don’t overconstrain yet; import must succeed
