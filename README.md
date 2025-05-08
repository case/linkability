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

# Platform coverage

These are the ~platforms we're looking to monitor:

## Operating Systems

- Android
- iOS / macOS / etc. — which share a common library, [`NSDataDetector`][nsdd]
- Windows

## Browsers

- Chromium
- WebKit
- Firefox

## Frameworks

- Electron

## Applications

- WhatsApp — It uses the OS-provided functionality

# Related

- 2023-07-21 — [PSL repo discussion][psl-thread] about this issue, from Rami at the `.tube` registry

[iana]: https://www.iana.org/domains/root/db
[nsdd]: https://developer.apple.com/documentation/foundation/nsdatadetector
[psl-thread]: https://github.com/publicsuffix/list/issues/1807
[ua]: https://www.icann.org/ua
