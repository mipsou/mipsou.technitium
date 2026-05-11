# `/api/user/login` returns a bogus 35-char token when `Content-Type: application/x-www-form-urlencoded` is set

**Target repo**: `TechnitiumSoftware/DnsServer`
**Issue type**: bug

---

## Summary

`/api/user/login` returns a 35-character `token` value in the JSON response (instead of the expected 64-character hex token) whenever the HTTP request carries `Content-Type: application/x-www-form-urlencoded`. The 35-char token is rejected by every subsequent API call as `{"status": "invalid-token", "errorMessage": "Invalid token or session expired."}`, with no clue at login time that anything went wrong.

The HTTP response on login is otherwise indistinguishable from a successful one (HTTP 200, `status: ok`).

## How to reproduce

```bash
docker run -d --name technitium-test -p 5380:5380 technitium/dns-server:latest

# Working — no Content-Type header on a plain GET, returns a 64-char hex token
curl -s "http://127.0.0.1:5380/api/user/login?user=admin&pass=admin&includeInfo=true" | jq -r .token | wc -c
# 65   (64 chars + newline)

# Broken — same URL, same params, only Content-Type added → 35-char token
curl -s -H "Content-Type: application/x-www-form-urlencoded" \
     "http://127.0.0.1:5380/api/user/login?user=admin&pass=admin&includeInfo=true" \
     | jq -r .token | wc -c
# 36   (35 chars + newline)

# Or via POST body with the same Content-Type → also 35-char broken token
curl -s -X POST -H "Content-Type: application/x-www-form-urlencoded" \
     --data 'user=admin&pass=admin&includeInfo=true' \
     "http://127.0.0.1:5380/api/user/login" \
     | jq -r .token | wc -c
# 36
```

Probing with the broken token:

```bash
TOKEN=<the-35-char-string>
curl -s "http://127.0.0.1:5380/api/zones/list?token=$TOKEN"
# {"server":"...","status":"invalid-token","errorMessage":"Invalid token or session expired."}
```

## Expected behaviour

Either:

1. The login endpoint returns the same 64-char hex token regardless of `Content-Type` (preferred — the request is otherwise valid), OR
2. The login endpoint returns `status: error` with a clear `errorMessage` when it cannot parse the request the way the client intended, instead of returning a 200 OK with a token that does not work.

## Impact

Any HTTP client that defaults to setting `Content-Type: application/x-www-form-urlencoded` (Ansible's `module_utils.urls.fetch_url` does this implicitly, several Python `requests` setups do, most Go HTTP libs do for form encoding helpers) silently produces a broken session for the user. The failure surface is also confusing: the user only sees "Invalid token" on the *next* call, well after the misconfiguration moment.

## Notes

Observed on Technitium DNS Server image `technitium/dns-server:latest` (currently 15.x). Documented as quirk #8 in [`mipsou/mipsou.technitium`](https://github.com/mipsou/mipsou.technitium/blob/main/docs/api_quirks.md).
