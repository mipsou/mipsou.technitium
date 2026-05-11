# `community.technitium` proposal — paste-ready

Forum post template for [forum.ansible.com](https://forum.ansible.com/new-topic?category=project&tags=coll-repo-request).
Tag: `coll-repo-request`.

---

## Title

`New collection: community.technitium — Ansible modules for the Technitium DNS Server HTTP API`

## Body

**Namespace:** `community.technitium`
**Maintainer:** [@mipsou](https://github.com/mipsou)
**Current home:** [github.com/mipsou/mipsou.technitium](https://github.com/mipsou/mipsou.technitium) · [galaxy](https://galaxy.ansible.com/ui/repo/published/mipsou/technitium/)

**Scope:** Declarative management of [Technitium DNS Server](https://technitium.com/dns/) via its HTTP API. Eight modules (`session`, `setting`, `blocklist`, `zone`, `record`, `user`, `allowed_zone`, `blocked_zone`), one lookup, one shared `TechnitiumClient`. Documents [10 Technitium API quirks](https://github.com/mipsou/mipsou.technitium/blob/main/docs/api_quirks.md) the collection abstracts away. No prior community collection covers Technitium.

**Status:** Sole maintainer, ~2000 LoC. `ansible-test sanity` green on stable-2.15/16/17 + integration smoke against a real `technitium/dns-server` container. Release pipeline automated (tag → GHA → Galaxy).

**Licence:** EUPL-1.2 today. Sole copyright holder, no CLA needed — happy to relicense to GPL-3.0-or-later at acceptance.

**Migration plan:**

1. Relicense to GPL-3.0-or-later (one commit).
2. Transfer repo to `ansible-collections/community.technitium`.
3. Rename namespace `mipsou` → `community` everywhere (`galaxy.yml`, imports, FQCNs, CI paths).
4. Cut first community release; deprecate `mipsou.technitium` with a pointer.

**[Collection requirements](https://docs.ansible.com/ansible/devel/community/collection_contributors/collection_requirements.html):**

✅ `requires_ansible: '>=2.15.0'` · sanity matrix · changelogs · DOC/EXAMPLES/RETURN · FQCN · version_added · idempotency · zero runtime deps · public issues · CoC · communication section · semver + tag = Galaxy version · justified sanity ignores
⏳ Galaxy ≥ 1.0.0 (currently 0.1.0; cut after 1+ external user — [`pra-dns-stack`](https://github.com/mipsou-infra/pra-dns-stack) inbound)
⏳ Sanity on `devel`/`milestone` (Python 3.12 runner sorted, re-enable before 1.0.0)
⏳ `ansible-collections` org branch protections (applied at transfer)

Thanks!

---

## How to post

1. Log in at <https://forum.ansible.com> (GitHub SSO works).
2. Open <https://forum.ansible.com/new-topic?category=project&tags=coll-repo-request>.
3. Paste the title and the body above.
4. Tag with `coll-repo-request` (mandatory).
5. Submit. Wait a few weeks for SC review.
