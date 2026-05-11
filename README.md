# Ansible Collection — `mipsou.technitium`

[![ansible-test](https://github.com/mipsou/mipsou.technitium/actions/workflows/ansible-test.yml/badge.svg)](https://github.com/mipsou/mipsou.technitium/actions/workflows/ansible-test.yml)
[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/page/eupl-text-11-12)
[![Galaxy](https://img.shields.io/badge/galaxy-mipsou.technitium-660198.svg)](https://galaxy.ansible.com/ui/repo/published/mipsou/technitium/)

Declarative, idempotent management of a [Technitium DNS Server](https://technitium.com/dns/)
via its HTTP API. Built for PRA / disaster-recovery workflows and homelab
infra-as-code.

> First Ansible collection for the Technitium API. Replaces raw `uri` calls
> (with all their HTTP-200-but-failed quirks) with proper state-based modules
> supporting `check_mode` and `diff`.

## Scope (v0.1.0)

| Module | Purpose |
| --- | --- |
| [`mipsou.technitium.session`](plugins/modules/session.py) | Auth + token; bootstraps fresh `admin/admin` containers and rotates the password |
| [`mipsou.technitium.setting`](plugins/modules/setting.py) | Read/diff/write server settings via `/api/settings/{get,set}` |
| [`mipsou.technitium.blocklist`](plugins/modules/blocklist.py) | Manage `blockListUrls` state-based, with a stdlib UDP DNS probe to detect activation |
| [`mipsou.technitium.zone`](plugins/modules/zone.py) | Create / delete Primary / Secondary / Stub / Forwarder / Catalog zones |
| [`mipsou.technitium.record`](plugins/modules/record.py) | A / AAAA / NS / CNAME / PTR / MX / TXT / SRV records, keyed on `(name, type, value)` |
| [`mipsou.technitium.user`](plugins/modules/user.py) | Manage user accounts; idempotent password rotation via probe-login |
| [`mipsou.technitium.allowed_zone`](plugins/modules/allowed_zone.py) | Entries in `/api/allowed/*` (domain allow-list) |
| [`mipsou.technitium.blocked_zone`](plugins/modules/blocked_zone.py) | Entries in `/api/blocked/*` (manual block-list) |

Plus one lookup plugin (`mipsou.technitium.record`) for Jinja2 DNS queries
through the API.

A shared `module_utils.technitium.TechnitiumClient` handles auth, the eight
Technitium API quirks documented in [`docs/api_quirks.md`](docs/api_quirks.md),
and the `open_url`-based HTTP path that avoids `fetch_url`'s session-side
effects.

## Requirements

- Ansible `>= 2.15`
- Python `>= 3.9` on the controller
- A Technitium DNS Server reachable over HTTP(S) — works against
  `technitium/dns-server:latest` containers, bare-metal installs and the
  Windows Service install identically.

## Install

```bash
ansible-galaxy collection install mipsou.technitium
```

## Quick start

```yaml
- hosts: localhost
  gather_facts: false
  tasks:
    - name: Open a session (bootstraps admin/admin on a fresh container)
      mipsou.technitium.session:
        host: 192.168.1.10
        user: admin
        password: "{{ vault_technitium_admin_password }}"
        bootstrap_password: admin
      register: tech

    - name: Create a primary zone
      mipsou.technitium.zone:
        session: "{{ tech.session }}"
        name: example.lan
        type: Primary
        state: present

    - name: A record for ns1
      mipsou.technitium.record:
        session: "{{ tech.session }}"
        zone: example.lan
        name: ns1.example.lan
        type: A
        ip_address: 192.168.1.10
        ttl: 3600
```

See [`tests/integration/targets/smoke/tasks/main.yml`](tests/integration/targets/smoke/tasks/main.yml)
for a fuller end-to-end walkthrough.

## Communication

- **Need help?** Ask in the [Get Help](https://forum.ansible.com/c/help/6/none)
  category on the Ansible Forum, mentioning `mipsou.technitium` in the post.
- **Project discussion** happens under the
  [`mipsou-technitium`](https://forum.ansible.com/tag/mipsou-technitium) tag
  on the Forum (create the tag on first use).
- **Bug reports & feature requests**:
  [GitHub Issues](https://github.com/mipsou/mipsou.technitium/issues).
- **Code of Conduct**: see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — we
  follow the
  [Ansible Community Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).

## License

EUPL-1.2. See [`LICENSE`](LICENSE). Relicensing to GPL-3.0-or-later is
planned at the moment the collection is adopted into the `community.*`
namespace (see [`PROPOSAL.md`](PROPOSAL.md)).
