# Contributing to `mipsou.technitium`

Thanks for your interest in this collection. It targets [Technitium DNS Server](https://technitium.com/dns/) and exists because driving the Technitium HTTP API through raw `ansible.builtin.uri` has too many sharp edges (silent HTTP-200 errors, repeated form fields for lists, fresh-container bootstrap).

## Scope

The collection's scope is everything reachable through the Technitium API:
sessions, settings, zones, records, blocklists, users, allow/block lists, DNS
apps, and the related operations on a running Technitium server. Anything
that requires shell access on the host (image build, volume layout, container
runtime) is **out of scope** — that belongs to your role/playbook that
deploys Technitium.

## Development workflow

1. Fork and clone.
2. Install dev dependencies:
   ```bash
   pip install ansible-core>=2.15 antsibull-changelog
   ```
   The collection itself has no runtime Python dependencies — the DNS probe
   used by `blocklist`'s `wait_for_active` is a stdlib socket implementation.
3. Make changes under `plugins/`. Keep idempotency: GET current state, diff
   against declared, only POST the delta. Check the response `status` on
   every call — the `module_utils.technitium.TechnitiumClient` does this for
   you.
4. Add a changelog fragment under `changelogs/fragments/` (any `.yml` file
   with the keys from `changelogs/config.yaml`).
5. Run sanity tests:
   ```bash
   ansible-test sanity --docker default
   ```
6. Run integration tests against a real Technitium container:
   ```bash
   podman run -d --name technitium-test -p 5380:5380 technitium/dns-server:latest
   ansible-playbook tests/integration/targets/smoke/tasks/main.yml \
       -e technitium_password=test -e ansible_connection=local
   ```
7. Open a pull request. Reference any Technitium API quirks documented in
   `docs/api_quirks.md`; add new ones there when you discover them.

## Conventions

- Module argument names use snake_case in YAML and map to Technitium's
  camelCase API parameters internally. Keep that translation in the module
  body, not in the user-facing argument spec.
- Token, password and bootstrap password go through `no_log_values` so
  `-vvv` runs do not leak them.
- Lists in Technitium settings (e.g. `blockListUrls`) are sent as repeated
  form fields, not comma-separated. Use `TechnitiumClient.post(..., lists=...)`.
- Failures from the API come back as HTTP 200 with `{"status": "error"}` —
  `TechnitiumClient` raises `TechnitiumError` on these. Don't bypass it with
  raw `fetch_url`.

## Releases

Release process (maintainer only):

```bash
antsibull-changelog release --version X.Y.Z
git commit -am "Release X.Y.Z"
git tag X.Y.Z && git push --tags
ansible-galaxy collection build
ansible-galaxy collection publish ./mipsou-technitium-X.Y.Z.tar.gz --api-key <token>
```

## License

Contributions are licensed under EUPL-1.2 (the collection's license). By
opening a pull request you confirm that you have the right to license your
contribution under that licence.
