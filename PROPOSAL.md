# Proposal: promote `mipsou.technitium` to `community.technitium`

> Draft for the future submission to **forum.ansible.com** with tag
> [`coll-repo-request`](https://forum.ansible.com/tag/coll-repo-request).
> Older docs may still reference an `ansible-collections/overview` PR
> process — that has been superseded by the forum-based flow.

## Status

**Pre-submission.** Currently published as `mipsou.technitium` on Ansible
Galaxy. We will request a `community.technitium` repo on the forum once the
collection has:

- a track record of releases (≥ 0.2.0 with bugfixes from real-world usage)
- a documented user beyond the initial author (PRA stack at minimum, ideally
  one external consumer)
- complete sanity & integration test coverage in CI (already in place for
  v0.1.0 — `ansible-test sanity` 2.15/2.16/2.17 + integration smoke against
  a real Technitium container)
- a co-maintainer or explicit commitment from another contributor

## Forum post template (to paste when ready)

```
Title: Request for a new collection: community.technitium

Hi,

I'd like a new collection repo in the community namespace please.

Name: community.technitium
Source: https://github.com/mipsou/mipsou.technitium (currently published as
mipsou.technitium on Galaxy)
Maintainer: @mipsou

Scope: Ansible modules and plugins to manage a Technitium DNS Server through
its HTTP API. Eight modules (session, setting, blocklist, zone, record, user,
allowed_zone, blocked_zone) plus a lookup plugin. Zero external Python
dependencies. CI: sanity matrix + integration smoke against a real
technitium/dns-server container. Documents 10 Technitium API quirks the
collection abstracts away.

No prior community.* collection targets Technitium DNS Server.

Thanks!
```

Tag the post with `coll-repo-request`.

## Why community.technitium

- **No prior art**: search of galaxy.ansible.com confirms no published
  collection targets Technitium. The namespace is unclaimed.
- **API-driven, no host coupling**: the collection talks only to the HTTP
  API. It works against containers, bare-metal installs and the Windows
  Service install identically.
- **Idempotency story is solid**: every module follows the GET-diff-POST
  pattern, validated by the integration smoke test under
  `tests/integration/targets/smoke/`. Re-runs report `changed=false`.
- **Captures expert knowledge**: 10 quirks documented in
  `docs/api_quirks.md`, three of them discovered while bootstrapping the
  collection's CI (login Content-Type, fetch_url session invalidation,
  changePassword race).

## Governance after promotion

If accepted, the repo moves to `github.com/ansible-collections/community.technitium`.
Initial maintainer commits to:

- triage incoming issues within 14 days
- accept at least one co-maintainer before reaching 1.0.0
- adopt the standard `ansible-collections` CI (sanity + units + integration
  matrix against the latest two `ansible-core` releases)
- follow [Ansible's collection requirements](https://docs.ansible.com/ansible/latest/community/collection_contributors/collection_requirements.html)

## Open questions for the reviewers

- Naming: `community.technitium` vs `community.technitium_dns`. The shorter
  form is consistent with `community.docker`, `community.postgresql`. Going
  with the shorter unless precedent suggests otherwise.
- License: currently EUPL-1.2. `community.*` collections are typically
  GPL-3.0-or-later. Re-licensing is on the table if it is a hard requirement.
