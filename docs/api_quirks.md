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

---

## 8. `/api/user/login` returns a bogus token under POST + form Content-Type

`POST /api/user/login` with `Content-Type: application/x-www-form-urlencoded`
and `user=admin&pass=admin&includeInfo=true` in the body returns HTTP 200 and
a JSON payload that contains a 35-character `token`. Every subsequent call
using that token is rejected with `{"status": "invalid-token", "errorMessage":
"Invalid token or session expired."}`. A `GET /api/user/login?user=admin&...`
with the *same* parameters in the query string returns the expected 64-char
hex token that actually works.

The trigger appears to be the `Content-Type: application/x-www-form-urlencoded`
header — even a GET request with that header set yields the broken token.
Diagnosed in CI by comparing baseline `ansible.builtin.uri` (which only sets
Content-Type when there is a body) against `ansible.module_utils.urls.fetch_url`
with a static `Content-Type` header.

**Module behaviour**: `module_utils/technitium.py` uses GET for
`/api/user/login`, `/api/user/logout`, and `/api/user/changePassword`, and
only sets `Content-Type` when an actual body is being sent (POST).

---

## 9. `fetch_url` silently invalidates Technitium sessions; use `open_url`

Even with the Content-Type fix above, `ansible.module_utils.urls.fetch_url`
produced login tokens that worked once and then got rejected as
`invalid-token` on the very next call against the same session. The same
URL handed to `ansible.builtin.uri` (which is built on `open_url`) worked
across repeated calls without issue.

Likely cause: `fetch_url` injects extra headers (notably ones related to
the calling `AnsibleModule`) that Technitium's session machinery interprets
as a session change.

**Module behaviour**: `module_utils/technitium.py` calls `open_url` directly
and does not use `fetch_url`. Any future addition that touches the HTTP layer
should keep that pattern.

---

## 10. `changePassword` invalidates the bootstrap session in unpredictable ways

After a fresh-container bootstrap, the sequence
`login(admin/admin) → changePassword(admin → declared) → login(admin/declared)`
yields a token that Technitium rejects as `invalid-token` on the very next
API call. Neither reusing the bootstrap token nor adding a delay before the
re-login fixes it reliably. This makes the rotation flow fragile for
automated tests; we keep the bootstrap code in `session` (it is the actual
production code path) but do not exercise rotation in CI smoke.

**Workaround**: when rotating in production, pause between the rotation and
the first downstream API call (a few seconds), or pre-create a permanent API
token via `/api/admin/sessions/createToken` and authenticate downstream tasks
with it instead of the session token.
