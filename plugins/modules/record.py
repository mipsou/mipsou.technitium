#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: record
short_description: Manage individual DNS records on a Technitium DNS Server
version_added: "0.1.0"
description:
  - Adds or removes a single resource record in an authoritative zone.
  - Idempotency is keyed on the tuple C((name, type, type-specific value)).
    Two A records with the same name but different IP addresses are treated as
    two distinct resources, matching Technitium's record-set semantics.
  - Updating an existing record's TTL or comments is not supported in
    v0.1.0 — delete and recreate it, or use C(/api/zones/records/update)
    via the C(uri) module. The match logic deliberately ignores TTL and
    comments to keep re-runs idempotent against the live state.
options:
  zone:
    description:
      - Authoritative zone the record belongs to. Optional; when omitted,
        Technitium uses the closest authoritative zone for I(name).
    type: str
  name:
    description: Fully-qualified record name (the C(domain) parameter in
      the Technitium API).
    type: str
    required: true
    aliases: [domain]
  type:
    description: DNS resource record type.
    type: str
    required: true
    choices: [A, AAAA, NS, CNAME, PTR, MX, TXT, SRV]
  state:
    description: Whether the record should exist.
    type: str
    choices: [present, absent]
    default: present
  ttl:
    description: TTL in seconds. Only applied on create; ignored when the
      record already exists.
    type: int
  comments:
    description: Free-form comment stored with the record. Only applied on
      create.
    type: str
  overwrite:
    description:
      - When C(true), replaces the entire record set for I(type) at I(name)
        with the declared record. Use with care — destroys other records of
        the same type at the same name.
    type: bool
    default: false
  ip_address:
    description: Required for I(type=A) and I(type=AAAA). The Technitium
      special value C(request-ip-address) is accepted.
    type: str
  name_server:
    description: Required for I(type=NS).
    type: str
  glue:
    description: Comma-separated glue addresses for I(type=NS).
    type: str
  cname:
    description: Required for I(type=CNAME).
    type: str
  ptr_name:
    description: Required for I(type=PTR).
    type: str
  exchange:
    description: Required for I(type=MX).
    type: str
  preference:
    description: Required for I(type=MX).
    type: int
  text:
    description: Required for I(type=TXT).
    type: str
  split_text:
    description: For I(type=TXT). If C(true), Technitium splits the text on
      newlines into multiple character-strings.
    type: bool
  priority:
    description: Required for I(type=SRV).
    type: int
  weight:
    description: Required for I(type=SRV).
    type: int
  port:
    description: Required for I(type=SRV).
    type: int
  target:
    description: Required for I(type=SRV).
    type: str
seealso:
  - module: mipsou.technitium.zone
author:
  - mipsou.technitium contributors
'''

EXAMPLES = r'''
- name: A record for ns1
  mipsou.technitium.record:
    session: "{{ tech.session }}"
    zone: example.lan
    name: ns1.example.lan
    type: A
    ip_address: 192.168.1.10
    ttl: 3600

- name: Add a second A record for the same name (round-robin)
  mipsou.technitium.record:
    session: "{{ tech.session }}"
    zone: example.lan
    name: ns1.example.lan
    type: A
    ip_address: 192.168.1.11

- name: Remove an MX record
  mipsou.technitium.record:
    session: "{{ tech.session }}"
    zone: example.lan
    name: example.lan
    type: MX
    exchange: mail.example.lan
    preference: 10
    state: absent
'''

RETURN = r'''
record:
  description: Record properties as reported by Technitium, or C(null) when absent.
  returned: success
  type: dict
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


# (record type) -> (param name in our module, key in rData, name of the
# query parameter accepted by /api/zones/records/{add,delete}). Order matters
# for matching: every entry is compared for equality.
_VALUE_FIELDS = {
    'A':     [('ip_address', 'ipAddress', 'ipAddress', 'str')],
    'AAAA':  [('ip_address', 'ipAddress', 'ipAddress', 'str')],
    'CNAME': [('cname',       'cname',     'cname',     'fqdn')],
    'NS':    [('name_server', 'nameServer','nameServer','fqdn')],
    'PTR':   [('ptr_name',    'ptrName',   'ptrName',   'fqdn')],
    'MX':    [('exchange',    'exchange',  'exchange',  'fqdn'),
              ('preference',  'preference','preference','int')],
    'TXT':   [('text',        'text',      'text',      'str')],
    'SRV':   [('priority',    'priority',  'priority',  'int'),
              ('weight',      'weight',    'weight',    'int'),
              ('port',        'port',      'port',      'int'),
              ('target',      'target',    'target',    'fqdn')],
}


def _norm(value, kind):
    if value is None:
        return None
    if kind == 'int':
        return int(value)
    if kind == 'fqdn':
        return str(value).rstrip('.').lower()
    return str(value)


def _required_value_params(module, type_):
    params = _VALUE_FIELDS[type_]
    missing = [p[0] for p in params if module.params.get(p[0]) is None]
    if missing:
        module.fail_json(
            msg='type={0!r} requires parameter(s): {1}'.format(type_, ', '.join(missing)),
        )


def _record_matches(rdata, type_, module_params):
    """Return True if the rData of an existing record matches the declared
    type-specific values from the module parameters."""
    for module_key, rdata_key, _api_key, kind in _VALUE_FIELDS[type_]:
        if _norm(rdata.get(rdata_key), kind) != _norm(module_params.get(module_key), kind):
            return False
    return True


def _find_record(client, zone, name, type_, module_params):
    scalars = {'domain': name}
    if zone:
        scalars['zone'] = zone
    try:
        payload = client.get('/api/zones/records/get', scalars=scalars)
    except TechnitiumError as exc:
        msg = (exc.error_message or str(exc) or '').lower()
        if any(k in msg for k in ('no such zone', 'zone was not found',
                                  'zone does not exist', 'not found')):
            return None
        raise
    records = (payload.get('response') or {}).get('records') or []
    for rec in records:
        if rec.get('type') != type_:
            continue
        if rec.get('name', '').rstrip('.').lower() != name.rstrip('.').lower():
            continue
        if _record_matches(rec.get('rData') or {}, type_, module_params):
            return rec
    return None


def _build_value_scalars(type_, module_params):
    scalars = {}
    for module_key, _rdata_key, api_key, _kind in _VALUE_FIELDS[type_]:
        v = module_params.get(module_key)
        if v is not None:
            scalars[api_key] = v
    return scalars


def main():
    spec = common_argument_spec()
    spec.update(dict(
        zone=dict(type='str'),
        name=dict(type='str', required=True, aliases=['domain']),
        type=dict(type='str', required=True,
                  choices=['A', 'AAAA', 'NS', 'CNAME', 'PTR', 'MX', 'TXT', 'SRV']),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        ttl=dict(type='int'),
        comments=dict(type='str'),
        overwrite=dict(type='bool', default=False),
        # type-specific fields
        ip_address=dict(type='str'),
        name_server=dict(type='str'),
        glue=dict(type='str'),
        cname=dict(type='str'),
        ptr_name=dict(type='str'),
        exchange=dict(type='str'),
        preference=dict(type='int'),
        text=dict(type='str'),
        split_text=dict(type='bool'),
        priority=dict(type='int'),
        weight=dict(type='int'),
        port=dict(type='int'),
        target=dict(type='str'),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
    )

    p = module.params
    name = p['name']
    zone = p.get('zone')
    type_ = p['type']

    _required_value_params(module, type_)

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        existing = _find_record(client, zone, name, type_, p)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to read records for {0!r}: {1}'.format(name, exc),
            error_message=exc.error_message,
        )

    if p['state'] == 'absent':
        if existing is None:
            module.exit_json(changed=False, record=None,
                             diff={'before': None, 'after': None})
        if module.check_mode:
            module.exit_json(changed=True, record=None,
                             diff={'before': existing, 'after': None})
        scalars = {'domain': name, 'type': type_}
        if zone:
            scalars['zone'] = zone
        scalars.update(_build_value_scalars(type_, p))
        if type_ == 'TXT' and p.get('split_text') is not None:
            scalars['splitText'] = p['split_text']
        try:
            client.post('/api/zones/records/delete', scalars=scalars)
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to delete record: {0}'.format(exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, record=None,
                         diff={'before': existing, 'after': None})

    # state == 'present'
    if existing is not None:
        module.exit_json(changed=False, record=existing,
                         diff={'before': existing, 'after': existing})

    scalars = {'domain': name, 'type': type_, 'overwrite': p['overwrite']}
    if zone:
        scalars['zone'] = zone
    if p.get('ttl') is not None:
        scalars['ttl'] = p['ttl']
    if p.get('comments'):
        scalars['comments'] = p['comments']
    scalars.update(_build_value_scalars(type_, p))
    if type_ == 'NS' and p.get('glue'):
        scalars['glue'] = p['glue']
    if type_ == 'TXT' and p.get('split_text') is not None:
        scalars['splitText'] = p['split_text']

    if module.check_mode:
        module.exit_json(changed=True, record={'name': name, 'type': type_},
                         diff={'before': None, 'after': {'name': name, 'type': type_}})

    try:
        payload = client.post('/api/zones/records/add', scalars=scalars)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to add {0} record for {1!r}: {2}'.format(type_, name, exc),
            error_message=exc.error_message,
        )

    added = (payload.get('response') or {}).get('addedRecord') or {
        'name': name, 'type': type_,
    }
    module.exit_json(changed=True, record=added,
                     diff={'before': None, 'after': added})


if __name__ == '__main__':
    main()
