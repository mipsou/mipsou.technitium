#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)
# SPDX-License-Identifier: EUPL-1.2

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: token
short_description: Manage permanent API tokens for a Technitium user
version_added: "0.2.0"
description:
  - Manages permanent API tokens through
    C(/api/user/{createToken,listTokens,deleteToken}).
  - Idempotency is based on the token I(name) (the human label). A token's
    value is **write-once** in Technitium — it is returned at creation time
    only and cannot be read back later. Re-runs with the same I(name)
    therefore return C(changed=false) but **do not** include the token
    value; the caller is expected to capture it from the first run and
    store it (vault, password manager).
  - To rotate a token, declare I(state=absent) then re-declare I(state=present)
    in a subsequent task (or run) — a fresh token is generated and returned.
options:
  name:
    description:
      - Human-readable token label (the C(tokenName) parameter in the
        Technitium API). Acts as the idempotency key.
    type: str
    required: true
    aliases: [token_name]
  state:
    description: Whether the token should exist.
    type: str
    choices: [present, absent]
    default: present
  user:
    description:
      - User account that owns the token. Defaults to the currently
        authenticated session user. Admins can manage tokens for other users
        by setting this explicitly.
    type: str
  password:
    description:
      - User password — **required for I(state=present)** because Technitium
        validates ownership of the user account before issuing a permanent
        token, even when the caller is already authenticated as that user.
      - Not used for I(state=absent).
    type: str
extends_documentation_fragment:
  - mipsou.technitium.session
seealso:
  - module: mipsou.technitium.user
  - module: mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Create a permanent token for the claude user (returned once)
  mipsou.technitium.token:
    session: "{{ tech.session }}"
    name: claude-cli
    user: claude
    password: "{{ vault_technitium_claude_password }}"
  register: claude_token
  no_log: true

- name: Persist the new token to a local file on first creation
  ansible.builtin.copy:
    content: "{{ claude_token.token }}\n"
    dest: "~/.config/ansible/technitium-claude.token"
    mode: "0600"
  when: claude_token.created and claude_token.token is defined
  delegate_to: localhost

- name: Revoke an old token by name
  mipsou.technitium.token:
    session: "{{ tech.session }}"
    name: legacy-runner
    user: pra-ansible
    state: absent
'''

RETURN = r'''
token:
  description:
    - The permanent token string. **Only returned on creation** — re-runs that
      find an existing token by I(name) do not return the value (write-once
      API). Treat as sensitive.
  returned: when a new token was created
  type: str
created:
  description: Whether a new token was created in this run.
  returned: success
  type: bool
name:
  description: The token label that was managed.
  returned: success
  type: str
user:
  description: The user account the token belongs to.
  returned: success
  type: str
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


def _list_tokens(client, user):
    """Return list of token dicts for a user (or current session if user=None).

    Technitium's /api/user/listTokens returns the current user's tokens.
    Admins can pass `user=X` to list another user's tokens; on older servers
    this parameter may be ignored — in which case the caller is the user.
    """
    scalars = {}
    if user:
        scalars['user'] = user
    payload = client.get('/api/user/listTokens', scalars=scalars or None)
    return (payload.get('response') or {}).get('tokens') or []


def _find_named(tokens, name):
    """Find a token by exact tokenName in a list; return the dict or None."""
    for t in tokens:
        if t.get('tokenName') == name:
            return t
    return None


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True, aliases=['token_name']),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        user=dict(type='str'),
        password=dict(type='str', no_log=True),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ('password',)),
        ],
    )

    p = module.params
    name = p['name']
    desired_state = p['state']
    user = p.get('user')

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        existing = _find_named(_list_tokens(client, user), name)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to list tokens: {0}'.format(exc),
            error_message=exc.error_message,
        )

    # ── state: absent ────────────────────────────────────────────────────────
    if desired_state == 'absent':
        if existing is None:
            module.exit_json(changed=False, created=False, name=name, user=user,
                             diff={'before': None, 'after': None})
        if module.check_mode:
            module.exit_json(changed=True, created=False, name=name, user=user,
                             diff={'before': existing, 'after': None})
        scalars = {'tokenName': name}
        if user:
            scalars['user'] = user
        try:
            client.post('/api/user/deleteToken', scalars=scalars)
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to delete token {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, created=False, name=name, user=user,
                         diff={'before': existing, 'after': None})

    # ── state: present ───────────────────────────────────────────────────────
    if existing is not None:
        # Token already exists — write-once API, we cannot fetch the value.
        # Return changed=false and let the caller rely on whatever they
        # captured on the original creation run.
        module.exit_json(
            changed=False,
            created=False,
            name=name,
            user=user or existing.get('user'),
            diff={'before': existing, 'after': existing},
        )

    if module.check_mode:
        module.exit_json(
            changed=True,
            created=True,
            name=name,
            user=user,
            diff={'before': None, 'after': {'tokenName': name, 'user': user}},
        )

    scalars = {'tokenName': name, 'pass': p['password']}
    if user:
        scalars['user'] = user
    try:
        payload = client.post('/api/user/createToken', scalars=scalars)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to create token {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    token_value = (
        payload.get('token')
        or (payload.get('response') or {}).get('token')
    )
    if not token_value:
        module.fail_json(
            msg='Technitium did not return a token value on createToken — '
                'API contract changed?',
        )

    # Mask the new token from any verbose log output.
    module.no_log_values.add(token_value)

    module.exit_json(
        changed=True,
        created=True,
        token=token_value,
        name=name,
        user=user,
        diff={'before': None, 'after': {'tokenName': name, 'user': user}},
    )


if __name__ == '__main__':
    main()
