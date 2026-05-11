#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: blocked_zone
short_description: Manage entries in the Technitium Blocked Zones list
version_added: "0.1.0"
description:
  - Adds or removes a domain in the Technitium Blocked Zones list via
    C(/api/blocked/{list,add,delete}).
  - Blocked Zones is the manual block-list, separate from C(blockListUrls)
    which downloads upstream feeds. Use this module for one-off blocks; use
    C(blocklist) to manage subscribed lists.
options:
  name:
    description: Domain name to block or remove.
    type: str
    required: true
    aliases: [domain]
  state:
    description: Whether the domain must be present in the block-list.
    type: str
    choices: [present, absent]
    default: present
seealso:
  - module: mipsou.technitium.allowed_zone
  - module: mipsou.technitium.blocklist
author:
  - mipsou.technitium contributors
'''

EXAMPLES = r'''
- name: Manually block a domain
  mipsou.technitium.blocked_zone:
    session: "{{ tech.session }}"
    name: tracker.example

- name: Unblock
  mipsou.technitium.blocked_zone:
    session: "{{ tech.session }}"
    name: tracker.example
    state: absent
'''

RETURN = r'''
blocked:
  description: Whether the domain is in the block-list after the call.
  returned: success
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
    is_zone_listed,
)


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True, aliases=['domain']),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
    ))

    module = AnsibleModule(argument_spec=spec, supports_check_mode=True)

    p = module.params
    name = p['name']
    desired_state = p['state']

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        present = is_zone_listed(client, 'blocked', name)
    except TechnitiumError as exc:
        module.fail_json(msg='Failed to list blocked zones: {0}'.format(exc),
                         error_message=exc.error_message)

    desired_present = (desired_state == 'present')
    if present == desired_present:
        module.exit_json(changed=False, blocked=present,
                         diff={'before': present, 'after': present})

    if module.check_mode:
        module.exit_json(changed=True, blocked=desired_present,
                         diff={'before': present, 'after': desired_present})

    path = '/api/blocked/' + ('add' if desired_present else 'delete')
    try:
        client.post(path, scalars={'domain': name})
    except TechnitiumError as exc:
        module.fail_json(msg='Failed to {0} {1!r}: {2}'.format(
                             'add' if desired_present else 'delete', name, exc),
                         error_message=exc.error_message)

    module.exit_json(changed=True, blocked=desired_present,
                     diff={'before': present, 'after': desired_present})


if __name__ == '__main__':
    main()
