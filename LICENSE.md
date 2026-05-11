# Licensing

This collection is **dual-licensed**, with the split chosen to satisfy the
[Ansible community collection inclusion requirements][reqs] while keeping the
canonical project licence (EUPL-1.2) wherever the spec allows.

| Path | Licence | Reason |
| --- | --- | --- |
| `plugins/modules/` and `plugins/module_utils/` | **EUPL-1.2** | Ansible's spec requires *GPL-3.0-or-later-compatible* for these. EUPL-1.2 is GPL-3.0-compatible via its [compatibility clause (Article 5 + Annex)][eupl-compat]. |
| `plugins/lookup/`, `plugins/doc_fragments/` (and any other `plugins/<type>/`) | **GPL-3.0-or-later** | Ansible's spec requires the *strict* GPL-3.0-or-later licence here, not just a compatible one. |
| Everything else in the repository (docs, tests, CI, build helpers, etc.) | **EUPL-1.2** | Default project licence. |

Every source file carries an [SPDX-License-Identifier][spdx] header
(`EUPL-1.2` or `GPL-3.0-or-later`) so machine-readable licence audit tools
work without surprises.

Canonical licence texts:

- [`LICENSE`](LICENSE) — full EUPL-1.2 text (European Union Public Licence v1.2).
- [`LICENSE.GPL-3.0-or-later`](LICENSE.GPL-3.0-or-later) — full GPL-3.0 text.

## Contributing under this scheme

By submitting a contribution to this collection you agree to license your
contribution under the licence that applies to the file(s) you modify, as
shown in the table above. We use **DCO** (developer certificate of origin)
for contributor agreements; sign your commits with `git commit -s`.

## Why dual-licence at all

EUPL-1.2 fits the project's broader European-friendly stance and lets us
ship under one of the rare strong-copyleft licences with explicit GPL-3.0
compatibility. The minimum split above is the smallest deviation that keeps
us on the Ansible community-collection inclusion track without abandoning
the EUPL preference for the bulk of the code.

[reqs]: https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html
[eupl-compat]: https://commission.europa.eu/content/eupl-guidelines-users-and-developers_en
[spdx]: https://spdx.dev/ids/
