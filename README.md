# Linkability for top-level domains

How well are the popular tech platforms doing, at auto-linking all the [IANA top-level domains][iana]?

This is a volunteer-run project, and is adjacent to the [ICANN Universal Acceptance][ua] effort:

> Universal Acceptance (UA) ensures that all domain names, including new top-level domains (TLDs), Internationalized Domain Names (IDNs), and email addresses are treated equally and can be used by all Internet-enabled applications, devices, and systems.

# Goals

We have a few short term goals:

- **Gather data** — With a bit of scripting, we can show the % of TLDs that popular platforms are "auto-linking" in their UIs
- **Learn from the data** -- We'll publish the results in easy-to-use formats, for both humans (e.g. CSV), and computers (e.g. JSON, etc)
- **Keep the data current** — Courtesty of open source & CI/CD (e.g. GitHub Actions platform runners, or similar), we can have jobs run on a schedule, and save their results here in this repo
- **Track the data over time** — As the operating systems and frameworks evolve, we can see the auto-linking percentage change over time. Hopefully in the right direction.

# Glossary

## Zones

| Term | Definition |
|------|------------|
| **Zone** | A top-level domain (TLD) as listed in the IANA root zone database. Used interchangeably with "TLD" in this project. |
| **ccTLD** | Country-code TLD — a 2-letter ASCII zone representing a country or territory (e.g. `.uk`, `.de`, `.jp`). |
| **gTLD** | Generic TLD — any zone that is not a ccTLD (e.g. `.com`, `.app`, `.museum`). |
| **Brand TLD** | A gTLD operated by a specific company for brand use (e.g. `.google`, `.apple`, `.bmw`). Identified via ICANN registry agreement types in [iana-data][iana-data]. |

## Linkability

| Term | Definition |
|------|------------|
| **Auto-linking** | When a platform automatically detects text as a clickable URL based on its TLD, without requiring a protocol prefix (e.g. `example.ai` rendered as a link). |
| **Linked** | Boolean result: whether a given zone is auto-linked by a given platform version. |
| **Linkability** | The overall measure of how completely a platform auto-links IANA zones, expressed as counts and percentages. |

## Platforms

A **platform** is a software ecosystem whose standard library, runtime, or core framework includes URL/link auto-detection. Each platform has:

- A **platform ID** — lowercase identifier used in filenames, CLI commands, and data files
- A **platform type** — the category of software: `os`, `browser`, `framework`, or `app`
- A **detection engine** — the specific API or component that performs link detection
- A **version scheme** — how releases of that platform are identified

| Platform ID | Type | Detection Engine | Version Scheme | Version Example |
|-------------|------|-----------------|----------------|-----------------|
| `apple` | `os` | `NSDataDetector` ([Foundation][nsdd]) | macOS version | `26.3` |
| `android` | `os` | `Patterns.java` regex ([AOSP][android]) | Android version | `14` |
| `windows` | `os` | RichEdit | Windows version + build | `11.26100` |
| `chromium` | `browser` | URL parser | Chromium major version | `131` |
| `firefox` | `browser` | URL parser | Firefox version | `134` |
| `electron` | `framework` | Chromium-based | Electron version | `33.0.0` |

### Platform type values

| Type | Meaning |
|------|---------|
| `os` | Operating system standard library provides the detection (e.g. Apple Foundation, Android framework) |
| `browser` | Browser engine performs its own link detection (e.g. Chromium, Firefox) |
| `framework` | Application framework with link detection, often wrapping another engine (e.g. Electron wraps Chromium) |
| `app` | A specific application whose behavior we observe (e.g. WhatsApp, which delegates to the OS) |

### Platform notes

- **Apple** — `NSDataDetector` is shared across macOS, iOS, iPadOS, watchOS, tvOS, and visionOS via the Foundation framework. We version by macOS release since that's the CI-testable surface, but the results apply across all Apple platforms for a given OS generation.
- **Android** — The `Patterns.java` TLD regex is compiled into the Android framework. It's versioned by Android release (e.g. `14`), with the precise AOSP git ref recorded in snapshot metadata for reproducibility.
- **Chromium** — Distinct from Chrome (the browser product). We test the Chromium engine's link detection directly.
- **Electron** — Bundles Chromium, but may apply additional link detection. The underlying Chromium version is recorded in metadata.

## Reports

| Term | Definition |
|------|------------|
| **Check** | The automated test that exercises a platform's detection engine against all IANA zones. |
| **Snapshot** | A complete set of per-zone linkability results for one platform at one version. Stored as a CSV in `Reports/snapshots/{platform}/{version}.csv`. |
| **Manifest** | A JSON file (`Reports/manifest.json`) recording metadata for all snapshots (date, version, source ref, etc). |
| **Summary** | A derived CSV time-series (`Reports/summary.csv`) of aggregate linkability statistics across all snapshots. |

### Summary CSV columns

| Column | Description |
|--------|------------|
| `platform` | Platform ID (e.g. `apple`, `android`, `chromium`) |
| `platform_type` | Platform category: `os`, `browser`, `framework`, or `app` |
| `platform_version` | Platform-specific version string (e.g. `26.3`, `14`, `131`) |
| `check_date` | ISO 8601 date when the check was run |
| `zones_count` | Total IANA zones in the dataset |
| `cctld_count` | Number of ccTLDs in the dataset |
| `gtld_count` | Number of gTLDs in the dataset |
| `brand_count` | Number of brand gTLDs in the dataset |
| `linked_total` | Total zones auto-linked by the platform |
| `linked_cctlds` | Number of ccTLDs auto-linked |
| `linked_gtlds` | Number of gTLDs auto-linked |
| `linked_brands` | Number of brand gTLDs auto-linked |
| `linked_pct` | Overall linkability percentage (`linked_total / zones_count * 100`) |

# Platform coverage

These are the platforms we're looking to cover:

**Operating Systems**

- Android — [detection engine is here][android]
- Apple (iOS / macOS / etc.) — which share [`NSDataDetector`][nsdd]
- Windows

**Browsers**

- Chromium
- WebKit
- Firefox

**Frameworks**

- Electron

**Applications**

- WhatsApp — uses the OS-provided detection engine

# Related

- 2023-07-21 — [PSL repo discussion][psl-thread] about this issue, from Rami at the `.tube` registry

- - -

# Apple platforms

(This is a work-in-progress, and as of 2025-06-20 it's simply an initial spike on the idea, to see if it's worth pursuing further.)

This tool fetches the [authoritative zones list][iana] (e.g. "all top-level domains") from IANA, and checks to see which ones the Apple platform standard library "auto-links."

For example, we can assume that the [Apple Numbers spreadsheet app][numbers] is using this stdlib functionality to auto-link these domain names:

![Screenshot](Docs/Numbers-app-example.png)

The `.ar` (Argentina) domain is being linked, but the `.ai` (Anguilla) domain is not. `.ai` is a popular TLD, so ideally it would be linked as well.

## Data sources

### All zones

IANA provides the full, canonical zones list: https://data.iana.org/TLD/tlds-alpha-by-domain.txt

**Note:**

The IANA data server appears to update the date stamp at the top of their file daily, whether or not the contents of the file have changed.

```diff
- # Version 2025061800, Last Updated Wed Jun 18 07:07:02 2025 UTC
+ # Version 2025061902, Last Updated Fri Jun 20 07:07:01 2025 UTC

{no other changes}
```

…so there is functionality in the `downloadIanaZones()` function to account for this.

### Brand zones

There are hundreds of "brand" zones (e.g. `.apple`), and many of these are not in active use, so it's worth including these in our work here.

Brand TLDs are identified from the [case/iana-data][iana-data] project, which provides structured ICANN data including registry agreement types. A TLD is classified as a brand when `"brand"` appears in its `annotations.registry_agreement_types` field.

The `download brands` command fetches this data:

```bash
uv run linkability download brands              # Downloads tlds.json, extracts brand zones
```

The ~5MB `tlds.json` file is cached locally in `Data-Zones/tlds.json` (gitignored) and the derived brand list is written to `Data-Zones/zones-brand.txt`.

### Local data cache

There are some `.txt` files in the `Data-Zones/` dir, generated on 2025-06-19, which this code is currently using to do its analysis.

## Local usage

Setup

```bash
make deps                                            # Install uv (if needed) + sync dependencies
```

### CLI Commands

```bash
uv run linkability --help                            # Show all commands
```

Run platform checks

```bash
uv run linkability check apple                       # Run Apple platform check (macOS only)
uv run linkability check android                     # Run Android platform check
```

Generate reports

```bash
uv run linkability report summary --platform apple   # Print text summary to console
uv run linkability report csv --platform apple       # Generate Reports/Report-Apple.csv
```

List linked zones

```bash
uv run linkability list linked --type cctld          # Show linked ccTLD zones
uv run linkability list linked --type gtld           # Show linked gTLD zones
uv run linkability list linked --type brand          # Show linked brand gTLD zones
```

Download latest zone data

```bash
uv run linkability download zones                    # Download latest TLD zones from IANA
uv run linkability download brands                   # Fetch brand zones from local ZoneDB CLI
```

Validate data integrity

```bash
uv run linkability validate missing-brands           # Show brand zones missing from root zone
uv run linkability validate cctld-brands             # Verify no ccTLDs marked as brands
```

## Todo

- [ ] Names of things - Many of the things in here (like the functions) could probably be named better.
- [x] ~~The `github.com/zonedb/zonedb` (Go) project is a pre-req~~ — Replaced with `case/iana-data` (no external tooling needed)
- [ ] Tests - there are a few tests, but there's always room for more 😅
- [ ] `Package.swift` - There are multiple `.executableTarget()`s in here, there's probably a more conventional way to do this?
- [ ] Get this running in GitHub Actions, probably on e.g. a monthly schedule (given Apple's OS update release cadence)
- [x] ~~Update this Readme once the `--json` ZoneDB PR is merged~~ — No longer needed (ZoneDB dependency removed)
- [ ] Maybe generalize this functionality away from just the Apple ecosystem? This CLI + reporting pattern is probably generally useful across the other platforms. (it could stay in Swift, or be ported to any other suitable language; I started with Swift because it seemed like the entrypoint for obtaining this info from the Apple stdlib)

<!-- Reference links -->

[android]: https://cs.android.com/android/platform/superproject/main/+/main:frameworks/base/core/java/android/util/Patterns.java;l=114
[iana]: https://data.iana.org/TLD/tlds-alpha-by-domain.txt
[nsdd]: https://developer.apple.com/documentation/foundation/nsdatadetector
[numbers]: https://apps.apple.com/us/app/numbers/id361304891
[psl-thread]: https://github.com/publicsuffix/list/issues/1807
[ua]: https://www.icann.org/ua
[iana-data]: https://github.com/case/iana-data
[zonedb]: https://zonedb.org/
