#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)
# SPDX-License-Identifier: EUPL-1.2

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: allowed_zone
short_description: Manage entries in the Technitium Allowed Zones list
version_added: "0.1.0"
description:
  - Adds or removes a domain in the Technitium Allowed Zones list via
    C(/api/allowed/{list,add,delete}).
  - The Allowed Zones list is the domain-level allow-list — entries here are
    always resolved normally, even when they match a blocklist. This is the
    correct mechanism for whitelisting domains, since the C(blockingBypassList)
    setting only accepts source network addresses (see C(setting)).
options:
  name:
    description: Domain name to allow or remove.
    type: str
    required: true
    aliases: [domain]
  state:
    description: Whether the domain must be present in the allow-list.
    type: str
    choices: [present, absent]
    default: present
seealso:
  - module: mipsou.technitium.blocked_zone
  - module: mipsou.technitium.setting
extends_documentation_fragment:
  - mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Allow netflix.com regardless of blocklists
  mipsou.technitium.allowed_zone:
    session: "{{ tech.session }}"
    name: netflix.com

- name: Remove from the allow-list
  mipsou.technitium.allowed_zone:
    session: "{{ tech.session }}"
    name: netflix.com
    state: absent
'''

RETURN = r'''
allowed:
  description: Whether the domain is in the allow-list after the call.
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
        present = is_zone_listed(client, 'allowed', name)
    except TechnitiumError as exc:
        module.fail_json(msg='Failed to list allowed zones: {0}'.format(exc),
                         error_message=exc.error_message)

    desired_present = (desired_state == 'present')
    if present == desired_present:
        module.exit_json(changed=False, allowed=present,
                         diff={'before': present, 'after': present})

    if module.check_mode:
        module.exit_json(changed=True, allowed=desired_present,
                         diff={'before': present, 'after': desired_present})

    path = '/api/allowed/' + ('add' if desired_present else 'delete')
    try:
        client.post(path, scalars={'domain': name})
    except TechnitiumError as exc:
        module.fail_json(msg='Failed to {0} {1!r}: {2}'.format(
                             'add' if desired_present else 'delete', name, exc),
                         error_message=exc.error_message)

    module.exit_json(changed=True, allowed=desired_present,
                     diff={'before': present, 'after': desired_present})


if __name__ == '__main__':
    main()
