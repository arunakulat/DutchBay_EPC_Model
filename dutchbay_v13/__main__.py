import argparse
import json
import sys
import time
import csv
from pathlib import Path


def _write_jsonl(items, outpath: Path):
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8") as f:
        for obj in items:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _write_csv(items, outpath: Path):
    cols = []
    for d in items:
        for k in d.keys():
            if k not in cols:
                cols.append(k)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for d in items:
            w.writerow({k: d.get(k, "") for k in cols})


def _write_annual_csv(items, outpath: Path):
    outpath.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, _ in enumerate(items, start=1):
        rows.append({"year": i, "cashflow": 0.0})
    with outpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "cashflow"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dutchbay_v13")
    sub = parser.add_subparsers(dest="command", required=True)
    p_sc = sub.add_parser("scenarios")
    p_sc.add_argument("--outdir", "-o", default="_out")
    p_sc.add_argument(
        "--format", "-f", choices=["text", "json", "jsonl", "csv"], default="text"
    )
    p_sc.add_argument("--save-annual", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "scenarios":
        from .scenario_runner import run_dir

        results = run_dir(Path.cwd(), base_cfg=None, mode="irr")
        ts = int(time.time())
        if args.format == "jsonl":
            _write_jsonl(
                results, Path(args.outdir) / f"scenario_000_results_{ts}.jsonl"
            )
        elif args.format == "csv":
            _write_csv(results, Path(args.outdir) / f"scenario_000_results_{ts}.csv")
        elif args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"Ran {len(results)} scenarios.")
            if results:
                first = results[0]
                irr = first.get("equity_irr_pct", first.get("equity_irr", 0) * 100.0)
                print(f"Example IRR: {irr:.2f}%")
        if args.save_annual:
            _write_annual_csv(
                results, Path(args.outdir) / f"scenario_000_annual_{ts}.csv"
            )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
