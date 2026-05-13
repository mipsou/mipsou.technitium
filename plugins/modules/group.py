#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)
# SPDX-License-Identifier: EUPL-1.2

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: group
short_description: Manage user groups on a Technitium DNS Server
version_added: "0.2.0"
description:
  - Manages groups via C(/api/admin/groups/{list,create,get,set,delete}).
  - Group membership and description are diffed against the current state
    before being pushed (idempotent on re-run).
  - When I(permissions) is set, the per-section permission dict is forwarded
    as a JSON-encoded string to C(/api/admin/groups/set). The exact schema
    is Technitium API-version dependent — see the upstream
    L(APIDOCS,https://github.com/TechnitiumSoftware/DnsServer/blob/master/APIDOCS.md)
    for the permission object format expected by your server version.
options:
  name:
    description: Group name (exact, case-sensitive).
    type: str
    required: true
    aliases: [group]
  state:
    description: Whether the group should exist.
    type: str
    choices: [present, absent]
    default: present
  description:
    description: Human-readable group description.
    type: str
  members:
    description:
      - List of usernames that must be members of the group. Replaces the
        current membership entirely (state-based). Omit to leave the
        membership untouched.
    type: list
    elements: str
  permissions:
    description:
      - Per-section permission dict pushed to the group, JSON-encoded on the
        wire. Schema is API-version dependent (see Technitium APIDOCS).
      - Omit to leave the permissions untouched.
    type: dict
extends_documentation_fragment:
  - mipsou.technitium.session
seealso:
  - module: mipsou.technitium.user
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Ensure grp_ia exists with claude as member
  mipsou.technitium.group:
    session: "{{ tech.session }}"
    name: grp_ia
    description: "AI assistants (Claude, etc.) — scoped DNS admin"
    members:
      - claude

- name: Ensure grp_mobile exists with the household mobile devices
  mipsou.technitium.group:
    session: "{{ tech.session }}"
    name: grp_mobile
    description: "Smartphone admin / monitoring (Technitium DNS Manager / dns-control)"
    members:
      - mi12

- name: Remove an obsolete group
  mipsou.technitium.group:
    session: "{{ tech.session }}"
    name: legacy_grp
    state: absent
'''

RETURN = r'''
group:
  description: Group attributes as reported by Technitium, or C(null) when absent.
  returned: success
  type: dict
'''

import json

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


def _get_group(client, name):
    """Return group details dict, or None when the group does not exist."""
    try:
        payload = client.get('/api/admin/groups/get',
                             scalars={'group': name, 'includeUsers': 'true'})
    except TechnitiumError as exc:
        msg = (exc.error_message or str(exc) or '').lower()
        if any(k in msg for k in ('no such group', 'group not found',
                                  'does not exist', 'not found')):
            return None
        raise
    return payload.get('response') or {}


def _diff_attrs(current, desired):
    """Return {key: {'before': X, 'after': Y}} for desired keys that differ."""
    out = {}
    for k, v in desired.items():
        if v is None:
            continue
        before = current.get(k)
        if k == 'members':
            # Compare as sets — order is not meaningful for membership.
            if set(before or []) != set(v or []):
                out[k] = {'before': before, 'after': v}
        elif k == 'permissions':
            # Opaque dict — compare deeply.
            if (before or {}) != (v or {}):
                out[k] = {'before': before, 'after': v}
        elif before != v:
            out[k] = {'before': before, 'after': v}
    return out


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True, aliases=['group']),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        description=dict(type='str'),
        members=dict(type='list', elements='str'),
        permissions=dict(type='dict'),
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
        current = _get_group(client, name)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to read group {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    # ── state: absent ────────────────────────────────────────────────────────
    if desired_state == 'absent':
        if current is None:
            module.exit_json(changed=False, group=None,
                             diff={'before': None, 'after': None})
        if module.check_mode:
            module.exit_json(changed=True, group=None,
                             diff={'before': current, 'after': None})
        try:
            client.post('/api/admin/groups/delete', scalars={'group': name})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to delete group {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, group=None,
                         diff={'before': current, 'after': None})

    # ── state: present ───────────────────────────────────────────────────────
    did_create = False
    if current is None:
        if module.check_mode:
            module.exit_json(changed=True, group={'name': name},
                             diff={'before': None, 'after': {'name': name}})
        try:
            client.post('/api/admin/groups/create', scalars={'group': name})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to create group {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        # `create` does not accept description/members/permissions — they are
        # applied via /set below if any were declared.
        current = {'name': name}
        did_create = True

    desired = {
        'description': p.get('description'),
        'members': p.get('members'),
        'permissions': p.get('permissions'),
    }
    attr_changes = _diff_attrs(current, desired)

    if not attr_changes:
        module.exit_json(changed=did_create, group=current,
                         diff={'before': None if did_create else current,
                               'after': current})

    if module.check_mode:
        merged = dict(current)
        for k, v in attr_changes.items():
            merged[k] = v['after']
        module.exit_json(
            changed=True,
            group=merged,
            diff={'before': current, 'after': merged},
        )

    scalars = {'group': name}
    for k, v in attr_changes.items():
        if k == 'members':
            scalars['members'] = (
                ','.join(v['after'] or []) if v['after'] is not None else ''
            )
        elif k == 'permissions':
            scalars['permissions'] = json.dumps(
                v['after'], separators=(',', ':'), sort_keys=True)
        else:
            scalars[k] = v['after']

    try:
        payload = client.post('/api/admin/groups/set', scalars=scalars)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to update group {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )
    updated = payload.get('response') or current
    module.exit_json(
        changed=True,
        group=updated,
        diff={'before': current, 'after': updated},
    )


if __name__ == '__main__':
    main()
