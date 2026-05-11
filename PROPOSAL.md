# Proposal — `community.technitium` collection adoption

Paste-ready draft for a post on
[forum.ansible.com — Project Discussions](https://forum.ansible.com/c/project/7)
requesting adoption of an Ansible collection covering the Technitium DNS
Server HTTP API. Tag the post with `coll-repo-request`.

> **Note (2026-05-11):** The legacy `ansible-collections/overview` GitHub repo
> and `ansible-community/community-topics` are now archived. All collection
> inclusion / namespace proposals moved to forum.ansible.com.

---

## Title

`New collection: community.technitium — Ansible modules for the Technitium DNS Server HTTP API`

## Body

**Namespace / name:** `community.technitium`

**Maintainer:** [@mipsou](https://github.com/mipsou) (sole author at this
stage). Email: `chpujol@gmail.com`.

**Current home:** [github.com/mipsou/mipsou.technitium](https://github.com/mipsou/mipsou.technitium)
— published on Galaxy as
[`mipsou.technitium`](https://galaxy.ansible.com/ui/repo/published/mipsou/technitium/).
The `mipsou.*` track will remain available as a personal mirror or be
deprecated in favor of `community.technitium` if this proposal is accepted.

**Scope:** Declarative, idempotent management of a
[Technitium DNS Server](https://technitium.com/dns/) via its HTTP API.
v0.1.0 ships eight modules and one shared `module_utils.technitium.TechnitiumClient`:

| Module | Purpose |
| --- | --- |
| `session` | Auth + token; bootstraps fresh `admin/admin` containers and rotates the password |
| `setting` | Read/diff/write `/api/settings/{get,set}` |
| `blocklist` | `blockListUrls` state-based, stdlib UDP DNS probe to detect activation |
| `zone` | Create / delete Primary / Secondary / Stub / Forwarder / Catalog zones |
| `record` | A / AAAA / NS / CNAME / PTR / MX / TXT / SRV records, keyed on `(name, type, value)` |
| `user` | Manage user accounts; idempotent password rotation via probe-login |
| `allowed_zone` | Entries in `/api/allowed/*` |
| `blocked_zone` | Entries in `/api/blocked/*` |

Plus one lookup plugin (`record`) and a `session` documentation fragment for
the shared host/port/token/session options.

Roadmap (v0.2+): `app` module (Technitium DNS Apps), update path for
`record` (TTL / comments mutation), inventory plugin sourced from authoritative
zones.

**Motivation:** Talking to Technitium with raw `ansible.builtin.uri` is painful
and unsafe — Technitium returns HTTP 200 with `{"status": "error"}` for most
failures, list parameters need repeated-form-fields serialisation, fresh
containers ship `admin/admin` with no env var override, and a number of
quirks around login `Content-Type`, `fetch_url` session invalidation and
`changePassword` race lurk for any client. Ten of those quirks are
documented in [`docs/api_quirks.md`](docs/api_quirks.md), with the collection
encoding the workaround for each. There is currently no Ansible collection
covering the Technitium API on Galaxy.

**Maintenance commitment:** Single maintainer for now; the codebase is small
(8 modules + 1 lookup + 1 doc_fragment + auth helper, ~2000 LoC), test
coverage is in place (`ansible-test sanity` green on stable-2.15, stable-2.16,
stable-2.17 + integration smoke against a real `technitium/dns-server:latest`
container), release pipeline is automated (tag → GitHub Actions → Galaxy).
Open to co-maintainers from the community.

**Licensing:** Currently EUPL-1.2 — happy to relicense to **GPL-3.0-or-later**
at acceptance time to align with `community.*` policy. As sole copyright
holder, relicensing is straightforward and no CLA collection is required.
EUPL-1.2 also lists GPL-3.0-or-later in its compatible-licences appendix, so
the migration is consistent with downstream / combined-work redistribution.

**Migration plan if accepted:**

1. Relicense `mipsou.technitium` repo to GPL-3.0-or-later (single commit,
   sole author).
2. Transfer the repo to the `ansible-collections` org as
   `ansible-collections/community.technitium`.
3. Update `galaxy.yml` namespace `mipsou` → `community`, all Python import
   paths (`ansible_collections.mipsou.technitium` → `ansible_collections.community.technitium`),
   all FQCN in EXAMPLES / docs / tests / CI workflow paths, and the public
   `TechnitiumClient` import path documented in `module_utils/technitium.py`.
4. Publish first community release; mark `mipsou.technitium` as deprecated
   with a pointer to the new collection.

**Compliance with the [Collection Requirements](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html):**

- ✅ Ansible-core support: `>=2.15.0` declared in `meta/runtime.yml`
- ✅ `ansible-test sanity` green on stable-2.15, stable-2.16, stable-2.17
- ✅ Integration smoke test against a real Technitium container, green in CI
- ✅ `changelogs/` follows the antsibull-changelog format
- ✅ All modules have proper `DOCUMENTATION` / `EXAMPLES` / `RETURN` blocks
  inheriting common args from `plugins/doc_fragments/session.py`
- ✅ FQCN in cross-references (`mipsou.technitium.*`, will become
  `community.technitium.*` after migration)
- ✅ `version_added` refers to collection version, not Ansible version
- ✅ No third-party Python dependencies at runtime (stdlib only — the DNS
  readiness probe uses raw `socket` + `struct`, not `dnspython`)
- ✅ Idempotency exercised by the integration smoke (re-runs report
  `changed=false`)
- ✅ Public issue tracker on GitHub, free tier
- ✅ Code of Conduct in `CODE_OF_CONDUCT.md` pointing to the Ansible CoC
- ✅ Communication section in `README.md` referencing the Forum
- ✅ `tags` field set; semver tagging; tags match Galaxy version
- ✅ Sanity ignores are inline-justified per the spec
- ⏳ Galaxy version ≥ 1.0.0 — currently 0.1.0; cut 1.0.0 once the collection
  has accrued real-world feedback (the consumer
  [`mipsou-infra/pra-dns-stack`](https://github.com/mipsou-infra/pra-dns-stack)
  is the first user; targeting at least one external user before 1.0.0)
- ⏳ `ansible-test sanity` on `devel` / `milestone` — temporarily dropped
  while we sort out the Python 3.12 controller requirement on the runners,
  to be re-enabled before 1.0.0
- ⏳ `ansible-collections` org branch protections (linear history, no merge
  commits) — applied at transfer time

Happy to address any feedback before / during the SC review. Thanks!

---

## How to post this

1. Log in at <https://forum.ansible.com> (single sign-on with your GitHub
   account works).
2. Visit <https://forum.ansible.com/new-topic?category=project>.
3. Title: `New collection: community.technitium — Ansible modules for the Technitium DNS Server HTTP API`.
4. Body: copy the "## Body" section above (everything between `## Body` and
   `## How to post this`).
5. **Tags**: add `coll-repo-request` (mandatory for routing to the right
   reviewers). Consider also `new-collection`.
6. Submit. Watch for Steering Committee triage; expect a few weeks for the
   review.
