# Community DNS Apps for Technitium — zero-trust audit

Source of truth: GitHub code-search on `IDnsApplicationRequestHandler` + `topic:technitium-dns-app` + repository metadata (audited on 2026-05-12). Scope = real DNS Apps (.NET DLL loaded in-process). Out of scope = external clients (Android, Web UI, ExternalDNS webhook, YAML configurators, Home Assistant integrations). 8 community apps found beyond the official store.

For the evaluation framework (criteria, trust tiers), see the [`app` module](../plugins/modules/app.py) documentation and the project memory `project_dns_apps_zero_trust_framework`.

## Summary

| App | Author | LoC | Network | Stars | Last push | Licence | CI build | Tier |
|---|---|---|---|---|---|---|---|---|
| [LANCache-TDNSApp](https://github.com/ruifung/LANCache-TDNSApp) | ruifung | 890 | lancache.net (configurable) | 20 | 2026-04-29 | GPL-3.0 | yes (`release.yml`) | **1** |
| [technitium-content-filter](https://github.com/coreyleavitt/technitium-content-filter) | coreyleavitt | 2389 | user-supplied blocklists | 1 | 2026-04-14 | Apache-2.0 | yes (5 workflows) | **2** |
| [MispConnectorApp](https://github.com/DeltaZulu-OU/MispConnectorApp) | DeltaZulu-OU | 644 | user-supplied MISP REST endpoint | 0 | 2026-05-12 | GPL-3.0 | yes (`release.yml`) | **2** |
| [technilux-apps/AdvancedBlockingPlus](https://github.com/elabx-org/technilux-apps) | elabx-org | ~2000 (App.cs) | user-supplied blocklist URLs | 0 | 2026-01-29 | none | yes | **2** |
| [technilux-apps/AdvancedForwardingPlus](https://github.com/elabx-org/technilux-apps) | elabx-org | ~1000 | user-supplied forwarders | 0 | 2026-01-29 | none | yes | **2** |
| [technilux-apps/NetworkHelper](https://github.com/elabx-org/technilux-apps) | elabx-org | ~800 | file I/O only | 0 | 2026-01-29 | none | yes | **2** |
| [ConditionalDualForwardResolver](https://github.com/idavidmarshali/ConditionalDualForwardResolver) | idavidmarshali | 249 | DNS only (forwarders) | 0 | 2026-01-27 | none | no | **3** |
| [TechnitiumLogDb](https://github.com/nazo6/TechnitiumLogDb) | nazo6 | 260 | external HTTP log sink | 0 | 2023-03-24 | none | no | **3** |
| [technitium_IpWildcard](https://github.com/bmacao/technitium_IpWildcard) | bmacao | 437 | none (parses query name) | 0 | 2022-07-25 | GPL-3.0 | no | **3** |

Tier 4 / dismissed without detail: `tonestone57/Technitium` (account created 2025-06, 11 MB repo = a full fork of the official DnsServer with no community-app intent — not an app, ignore).

## Per-app details

### LANCache-TDNSApp — Tier 1

- Repo: <https://github.com/ruifung/LANCache-TDNSApp>
- Author: Yip Rui Fung, on GitHub since 2011, 88 public repos, active blog at <https://yrf.me>
- Purpose: resolves gaming CDN domains (Steam, Origin, Battle.net, …) to a local LANCache IP for download caching
- Evaluation:
  - Source: public, complete
  - Licence: GPL-3.0
  - Last release: v1.5.0 (2026-04-29) — active
  - LoC: 890 (App 18 KB + handler 9 KB + base 0.7 KB) → auditable in 1–2 hours
  - Network: `HttpClient` ONLY for pulling the LANCache domain list from `lancache.net` (configurable endpoint) — no third-party telemetry
  - Dependencies: `DnsServerCore.ApplicationCommon` + `TechnitiumLibrary.Net` via pinned submodules. NUnit/Moq tests. No third-party runtime NuGet packages.
  - Reproducible build: GitHub Actions (`build.yml`, `release.yml`), release ZIP signed by `github-actions[bot]`
  - Adoption: 20 stars, 1 fork, 0 open issues
- **Verdict**: credible author + GPL + clean CI + single configurable outbound endpoint. The most solid out-of-store candidate.

### technitium-content-filter — Tier 2

- Repo: <https://github.com/coreyleavitt/technitium-content-filter>
- Author: Corey Leavitt, on GitHub since 2016, employer "24M Technologies" — real, verifiable identity
- Purpose: content filtering (DNS rewrite/block) with per-client profiles, scheduling and blocklists
- Evaluation:
  - Source: public, professional layout (Services/Models/Web UI/docs/tests/Stryker mutation testing/CodeQL)
  - Licence: Apache-2.0
  - Last push: 2026-04-14, **no release tag yet** — young project (created 2026-03-10)
  - LoC: 2389 (excluding tests) — upper limit for personal audit but well factored
  - Network: `HttpClient` in `BlockListManager` only → fetches user-configured blocklists (HTTP GET with conditional / If-Modified-Since). No phone-home.
  - Dependencies: direct references to the official DLLs, no third-party runtime NuGet
  - CI: 5 workflows (ci, codeql, docs, perf, release) — serious
  - Adoption: 1 star, 2 open issues
- **Verdict**: solid code with CodeQL and tests, but the project is young (~2 months), no stable release, and no user base. Installable with guardrails = pin a commit, watch issues.

### MispConnectorApp (DeltaZulu) — Tier 2

- Repo: <https://github.com/DeltaZulu-OU/MispConnectorApp>
- Author: DeltaZulu OÜ (Estonian organisation, blog at <https://deltazulu.ee>, created 2025-12 → **5 months old**)
- Purpose: pulls domain-name IoCs from a MISP server (threat intel) and blocks them
- Evaluation:
  - Source: public, 644 LoC in a single `App.cs`, simple layout
  - Licence: GPL-3.0
  - Last release: v2.0.0 (2026-05-12, signed by `github-actions[bot]`)
  - Network: `HttpClient` → only towards the user-configured `mispServerUrl`, with a `disableTlsValidation` option (logs a warning). `TcpClient` present → worth inspecting in detail if you want to push it to Tier 1.
  - Dependencies: pinned submodules pointing at the official DnsServer and TechnitiumLibrary
  - CI: `release.yml` produces the ZIP via Actions
  - Adoption: 0 stars, 0 forks. Author also maintains a sister `LogExporterApp` repo.
- **Verdict**: clean code, reproducible build, but the organisation is < 6 months old and has zero adoption. Tier 2 = installable if you already run a MISP instance; otherwise wait for traction. Auditing `App.cs` (644 LoC) is doable in ~30 minutes.

### technilux-apps (elabx-org) — Tier 2 for all 3

- Repo: <https://github.com/elabx-org/technilux-apps>
- Author: org `elabx-org` (anonymous, no display name, 0 followers, created 2021-02), releases by user `elmerfds`
- Purpose: 3 apps — `AdvancedBlockingPlus` (enriched fork of the official AdvancedBlocking), `AdvancedForwardingPlus` (enriched fork), `NetworkHelper` (internal REST controllers for managing a device store)
- Evaluation:
  - Source: public, 3791 LoC total
  - Licence: **none** (no LICENSE file) — legal risk on redistribution
  - Last push: 2026-01-29, several releases
  - Network: `AdvancedBlockingPlus` uses `HttpClient` to fetch user-configured blocklists (same as the official app). `AdvancedForwardingPlus` has zero direct `HttpClient`. `NetworkHelper` has zero network (file I/O only).
  - Dependencies: direct references to the official DLLs, no third-party NuGet
  - CI: `release.yml`, releases signed by both bot AND `elmerfds` user (mixed signal but explainable: manual bootstrap then CI)
  - Notes: presence of a `CLAUDE.md` (Claude-assisted development) and an `appstore.json` suggesting a competing app store
- **Verdict**: code derived from the official apps, limited network surface identical to upstream. Weak author identity and **no licence** = conditional Tier 2. Fork / pin a commit for production use. Re-vendor manually with an explicit licence if you redistribute.

### ConditionalDualForwardResolver — Tier 3

- Repo: <https://github.com/idavidmarshali/ConditionalDualForwardResolver>
- Author: Korosh Mousaei, on GitHub since 2017, 17 repos, 3 followers — plausible identity but low profile
- Purpose: a forwarder that detects "poisoned" answers (specific IPs) and falls back to a DoH resolver
- Evaluation:
  - Source: public, 249 LoC, monolithic
  - Licence: **none**
  - Last push: 2026-01-27 (single commit, never touched since)
  - LoC: 249 → trivially auditable
  - Network: DNS only (DnsClient via TechnitiumLibrary). No direct HttpClient/Socket.
  - Dependencies: Technitium DLLs only
  - CI: none. No release. No ZIP provided.
- **Verdict**: short, low-risk code, but one-shot commit, no licence, no CI, no release = zero maintenance guarantee. Avoid in production; OK to lift the code for personal use.

### TechnitiumLogDb (nazo6) — Tier 3

- Repo: <https://github.com/nazo6/TechnitiumLogDb>
- Author: nazo6, GitHub since 2019, 109 repos, blog at `nazo6.dev` — reasonable credibility
- Purpose: logs DNS queries to an external HTTP endpoint (DB log)
- Evaluation:
  - Source: public, 260 LoC
  - Licence: **none**
  - Last push: 2023-03-24 → **3 years without maintenance**
  - Network: `HttpClient` sends **DNS query logs** to an externally configured endpoint → intentional metadata exfiltration (privacy-sensitive: you ship all your DNS traffic to an HTTP sink)
  - CI: none, no release
- **Verdict**: the nominal purpose IS to ship query logs elsewhere; the privacy risk is not a bug, it is the feature. Combined with 3 years of abandonment and no licence → Tier 3. The official store now has a `LogExporterApp` that covers this need with maintenance.

### technitium_IpWildcard (bmacao) — Tier 3

- Repo: <https://github.com/bmacao/technitium_IpWildcard>
- Author: Bruno Mação, on GitHub since 2011, 8 repos, WordPress blog — real identity
- Purpose: a self-hosted `nip.io` equivalent — parses an IP encoded in the QNAME and returns an A record. No outbound call.
- Evaluation:
  - Source: public, 437 LoC across 3 versioned folders (0.9, 0.9.5, 0.9.5.1)
  - Licence: GPL-3.0
  - Last push: 2022-07-25 → **4 years without maintenance**
  - Network: zero (just `using System.Net.Sockets` for `IPAddress`)
  - CI: none, no release
- **Verdict**: minimal network risk (zero outbound calls, parse-only) BUT abandoned for 4 years, untested against recent `DnsApplicationCommon` versions. Note: the official Technitium server includes a `WildIpApp` (`Apps/WildIpApp/App.cs`) that covers this use case → **use the official store version instead**.

## Cross-cutting observations

- **All network-active apps** use `HttpClient` only against user-configured endpoints (lancache.net, MISP, blocklist URLs). None has a suspicious hardcoded domain.
- **NetworkHelper from technilux** is the only one that exposes its own REST controllers — check the bind address (localhost vs 0.0.0.0) before installing.
- **Apps without CI or release tag** (`bmacao`, `nazo6`, `idavidmarshali`) → you must build the ZIP yourself. This is actually a zero-trust advantage: you control the binary.
- **Apps with bot-signed CI** (`ruifung`, `coreyleavitt`, `DeltaZulu`, `elabx-org`) → you can re-run the workflow on your own fork to match the hash.
- **No app ships a third-party DLL or suspicious runtime NuGet**. They all only rely on the two official DLLs `DnsServerCore.ApplicationCommon` + `TechnitiumLibrary.Net`.

## Actionable recommendations for the `mipsou.technitium.app` module

1. **No whitelist by default**: exposing a free-form `url` parameter is necessary (the user wants out-of-store installs) — but link this audit from the module documentation so users see the per-app tier.
2. **Hash pinning (future)**: add an optional `sha256` parameter to validate the downloaded ZIP. None of the projects above publishes a checksum today, so users would have to compute it themselves. Plan for v0.3+.
3. **Tier 1 is the only "recommended" tier** in the Ansible documentation: `LANCache-TDNSApp` is the only app that passes every criterion. Mention the others with their tier so users can make an informed choice.
4. **Re-vendor recommended for Tier 2 elabx-org**: no explicit licence → fork, add a compatible LICENSE, build the ZIP, host it on your own release artifact.

## Sources

- [GitHub topic `technitium-dns-app`](https://github.com/topics/technitium-dns-app)
- [Technitium official DnsServer repo](https://github.com/TechnitiumSoftware/DnsServer)
- [Technitium DNS Apps dev blog post](https://blog.technitium.com/2021/03/creating-and-running-dns-apps-on.html)
- [Technitium APIDOCS](https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md)
