# `changePassword` followed by an immediate re-login yields a token rejected on first use

**Target repo**: `TechnitiumSoftware/DnsServer`
**Issue type**: bug

---

## Summary

The bootstrap-and-rotate sequence on a fresh Technitium container — `login(admin/admin) → changePassword(pass=admin, newPass=<X>) → login(admin/<X>)` — produces a session token that Technitium rejects as `invalid-token` on the very next API call. Both the original bootstrap token and the freshly-issued post-rotation token are affected, even when seconds elapse between rotation and the next request.

## How to reproduce

```bash
docker run --rm -d --name technitium-test -p 5380:5380 technitium/dns-server:latest
# wait for the API to come up
sleep 2

# 1. Login with the default admin/admin
T1=$(curl -s "http://127.0.0.1:5380/api/user/login?user=admin&pass=admin&includeInfo=true" | jq -r .token)
echo "bootstrap token: $T1"

# 2. Rotate the password
curl -s "http://127.0.0.1:5380/api/user/changePassword?token=$T1&pass=admin&newPass=SmokeTestPwd2026"
# {"status": "ok"}

# 3. Re-login with the new password
T2=$(curl -s "http://127.0.0.1:5380/api/user/login?user=admin&pass=SmokeTestPwd2026&includeInfo=true" | jq -r .token)
echo "post-rotation token: $T2"

# 4. Either token immediately fails
curl -s "http://127.0.0.1:5380/api/zones/list?token=$T2"
# {"status": "invalid-token", "errorMessage": "Invalid token or session expired."}
```

Adding a `sleep 1` between steps 2 and 3, or between 3 and 4, does not make the post-rotation token valid.

## Expected behaviour

After a successful `changePassword`, a freshly-issued login token under the new password should be valid for the configured session lifetime — same as any first-time login.

## Impact

The "fresh container → first-time admin password rotation" use case is exactly what most operators script as part of an automated deployment. Any Ansible/Terraform pipeline that wants to leave admin/admin behind has to either:

- live with a broken token after the rotation and reinitialize a moment later (unreliable, timing-dependent), or
- skip the rotation entirely and leave admin/admin in place (a non-starter for production), or
- pre-create a permanent API token via `/api/admin/sessions/createToken` *before* changing the password, then drop the bootstrap session — undocumented as a recommended path.

## Workaround we use

[`mipsou/mipsou.technitium`](https://github.com/mipsou/mipsou.technitium)'s `session` module keeps the bootstrap+rotation code (it is the actual production code path) but the rotation is not covered by CI smoke. Documented as quirk #10 in `docs/api_quirks.md`. We'd love to remove the workaround once this is fixed upstream.

## Notes

Observed on Technitium DNS Server image `technitium/dns-server:latest` (currently 15.x). Tied to CI runs:
- working flow without rotation: <https://github.com/mipsou/mipsou.technitium/actions/runs/25690502545>
- failing flow with rotation: <https://github.com/mipsou/mipsou.technitium/actions/runs/25689665798>
