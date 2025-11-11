# Changelog
All notable changes to this project will be documented in this file.

The format is based on **Keep a Changelog** and this project adheres to **Semantic Versioning**.

## [Unreleased]

### Added
- Additional smoke tests to harden CLI and adapter behavior.
- DSCR smoke scaffold (planned) and matrix scenario runner (planned).

### Changed
- Minor doc clarifications and inline comments (planned).

### Fixed
- N/A

---

## [0.1.0] - 2025-11-12

### Added
- **Strict/Relaxed validation** pipeline with `VALIDATION_MODE` and JSON Schema support for `Financing_Terms`.
- **Git-friendly CLI outputs**: always writes `_out/summary.json`; optional CSV/JSONL result exports.
- **Debt layer** with tranche mix caps (`lkr_max`, `dfi_max`, `usd_commercial_min`), sculpted amortization by target DSCR, DSRA hooks.
- **Architecture tests** to enforce **single IRR/NPV implementation** in `finance/irr.py`.
- **Smoke tests** for CLI end-to-end and adapter + validator round-trip.

### Changed
- **Refactor:** split concerns:
  - `finance/irr.py` now hosts the sole IRR/NPV implementation and cashflow builders only.
  - `adapters.py` slimmed to orchestration (params → cashflow → debt → metrics).
  - `params.py` introduced as the single source for parameter resolution and guards.
- **Scenario runner** writes stable, timestamped result files; improved progress messaging.
- **Validation** now rejects unknown top-level keys in strict mode and allows harmless metadata in relaxed mode.

### Fixed
- Intermittent import loops between adapters/irr/runner.
- Indentation/tabs issues in `scenario_runner.py` under some editors.
- Site-packages false positives in the IRR singleton test.

[Unreleased]: https://github.com/your-org/your-repo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/your-repo/releases/tag/v0.1.0