# Ansible Collection — `mipsou.technitium`

Ansible modules and plugins to manage [Technitium DNS Server](https://technitium.com/dns/)
through its HTTP API: sessions, settings, zones, records, blocklists, users.

> **Status**: pre-release (v0.1.0), built around concrete bugs / quirks found
> while driving Technitium from raw `uri` calls in production. See
> [`docs/api_quirks.md`](docs/api_quirks.md) for the surprising behaviours this
> collection abstracts away.

## Why this collection

Technitium has no official Ansible collection. Talking to its API with the
generic `uri` module works, but several quirks make it painful and unsafe:

- `blockingBypassList` accepts only CIDR network addresses, not domains — and
  rejects domains with HTTP 200 + an error payload (silent failure with `uri`).
- `blockListUrls` only accepts repeated form fields (`urls=a&urls=b`), not
  comma- or newline-separated lists.
- `changePassword` requires both `pass` and `newPass`.
- `blockListLastUpdatedOn` is not reliably updated after a force-refresh.
- Fresh containers start with `admin/admin` and must be rotated on first boot;
  the official image does not honour `DNS_SERVER_ADMIN_PASSWORD`.

Every quirk above maps to a dedicated module that handles it idempotently.

## Modules (v0.1.0 scope)

| Module | Status | Purpose |
| --- | --- | --- |
| `session` | P0 | Auth + token. Bootstraps `admin/admin` and rotates automatically. |
| `setting` | P0 | Get/set server settings with diff. |
| `blocklist` | P0 | Manage `blockListUrls` (state-based), wait for active. |
| `zone` | P0 | Create/delete primary, secondary, forwarder, stub zones. |
| `record` | P0 | A / AAAA / NS / CNAME / PTR / MX / TXT / SRV. Match key is `(name, type, value)`; TTL / comments updates are not in v0.1 — delete + recreate to change them. |
| `user` | P1 | Manage users, idempotent password rotation (verified by probe-login). |
| `allowed_zone` | P1 | Manage entries in the Allowed Zones list (`/api/allowed/*`). |
| `blocked_zone` | P1 | Manage entries in the Blocked Zones list (`/api/blocked/*`). |

## Lookup plugins

| Lookup | Purpose |
| --- | --- |
| `record` | `lookup('mipsou.technitium.record', 'host.example', type='A', session=tech.session)` |

## Quick start

```yaml
- hosts: dns
  tasks:
    - mipsou.technitium.session:
        host: 192.168.1.10
        port: 5380
        user: admin
        password: "{{ vault_technitium_admin_password }}"
        bootstrap_password: admin
        rotate_if_bootstrap: true
      register: tech

    - mipsou.technitium.zone:
        session: "{{ tech.session }}"
        name: example.lan
        type: primary
        state: present

    - mipsou.technitium.record:
        session: "{{ tech.session }}"
        zone: example.lan
        name: ns1.example.lan
        type: A
        value: 192.168.1.10
        ttl: 3600
        state: present
```

## Communication

- **Need help?** Ask in the [Get Help](https://forum.ansible.com/c/help/6/none) category on the Ansible Forum, mentioning `mipsou.technitium` in the post so maintainers see it.
- **Project discussion** happens under the [`mipsou-technitium`](https://forum.ansible.com/tag/mipsou-technitium) tag on the Forum (use that tag when you start a topic in *Project Discussions*). The tag will be created on first use.
- **Bug reports & feature requests:** [GitHub Issues](https://github.com/mipsou/mipsou.technitium/issues) on this repository.
- **Code of Conduct:** see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — we follow the [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).

## License

Licensed under the [EUPL-1.2](LICENSE) — European Union Public Licence v1.2. A re-licensing to **GPL-3.0-or-later** is on the roadmap if/when the collection is proposed for adoption into the `community.*` namespace (see [`PROPOSAL.md`](PROPOSAL.md)).

## Links

- Technitium DNS API documentation: <https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md>
- Container image: `docker.io/technitium/dns-server:latest`
