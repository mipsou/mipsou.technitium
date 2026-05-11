# Session tokens get invalidated after one use depending on the request's HTTP headers

**Target repo**: `TechnitiumSoftware/DnsServer`
**Issue type**: bug (or documentation gap)

---

## Summary

A valid session token obtained from `/api/user/login` is revoked by Technitium after a single API call when the call carries certain auxiliary HTTP headers — even when the token, URL, and request method are otherwise correct. The same token, used through a more minimal HTTP client, survives across many calls without issue.

Empirically, the trigger appears to be one or more of the headers added by `ansible.module_utils.urls.fetch_url` (the Python HTTP helper used inside Ansible modules) that are *not* added by `ansible.builtin.uri` (which uses the lower-level `open_url`). Both call the same Python `urllib` machinery underneath, so the difference is purely in the request shape.

## How to reproduce

(Reproduce inside an Ansible collection or with a Python script that mimics fetch_url's header set.)

1. Login normally via GET, with no Content-Type:
   ```
   GET /api/user/login?user=admin&pass=admin&includeInfo=true
   ```
   This returns a working 64-char token (see also issue [#01] about the `Content-Type` quirk).
2. Call `/api/zones/list?token=<token>` once via Ansible's `ansible.builtin.uri` module → `status: ok`, the list comes back.
3. Call `/api/zones/list?token=<token>` again via `fetch_url(module, ..., method='GET')`:
   - The call returns HTTP 200.
   - **Any subsequent call** (using the *same* token, the same URL, even via the *working* client) returns `{"status": "invalid-token", "errorMessage": "Invalid token or session expired."}`.

We could not narrow down which specific header(s) triggers the revocation — possibly the combination of `User-Agent: ansible-httpget/...`, the `Connection` header behaviour of fetch_url, or a charset on `Accept`. A diff of the request headers between `urllib.request.Request` (works) and `fetch_url` (revokes) would be the place to look.

## Expected behaviour

A session token should remain valid until explicit logout, the configured idle/absolute timeout, or admin revocation — regardless of which HTTP headers the client uses, as long as the call is otherwise well-formed.

## Workaround we use

[`mipsou/mipsou.technitium`](https://github.com/mipsou/mipsou.technitium) avoids `fetch_url` entirely and goes through `ansible.module_utils.urls.open_url` (the same path `ansible.builtin.uri` takes). After that switch, the same token survives across all subsequent calls. Documented as quirk #9 in `docs/api_quirks.md`.

## Notes

Observed on Technitium DNS Server image `technitium/dns-server:latest` (currently 15.x). Detection in CI was non-trivial — the token *appears* valid because the first call after issuing it succeeds; only later calls expose the revocation. A logged warning at revocation time would have saved hours.
