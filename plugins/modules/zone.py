#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: zone
short_description: Manage authoritative zones on a Technitium DNS Server
version_added: "0.1.0"
description:
  - Creates or deletes authoritative DNS zones on a Technitium DNS Server.
  - "Idempotent: re-running with the same parameters reports C(changed=false)."
  - When a zone already exists with a different I(type), the module fails
    rather than silently converting it. Convert deliberately by deleting and
    recreating, or use C(/api/zones/convert) directly via the C(uri) module.
options:
  name:
    description: Zone name. For reverse zones, an IP address or CIDR network
      address is accepted; Technitium derives the in-addr.arpa name itself.
    type: str
    required: true
    aliases: [zone]
  type:
    description:
      - Zone type. Required when I(state=present).
      - Forwarder zones additionally require I(forwarder).
      - Secondary/Stub/SecondaryForwarder/SecondaryCatalog zones may require
        I(primary_name_server_addresses).
    type: str
    choices:
      - Primary
      - Secondary
      - Stub
      - Forwarder
      - SecondaryForwarder
      - Catalog
      - SecondaryCatalog
  state:
    description: Whether the zone should exist.
    type: str
    choices: [present, absent]
    default: present
  forwarder:
    description:
      - Forwarder address to use when I(type=Forwarder). The special value
        C(this-server) can be used to forward to the local DNS server.
    type: str
  forwarder_protocol:
    description: Transport protocol for a Forwarder zone.
    type: str
    choices: [Udp, Tcp, Tls, Https, Quic]
  initialize_forwarder:
    description:
      - When I(type=Forwarder), set to C(false) to create an empty Forwarder
        zone without the initial FWD record.
    type: bool
  primary_name_server_addresses:
    description: Comma-separated IP addresses or domain names of the primary
      name server. Used by Secondary/Stub/SecondaryForwarder/SecondaryCatalog
      zones.
    type: list
    elements: str
  dnssec_validation:
    description: Enable DNSSEC validation. Only for Forwarder zones.
    type: bool
  use_soa_serial_date_scheme:
    description: Use a date-based SOA serial. Primary, Forwarder, Catalog only.
    type: bool
seealso:
  - module: mipsou.technitium.record
extends_documentation_fragment:
  - mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Create a primary zone
  mipsou.technitium.zone:
    session: "{{ tech.session }}"
    name: example.lan
    type: Primary
    state: present

- name: Create a conditional forwarder zone for reverse DNS
  mipsou.technitium.zone:
    session: "{{ tech.session }}"
    name: 100.168.192.in-addr.arpa
    type: Forwarder
    forwarder: 192.168.100.254
    forwarder_protocol: Udp

- name: Remove a zone
  mipsou.technitium.zone:
    session: "{{ tech.session }}"
    name: example.lan
    state: absent
'''

RETURN = r'''
zone:
  description: Zone properties as reported by Technitium, or C(null) when absent.
  returned: success
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


def _looks_like_missing_zone(exc):
    msg = (exc.error_message or str(exc) or '').lower()
    return any(k in msg for k in ('no such zone', 'zone was not found',
                                  'zone does not exist', 'no zone found',
                                  'not found'))


def _get_zone_options(client, name):
    """Return zone options dict, or None when the zone does not exist."""
    try:
        payload = client.get('/api/zones/options/get', scalars={'zone': name})
    except TechnitiumError as exc:
        if _looks_like_missing_zone(exc):
            return None
        raise
    return payload.get('response') or {}


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True, aliases=['zone']),
        type=dict(type='str', choices=[
            'Primary', 'Secondary', 'Stub', 'Forwarder',
            'SecondaryForwarder', 'Catalog', 'SecondaryCatalog',
        ]),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        forwarder=dict(type='str'),
        forwarder_protocol=dict(type='str',
                                choices=['Udp', 'Tcp', 'Tls', 'Https', 'Quic']),
        initialize_forwarder=dict(type='bool'),
        primary_name_server_addresses=dict(type='list', elements='str'),
        dnssec_validation=dict(type='bool'),
        use_soa_serial_date_scheme=dict(type='bool'),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['type']),
        ],
    )

    p = module.params
    name = p['name']
    desired_state = p['state']
    desired_type = p['type']

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        current = _get_zone_options(client, name)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to read zone state for {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    diff = {'before': current, 'after': current}

    if desired_state == 'absent':
        if current is None:
            module.exit_json(changed=False, zone=None, diff=diff)
        if module.check_mode:
            module.exit_json(changed=True, zone=None,
                             diff={'before': current, 'after': None})
        try:
            client.post('/api/zones/delete', scalars={'zone': name})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to delete zone {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, zone=None,
                         diff={'before': current, 'after': None})

    # state == 'present'
    if current is not None:
        existing_type = current.get('type')
        if existing_type and existing_type != desired_type:
            module.fail_json(
                msg=("Zone {0!r} exists with type {1!r}; refusing to convert "
                     "to {2!r}. Delete the zone first or convert it "
                     "deliberately via /api/zones/convert.").format(
                    name, existing_type, desired_type),
            )
        module.exit_json(changed=False, zone=current, diff=diff)

    scalars = {'zone': name, 'type': desired_type}
    if desired_type == 'Forwarder':
        if not p.get('forwarder') and p.get('initialize_forwarder') is not False:
            module.fail_json(
                msg='type=Forwarder requires forwarder, or initialize_forwarder=false '
                    'to create an empty zone.')
        if p.get('forwarder'):
            scalars['forwarder'] = p['forwarder']
        if p.get('forwarder_protocol'):
            scalars['protocol'] = p['forwarder_protocol']
        if p.get('dnssec_validation') is not None:
            scalars['dnssecValidation'] = p['dnssec_validation']
        if p.get('initialize_forwarder') is not None:
            scalars['initializeForwarder'] = p['initialize_forwarder']
    if p.get('primary_name_server_addresses'):
        scalars['primaryNameServerAddresses'] = ','.join(p['primary_name_server_addresses'])
    if p.get('use_soa_serial_date_scheme') is not None:
        scalars['useSoaSerialDateScheme'] = p['use_soa_serial_date_scheme']

    if module.check_mode:
        module.exit_json(
            changed=True,
            zone={'name': name, 'type': desired_type},
            diff={'before': None, 'after': {'name': name, 'type': desired_type}},
        )

    try:
        client.post('/api/zones/create', scalars=scalars)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to create zone {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    try:
        created = _get_zone_options(client, name)
    except TechnitiumError:
        created = {'name': name, 'type': desired_type}

    module.exit_json(
        changed=True,
        zone=created,
        diff={'before': None, 'after': created},
    )


if __name__ == '__main__':
    main()
