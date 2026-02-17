# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Measures how well popular tech platforms auto-link IANA top-level domains (TLDs). Adjacent to the ICANN Universal Acceptance (UA) initiative. Implements platform checks for Apple (via `NSDataDetector`) and Android (via AOSP `Patterns.java` regex). Electron and Windows checks are stubbed for future implementation.

## Build & Run

This is a Python 3.11+ project with a minimal Swift helper for the Apple platform check.

```bash
make deps                                    # Create venv + install package with dev deps
make test                                    # Run pytest suite
make lint                                    # Run ruff linter
make apple-check                             # Build the Swift Apple check binary (macOS only)
```

### CLI Commands

```bash
linkability --help                           # Show all commands
linkability download zones                   # Download latest TLD zones from IANA
linkability download brands                  # Fetch brand zones from local ZoneDB CLI
linkability report csv --platform apple      # Generate Reports/Report-Apple.csv
linkability report summary --platform apple  # Print text summary to console
linkability list linked --type cctld         # Show linked ccTLD zones
linkability list linked --type gtld          # Show linked gTLD zones
linkability list linked --type brand         # Show linked brand gTLD zones
linkability validate missing-brands          # Show brand zones missing from root zone
linkability validate cctld-brands            # Verify no ccTLDs marked as brands
linkability check apple                      # Run Apple platform check
linkability check android                    # Run Android platform check
```

## Tests

```bash
.venv/bin/python3 -m pytest tests/ -v        # Run all tests
.venv/bin/python3 -m pytest tests/test_zones.py  # Run specific test file
```

Uses pytest. Test data lives in `tests/data/`.

## Architecture

Python orchestrator with platform-specific check plugins:

- **`src/linkability/`** — Core Python package:
  - `cli.py` — argparse CLI, `console_scripts` entry point
  - `zones.py` — `read_zones()`, `download_iana_zones()`, `download_brand_zones()`. Parses zone files, stripping comments/blanks, lowercasing, decoding Punycode via the `idna` package.
  - `classify.py` — `is_cctld()` (2 ASCII chars), `classify_zone()` returns type and brand status
  - `analyze.py` — `ZoneSummary` dataclass with percentage properties, `compute_summary()` takes check-agnostic `dict[str, bool]` results
  - `reports.py` — `generate_csv_report()` writes platform-parameterized CSV, `format_summary()` produces human-readable stats
  - `validate.py` — `show_missing_brands()`, `test_cctld_brands()` for data consistency checks

- **`src/linkability/checks/`** — Platform check plugins:
  - `base.py` — `Check` ABC: `platform_name`, `is_available()`, `check_zones()`
  - `apple.py` — Calls Swift binary via subprocess, parses JSON. Auto-builds if binary not found.
  - `android.py` — Fetches AOSP `Patterns.java`, extracts TLD regex, expands character classes to individual TLDs
  - `electron.py` — Stub (PSL-based approach documented)
  - `windows.py` — Stub (RichEdit-based approach documented)

- **`checks/apple/`** — Minimal Swift package (no dependencies):
  - Reads zone names from stdin, runs `NSDataDetector` on `"nic.{zone}"`, outputs JSON `{"results": {...}}`

## Data Flow

1. Zone data is downloaded and cached in `Data-Zones/` (zones-full.txt from IANA, zones-brand.txt from ZoneDB CLI)
2. `read_zones()` loads and normalizes zone files (lowercase, Punycode-decoded, comments stripped)
3. A platform check tests each zone (e.g., Apple constructs `"nic.{zone}"` and checks `NSDataDetector`)
4. Results are output as CSV or text summary, categorized by ccTLD/gTLD and brand/non-brand

## Dependencies

- **Python:** `idna>=3.6` (Punycode/IDN decoding). Dev: `pytest>=8.0`, `ruff>=0.4`.
- **Swift** (Apple check only): No external dependencies, uses Foundation framework
- **zonedb CLI** (external) — Required only for `linkability download brands`. Expects the ZoneDB repo at `~/git/domainr/zonedb`

## Key References

- IANA TLD data source: https://data.iana.org/TLD/tlds-alpha-by-domain.txt
- Apple NSDataDetector: https://developer.apple.com/documentation/foundation/nsdatadetector
- Android Patterns.java: https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/util/Patterns.java
- ZoneDB project: https://zonedb.org/
