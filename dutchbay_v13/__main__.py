from __future__ import annotations
import sys
from . import cli


def main():
    argv = list(sys.argv[1:])
    if argv and argv[0] in {
        "baseline",
        "cashflow",
        "debt",
        "epc",
        "irr",
        "montecarlo",
        "optimize",
        "report",
        "sensitivity",
        "utils",
        "validate",
        "scenarios",
    }:
        mode = argv.pop(0)
        return cli.main(["--mode", mode] + argv)
    return cli.main(argv)


if __name__ == "__main__":
    sys.exit(main())
