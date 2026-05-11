#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: user
short_description: Manage user accounts on a Technitium DNS Server
version_added: "0.1.0"
description:
  - Manages user accounts via C(/api/admin/users/{list,create,get,set,delete}).
  - Password rotation is idempotent. When I(password) is set, the module first
    attempts a login as I(name) with that password; if the login succeeds the
    password is already current and no rotation is performed. This avoids
    perpetual C(changed=True) on re-runs.
  - Group membership, display name, disabled flag and session timeout are
    diffed against the current value before being pushed.
options:
  name:
    description: Username.
    type: str
    required: true
    aliases: [user]
  state:
    description: Whether the user should exist.
    type: str
    choices: [present, absent]
    default: present
  password:
    description:
      - Desired password. Required on creation. On update, used only when it
        differs from the current password (verified by attempting a login).
    type: str
  display_name:
    description: Display name.
    type: str
  disabled:
    description: Whether the user account is disabled.
    type: bool
  session_timeout_seconds:
    description: Session timeout in seconds.
    type: int
  groups:
    description:
      - List of group names the user must be a member of. Replaces the current
        membership entirely (state-based). Omit to leave membership untouched.
    type: list
    elements: str
author:
  - mipsou.technitium contributors
'''

EXAMPLES = r'''
- name: Create a DNS administrator user
  mipsou.technitium.user:
    session: "{{ tech.session }}"
    name: dnsop
    password: "{{ vault_dnsop_password }}"
    display_name: DNS Operator
    groups:
      - DNS Administrators

- name: Rotate the admin password idempotently
  mipsou.technitium.user:
    session: "{{ tech.session }}"
    name: admin
    password: "{{ vault_new_admin_password }}"

- name: Remove a user
  mipsou.technitium.user:
    session: "{{ tech.session }}"
    name: legacy_user
    state: absent
'''

RETURN = r'''
user:
  description: User attributes as reported by Technitium, or C(null) when absent.
  returned: success
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


def _get_user(client, name):
    """Return user details dict, or None when the user does not exist."""
    try:
        payload = client.get('/api/admin/users/get',
                             scalars={'user': name, 'includeGroups': 'true'})
    except TechnitiumError as exc:
        msg = (exc.error_message or str(exc) or '').lower()
        if any(k in msg for k in ('no such user', 'user not found',
                                  'does not exist', 'not found')):
            return None
        raise
    return payload.get('response') or {}


def _password_matches(client, name, password):
    """Probe whether (name, password) is the current credential.

    Performs a throwaway login on a copy of the client so the admin's token is
    left intact regardless of the outcome. The throwaway session lives on the
    server until it expires; we do not bother to log it out.

    A login that fails for reasons unrelated to the password (account disabled,
    2FA enabled, etc.) is treated as "password matches" — otherwise the module
    would attempt a pointless rotation on every re-run.
    """
    probe = TechnitiumClient(
        module=client.module,
        host=client.host,
        port=client.port,
        scheme=client.scheme,
        validate_certs=client.validate_certs,
        timeout=client.timeout,
    )
    try:
        probe.login(name, password)
        try:
            probe.logout()
        except TechnitiumError:
            pass
        return True
    except TechnitiumError as exc:
        msg = (exc.error_message or str(exc) or '').lower()
        wrong_password = any(k in msg for k in (
            'invalid username', 'invalid password', 'invalid credentials',
            'wrong password',
        ))
        return not wrong_password


def _diff_attrs(current, desired):
    """Return {key: {'before': X, 'after': Y}} for desired keys that differ."""
    out = {}
    for k, v in desired.items():
        if v is None:
            continue
        before = current.get(k)
        if k == 'memberOfGroups':
            # Compare as sets — group order is not meaningful.
            if set(before or []) != set(v or []):
                out[k] = {'before': before, 'after': v}
        elif before != v:
            out[k] = {'before': before, 'after': v}
    return out


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True, aliases=['user']),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        password=dict(type='str', no_log=True),
        display_name=dict(type='str'),
        disabled=dict(type='bool'),
        session_timeout_seconds=dict(type='int'),
        groups=dict(type='list', elements='str'),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
    )

    p = module.params
    name = p['name']
    desired_state = p['state']

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        current = _get_user(client, name)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to read user {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    if desired_state == 'absent':
        if current is None:
            module.exit_json(changed=False, user=None,
                             diff={'before': None, 'after': None})
        if module.check_mode:
            module.exit_json(changed=True, user=None,
                             diff={'before': current, 'after': None})
        try:
            client.post('/api/admin/users/delete', scalars={'user': name})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to delete user {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, user=None,
                         diff={'before': current, 'after': None})

    # state == 'present'
    did_create = False
    if current is None:
        if not p.get('password'):
            module.fail_json(msg='password is required when creating user {0!r}'.format(name))
        scalars = {'user': name, 'pass': p['password']}
        if p.get('display_name'):
            scalars['displayName'] = p['display_name']
        if module.check_mode:
            module.exit_json(changed=True, user={'username': name},
                             diff={'before': None, 'after': {'username': name}})
        try:
            payload = client.post('/api/admin/users/create', scalars=scalars)
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to create user {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        created = payload.get('response') or {'username': name}
        # `create` does not accept disabled/sessionTimeout/groups — apply via set
        # if any were declared, by falling through to the update path.
        current = created
        did_create = True

    desired = {
        'displayName': p.get('display_name'),
        'disabled': p.get('disabled'),
        'sessionTimeoutSeconds': p.get('session_timeout_seconds'),
        'memberOfGroups': p.get('groups'),
    }
    attr_changes = _diff_attrs(current, desired)

    password_change = False
    # Skip the probe-login right after a create: we just set this password
    # ourselves, so we know it matches.
    if p.get('password') and not did_create:
        if not _password_matches(client, name, p['password']):
            password_change = True

    if not attr_changes and not password_change:
        module.exit_json(changed=did_create, user=current,
                         diff={'before': None if did_create else current,
                               'after': current})

    if module.check_mode:
        merged = dict(current)
        for k, v in attr_changes.items():
            merged[k] = v['after']
        module.exit_json(
            changed=True,
            user=merged,
            diff={'before': current, 'after': merged},
            password_change=password_change,
        )

    scalars = {'user': name}
    for k, v in attr_changes.items():
        if k == 'memberOfGroups':
            scalars[k] = ','.join(v['after'] or []) if v['after'] is not None else ''
        else:
            scalars[k] = v['after']
    if password_change:
        scalars['newPass'] = p['password']

    try:
        payload = client.post('/api/admin/users/set', scalars=scalars)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to update user {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )
    updated = payload.get('response') or current
    module.exit_json(
        changed=True,
        user=updated,
        diff={'before': current, 'after': updated},
        password_change=password_change,
    )


if __name__ == '__main__':
    main()
