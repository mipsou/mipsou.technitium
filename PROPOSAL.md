# Proposal: promote `mipsou.technitium` to `community.technitium`

> Draft for the future submission to **forum.ansible.com** with tag
> [`coll-repo-request`](https://forum.ansible.com/tag/coll-repo-request),
> following the requirements documented in
> <https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html>
> (the `ansible-collections/overview` PR flow is deprecated).

## Status

**Pre-submission.** Currently published as `mipsou.technitium` on Ansible
Galaxy. The community-collection inclusion checklist has 7 MUST gaps to
close before we open the forum topic — see the audit below.

## Audit against the inclusion checklist

Legend: ✅ done · ❌ to do · ⏳ partial · 🚫 strategic decision pending

### Critical (showstoppers)

| MUST | Status | Notes |
| --- | --- | --- |
| Galaxy publication ≥ 1.0.0 | ❌ | Currently 0.1.0. Cut 1.0.0 once the other gaps are closed and the collection has accrued real-world feedback. |
| `modules/`, `module_utils/`, `plugins/` GPL-3.0-or-later compatible | ✅ | Dual-licence applied: `plugins/modules/` + `plugins/module_utils/` stay EUPL-1.2 (GPL-3.0-compatible via Article 5), `plugins/lookup/` + `plugins/doc_fragments/` are GPL-3.0-or-later (strict). SPDX headers everywhere. See [`LICENSE.md`](LICENSE.md). |
| `module_utils` file names leading underscore (internal-only marker) | ❌ | Rename `plugins/module_utils/technitium.py` → `plugins/module_utils/_technitium.py` + update every import. Breaking change for any external consumer that imports the helper directly. |
| Forum public tag corresponding to the collection | ❌ | Create `community-technitium` tag the day of the forum topic. |
| README communication section referencing the Forum | ✅ | Added in v0.1.0. |
| `ansible-collections` repo branch protections (linear history, no merge commits, no bypass) | ❌ | Only relevant once the repo is transferred to the org. |

### Quality bar (also MUST)

| MUST | Status | Notes |
| --- | --- | --- |
| `ansible-test sanity` matrix against supported ansible-core versions | ✅ | stable-2.15 / 2.16 / 2.17 green. |
| `ansible-test sanity` against `devel` + `milestone` | ❌ | Re-enable once Python 3.12 is available on GitHub Actions matrix. |
| Sanity ignore entries justified by comments | ✅ | Justifications added in `tests/sanity/ignore-*.txt` headers. |
| Semantic versioning + tag matches Galaxy version | ✅ | `0.1.0` tag = `galaxy.yml` version. |
| Changelog (antsibull-changelog) | ✅ | `changelogs/config.yaml` + fragment. |
| Public issue tracker, no paid tier | ✅ | GitHub Issues. |
| Code of Conduct linked from README | ✅ | `CODE_OF_CONDUCT.md` points to Ansible CoC. |
| `meta/runtime.yml` `requires_ansible` | ✅ | `>=2.15.0`. |
| DOCUMENTATION / EXAMPLES / RETURN blocks | ✅ | All modules + lookup. |
| FQCN in cross-references | ✅ | `mipsou.technitium.*` (will become `community.technitium.*` after the rename). |
| `version_added` refers to collection version | ✅ | `"0.1.0"` everywhere. |
| Idempotency for every module | ✅ | Smoke test exercises `changed=false` on re-runs. |
| No CLA other than DCO | ✅ | No CLA. |

### Strategic decisions to settle

1. **Re-licence to GPL-3.0-or-later?** Already resolved with a **dual-licence
   split**: EUPL-1.2 for the bulk of the code (the spec allows GPL-3.0-compatible
   licences there, and EUPL-1.2 is compatible via Article 5), GPL-3.0-or-later
   for `plugins/lookup/` and `plugins/doc_fragments/` where the spec is strict.
   See [`LICENSE.md`](LICENSE.md).
2. **Rename `module_utils/technitium.py` to `_technitium.py`?** Required by the checklist to mark module_utils as internal. Cost is one breaking import-path change; trivial to do before any external consumer adopts the helper.
3. **Cut 1.0.0 when?** Plan: after at least one external user (other than `mipsou-infra/pra-dns-stack`) has been on a tagged version for a sprint.

## Forum post template (to paste when ready)

```
Title: Request for a new collection: community.technitium

Hi,

I'd like a new collection repo in the community namespace please.

Name: community.technitium
Source: https://github.com/mipsou/mipsou.technitium (currently published as
mipsou.technitium on Galaxy, version 1.0.0+)
Maintainer: @mipsou
Forum tag: community-technitium (to be created)

Scope: Ansible modules and plugins to manage a Technitium DNS Server through
its HTTP API. Eight modules (session, setting, blocklist, zone, record, user,
allowed_zone, blocked_zone) plus a lookup plugin. Zero external Python
dependencies. CI: sanity matrix + integration smoke against a real
technitium/dns-server container. Documents 10 Technitium API quirks the
collection abstracts away.

License: GPL-3.0-or-later (re-licensed from EUPL-1.2 at v1.0).
No prior community.* collection targets Technitium DNS Server.

Audit against the inclusion checklist:
https://github.com/mipsou/mipsou.technitium/blob/main/PROPOSAL.md

Thanks!
```

Tag the post with `coll-repo-request`.
