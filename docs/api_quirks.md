# Technitium API quirks

Surprising behaviours of the Technitium DNS Server HTTP API that this collection
abstracts away. Each quirk maps to a workaround inside a specific module so
playbooks no longer need to deal with it.

Reference: <https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md>

---

## 1. Errors come back with HTTP 200 — always check `status`

Most error conditions are returned as `HTTP 200 OK` with a JSON body of the form:

```json
{ "status": "error", "errorMessage": "..." }
```

The generic `uri` module treats this as success, so misuse is silent. **Every
call inside `module_utils/technitium.py` checks `json.status == 'ok'` and fails
explicitly otherwise**, including the `errorMessage`.

---

## 2. `blockingBypassList` takes network addresses, not domains

`POST /api/settings/set` with `blockingBypassList=netflix.com` returns:

```json
{ "status": "error", "errorMessage": "Invalid network address was specified: netflix.com" }
```

The field accepts IP / CIDR network addresses only — it bypasses blocking *for
those source networks*. Domain-level allow-listing goes through a separate
allow-list file (`/etc/dns/config/allow-list.txt`) or the `/api/allowed/*`
endpoints.

**Module behaviour**: `setting` validates that `blockingBypassList` entries
parse as IP/CIDR; domains should go through `allowed_zone` (planned for v0.2).

---

## 3. `changePassword` requires both `pass` and `newPass`

`POST /api/user/changePassword?token=…&newPass=Y` fails with
`Parameter 'pass' missing`. Both the current password and the new one are
mandatory query parameters.

**Module behaviour**: `user` and the bootstrap path of `session` always send
both; rotation is idempotent (login with the new password succeeds → no-op).

---

## 4. List parameters must be repeated form fields

`blockListUrls` and similar list-typed fields are only accepted as repeated
form fields:

```
blockListUrls=https://a.example/list.txt&blockListUrls=https://b.example/list.txt
```

Comma-separated and newline-separated forms are silently rejected or partially
parsed. Ansible's `uri` module with `body_format: form-urlencoded` serialises
Python lists in a way that does not match, and `body_format: json` causes
Technitium to ignore the token in the body.

**Module behaviour**: `module_utils/technitium.py` exposes
`api_form_repeat(path, scalar_params, list_params)` which builds the body as
`k1=v1&k2=v2&list_key=item1&list_key=item2` with proper URL encoding.

---

## 5. `blockListLastUpdatedOn` is not a reliable readiness signal

After `POST /api/settings/forceUpdateBlocklists`, `blockListLastUpdatedOn`
sometimes stays `null` even when the blocklists are loaded and actively
blocking. Polling that field is unreliable.

**Module behaviour**: `blocklist` with `wait_for_active:` performs an actual
DNS probe (default: resolve a well-known blocked domain, expect `NXDOMAIN`)
instead of trusting the timestamp.

---

## 6. Fresh container = `admin/admin` — no `DNS_SERVER_ADMIN_PASSWORD`

The official `technitium/dns-server` image does not honour any environment
variable for the initial admin password. Every fresh deployment starts with
`admin/admin` and must be rotated.

**Module behaviour**: `session` accepts `bootstrap_password: admin` and, when
the primary credentials fail, falls back to that bootstrap password, rotates
to the declared one, and re-authenticates. Re-runs with the rotated password
succeed directly, so the flow is idempotent.

---

## 7. Token is a query parameter, not a header

Authenticated calls take `?token=<token>` in the URL. Putting it in a header
is silently ignored. The token is alphanumeric hex, so URL encoding rarely
matters in practice — but always pass it through `urlencode` to be safe.
