#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: session
short_description: Authenticate against a Technitium DNS Server and return a reusable session
version_added: "0.1.0"
description:
  - Opens a session against a Technitium DNS Server through C(/api/user/login) and
    returns a I(session) dict that other modules in the C(mipsou.technitium)
    collection consume.
  - Handles the fresh-container bootstrap flow. Technitium starts with
    C(admin/admin) and does not honour any environment variable for the initial
    admin password. When the declared credentials fail, this module falls back
    to a configurable bootstrap password, rotates the account to the declared
    password and re-authenticates. Re-runs with the declared password succeed
    directly, so the operation is idempotent.
options:
  host:
    description: Hostname or IP address of the Technitium DNS Server.
    type: str
    required: true
  port:
    description: TCP port of the Technitium web admin API.
    type: int
    default: 5380
  scheme:
    description: URL scheme used to reach the API.
    type: str
    choices: [http, https]
    default: http
  validate_certs:
    description: Whether to validate TLS certificates when I(scheme=https).
    type: bool
    default: true
  timeout:
    description: HTTP timeout in seconds for every API call.
    type: int
    default: 30
  user:
    description: Admin user to authenticate as.
    type: str
    default: admin
  password:
    description: Declared (desired) password for I(user).
    type: str
    required: true
  bootstrap_password:
    description:
      - Fallback password to try when login with I(password) fails. On a fresh
        Technitium container this is C(admin).
      - When set, a failed primary login triggers a bootstrap attempt; on
        success the password is rotated to I(password) (unless
        I(rotate_if_bootstrap=false)).
    type: str
  rotate_if_bootstrap:
    description:
      - When C(true) and the bootstrap login succeeds, rotate the password to
        the declared I(password) and re-authenticate.
      - When C(false), leave the password unchanged and return the token
        obtained with the bootstrap password. Useful only for diagnostics.
    type: bool
    default: true
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Open a Technitium session (idempotent, with fresh-container bootstrap)
  mipsou.technitium.session:
    host: 192.168.100.23
    port: 5380
    user: admin
    password: "{{ vault_technitium_admin_password }}"
    bootstrap_password: admin
    rotate_if_bootstrap: true
  register: tech

- name: Use the session in a subsequent module
  mipsou.technitium.zone:
    session: "{{ tech.session }}"
    name: example.lan
    type: primary
    state: present
'''

RETURN = r'''
session:
  description:
    - Opaque dict holding the host, port, scheme, TLS settings and auth token.
    - Pass it verbatim to the C(session) argument of other
      C(mipsou.technitium) modules.
  returned: success
  type: dict
  contains:
    host: {type: str, description: Technitium host.}
    port: {type: int, description: Technitium port.}
    scheme: {type: str, description: http or https.}
    validate_certs: {type: bool, description: TLS verification flag.}
    timeout: {type: int, description: HTTP timeout in seconds.}
    token: {type: str, description: API token (sensitive).}
bootstrap_used:
  description: Whether the bootstrap password was needed to log in.
  returned: success
  type: bool
rotated:
  description: Whether the password was rotated during this run.
  returned: success
  type: bool
'''

import time

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
)


def _looks_like_auth_error(exc):
    """Return True when a TechnitiumError clearly indicates bad credentials.

    Technitium returns HTTP 200 with `status=error` and an errorMessage like
    'Invalid username or password'. We match loosely on the keyword so minor
    wording changes upstream do not break bootstrap detection.
    """
    msg = (exc.error_message or str(exc) or '').lower()
    return any(k in msg for k in ('invalid username', 'invalid password',
                                  'invalid credentials', 'wrong password'))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', required=True),
            port=dict(type='int', default=5380),
            scheme=dict(type='str', choices=['http', 'https'], default='http'),
            validate_certs=dict(type='bool', default=True),
            timeout=dict(type='int', default=30),
            user=dict(type='str', default='admin'),
            password=dict(type='str', required=True, no_log=True),
            bootstrap_password=dict(type='str', no_log=True),
            rotate_if_bootstrap=dict(type='bool', default=True),
        ),
        supports_check_mode=True,
    )

    p = module.params
    client = TechnitiumClient(
        module=module,
        host=p['host'],
        port=p['port'],
        scheme=p['scheme'],
        validate_certs=p['validate_certs'],
        timeout=p['timeout'],
    )

    bootstrap_used = False
    rotated = False

    try:
        client.login(p['user'], p['password'])
    except TechnitiumError as exc:
        if not (_looks_like_auth_error(exc) and p['bootstrap_password']):
            module.fail_json(
                msg='Login failed for user {0!r}: {1}'.format(p['user'], exc),
                error_message=exc.error_message,
            )

        # In check mode we cannot actually log in with the bootstrap password
        # and rotate, so we report the expected change and stop.
        if module.check_mode:
            module.exit_json(
                changed=True,
                bootstrap_used=True,
                rotated=bool(p['rotate_if_bootstrap']),
                session=None,
                msg='Bootstrap would be triggered (check mode).',
            )

        try:
            client.login(p['user'], p['bootstrap_password'])
        except TechnitiumError as boot_exc:
            module.fail_json(
                msg='Primary login failed and bootstrap login also failed: '
                    '{0}'.format(boot_exc),
                error_message=boot_exc.error_message,
            )

        bootstrap_used = True

        if p['rotate_if_bootstrap']:
            try:
                client.change_password(p['bootstrap_password'], p['password'])
            except TechnitiumError as rot_exc:
                module.fail_json(
                    msg='Password rotation after bootstrap failed: {0}'.format(rot_exc),
                    error_message=rot_exc.error_message,
                )
            # Technitium invalidates the session that performed changePassword
            # and needs a brief moment before a fresh login produces a token
            # that survives subsequent calls. Without the sleep, the immediate
            # re-login returns a token rejected as 'invalid-token' on the
            # very next API call.
            time.sleep(1)
            try:
                client.login(p['user'], p['password'])
            except TechnitiumError as relogin_exc:
                module.fail_json(
                    msg='Re-login after password rotation failed: {0}'.format(relogin_exc),
                    error_message=relogin_exc.error_message,
                )
            rotated = True

    # Ansible only masks values flagged no_log in the argument_spec on input.
    # Returned values are NOT masked automatically, so register the token as
    # a no_log value explicitly before exit_json to keep it out of `-v` logs.
    # Do NOT add the session token to no_log_values: Ansible would then
    # replace it with VALUE_SPECIFIED_IN_NO_LOG_PARAMETER in the returned
    # `session` dict, breaking every downstream task that consumes it.
    # The bootstrap password is fine to mask because we never return it.
    if bootstrap_used and p.get('bootstrap_password'):
        module.no_log_values.add(p['bootstrap_password'])

    module.exit_json(
        changed=rotated,
        bootstrap_used=bootstrap_used,
        rotated=rotated,
        session=client.to_session(),
    )


if __name__ == '__main__':
    main()
