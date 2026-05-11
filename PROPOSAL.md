# Proposal: promote `mipsou.technitium` to `community.technitium`

> This file is a draft for the future submission to
> [`ansible-collections/overview`](https://github.com/ansible-collections/overview).
> It is **not** part of the published collection — it lives in the repo so
> the rationale stays close to the code. Move it to a GitHub issue under
> ansible-collections/overview when ready to submit.

## Status

**Pre-submission.** The collection is currently published as `mipsou.technitium`
on Ansible Galaxy. Promotion to the official `community.technitium` namespace
will be proposed once the collection has:

- a track record of releases (≥ 0.2.0 with bugfixes from real-world usage)
- a documented user beyond the initial author (PRA stack at minimum, ideally
  one external consumer)
- complete sanity & integration test coverage in CI
- a co-maintainer or explicit commitment from another contributor

## Summary

`mipsou.technitium` is an Ansible collection of modules and lookup plugins to
manage a [Technitium DNS Server](https://technitium.com/dns/) through its
HTTP API. It exists because every team running Technitium under Ansible
re-derives the same workarounds for the API's quirks (HTTP-200 errors, list
parameter serialisation, fresh-container bootstrap, unreliable readiness
signals — see `docs/api_quirks.md`).

There is no existing `community.*` collection for Technitium.

## Why community.technitium

- **No prior art**: search of galaxy.ansible.com confirms no published
  collection targets Technitium. The namespace is unclaimed.
- **API-driven, no host coupling**: the collection talks only to the HTTP
  API. It works against containers, bare-metal installs and the Windows
  Service install identically. No platform-specific code.
- **Idempotency story is solid**: every module follows the GET-diff-POST
  pattern, validated by the integration smoke test under
  `tests/integration/targets/smoke/`. Re-runs report `changed=false`.
- **Captures expert knowledge**: the seven quirks documented in
  `docs/api_quirks.md` represent real production incidents that a generic
  `uri`-based approach silently mishandles. The collection encodes them
  once.

## Module inventory (v0.1.0)

| Module / plugin | Scope |
| --- | --- |
| `session` (module) | Authenticate; handle fresh-container `admin/admin` bootstrap + rotation. |
| `setting` (module) | Read/diff/write `/api/settings/{get,set}`. Validates `blockingBypassList` is IP/CIDR. |
| `blocklist` (module) | `blockListUrls` state-based; force-update; DNS probe to detect activation. |
| `zone` (module) | Create/delete Primary/Secondary/Stub/Forwarder/(Secondary)Catalog zones. |
| `record` (module) | A/AAAA/NS/CNAME/PTR/MX/TXT/SRV add/delete, keyed on `(name, type, value)`. |
| `user` (module) | Create/update/delete admin users; idempotent password rotation via probe-login. |
| `allowed_zone` (module) | Add/remove from `/api/allowed/*`. |
| `blocked_zone` (module) | Add/remove from `/api/blocked/*`. |
| `record` (lookup) | Resolve DNS records via API from Jinja2. |

## Governance after promotion

If promoted, the collection moves to `github.com/ansible-collections/community.technitium`.
Initial maintainer commits to:

- triage incoming issues within 14 days
- accept at least one co-maintainer before reaching 1.0.0
- adopt the standard `ansible-collections` CI (sanity + units + integration
  matrix against the latest two `ansible-core` releases)
- follow [Ansible's collection requirements](https://docs.ansible.com/ansible/latest/community/collection_contributors/collection_requirements.html)

## Open questions for the reviewers

- Naming: `community.technitium` vs `community.technitium_dns`. The shorter
  form is consistent with `community.docker`, `community.postgresql`. Going
  with the shorter unless there is a precedent suggesting otherwise.
- License: the collection is currently EUPL-1.2. `community.*` collections
  are typically GPL-3.0-or-later. Re-licensing is on the table if it is a
  hard requirement.
