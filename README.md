# Ansible Collection — `mipsou.technitium`

[![ansible-test](https://github.com/mipsou/mipsou.technitium/actions/workflows/ansible-test.yml/badge.svg)](https://github.com/mipsou/mipsou.technitium/actions/workflows/ansible-test.yml)
[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/page/eupl-text-11-12)
[![Galaxy](https://img.shields.io/badge/galaxy-mipsou.technitium-660198.svg)](https://galaxy.ansible.com/ui/repo/published/mipsou/technitium/)

Declarative, idempotent management of a [Technitium DNS Server](https://technitium.com/dns/)
via its HTTP API. Replaces raw `uri` calls (and their HTTP-200-but-failed
quirks) with proper state-based modules supporting `check_mode` and `diff`.

## Scope (v0.1.0)

| Module | Purpose |
| --- | --- |
| [`session`](plugins/modules/session.py) | Auth + token; bootstraps `admin/admin` and rotates |
| [`setting`](plugins/modules/setting.py) | Server settings with diff |
| [`blocklist`](plugins/modules/blocklist.py) | `blockListUrls` state-based, stdlib DNS readiness probe |
| [`zone`](plugins/modules/zone.py) | Primary / Secondary / Stub / Forwarder / Catalog |
| [`record`](plugins/modules/record.py) | A / AAAA / NS / CNAME / PTR / MX / TXT / SRV |
| [`user`](plugins/modules/user.py) | Users; idempotent password rotation |
| [`allowed_zone`](plugins/modules/allowed_zone.py) | `/api/allowed/*` |
| [`blocked_zone`](plugins/modules/blocked_zone.py) | `/api/blocked/*` |

Plus one lookup plugin and a [`TechnitiumClient`](plugins/module_utils/technitium.py)
public helper. Quirks the collection abstracts away: [`docs/api_quirks.md`](docs/api_quirks.md).

## Requirements

- Ansible `>= 2.15`
- Python `>= 3.9` on the controller
- A Technitium DNS Server reachable over HTTP(S)

## Install

```bash
ansible-galaxy collection install mipsou.technitium
```

## Quick start

```yaml
- hosts: localhost
  gather_facts: false
  tasks:
    - mipsou.technitium.session:
        host: 192.168.1.10
        user: admin
        password: "{{ vault_technitium_admin_password }}"
        bootstrap_password: admin
      register: tech

    - mipsou.technitium.zone:
        session: "{{ tech.session }}"
        name: example.lan
        type: Primary

    - mipsou.technitium.record:
        session: "{{ tech.session }}"
        zone: example.lan
        name: ns1.example.lan
        type: A
        ip_address: 192.168.1.10
        ttl: 3600
```

Full walkthrough: [`tests/integration/targets/smoke/tasks/main.yml`](tests/integration/targets/smoke/tasks/main.yml).

## Communication

- Help: [Get Help](https://forum.ansible.com/c/help/6/none) on the Ansible Forum, mention `mipsou.technitium`.
- Discussion: forum tag [`mipsou-technitium`](https://forum.ansible.com/tag/mipsou-technitium).
- Bugs: [GitHub Issues](https://github.com/mipsou/mipsou.technitium/issues).
- [Code of Conduct](CODE_OF_CONDUCT.md).

## License

EUPL-1.2 ([`LICENSE`](LICENSE)). Relicense to GPL-3.0-or-later planned at community adoption (see [`PROPOSAL.md`](PROPOSAL.md)).
