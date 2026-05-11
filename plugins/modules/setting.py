#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: setting
short_description: Manage Technitium DNS Server settings with diff and idempotency
version_added: "0.1.0"
description:
  - Reads the current settings via C(/api/settings/get), diffs against the
    declared I(settings) dict, and only pushes the delta via
    C(/api/settings/set). Returns C(changed=false) when the live state already
    matches.
  - Validates that every entry in C(blockingBypassList) parses as an IP
    address or CIDR network. Domain entries are rejected because Technitium
    silently fails on them — domain allow-listing belongs to the
    C(/api/allowed/*) endpoints (planned as a dedicated module in v0.2).
  - Lists declared as Python lists are sent as repeated form fields
    (e.g. C(blockListUrls=a&blockListUrls=b)) which Technitium accepts.
    An empty list is sent as the literal string C(false), which Technitium
    treats as "clear all existing values" for list-typed settings.
options:
  settings:
    description:
      - Mapping of Technitium setting names to desired values. Keys must
        match the names used by C(/api/settings/{get,set}) verbatim (e.g.
        C(enableBlocking), C(blockListUrls), C(blockingType)).
      - Values may be scalars (str/int/bool) or lists of scalars. Pipe-
        separated structured settings such as C(tsigKeys) or
        C(qpmPrefixLimitsIPv4) must be passed as a pre-formatted string.
    type: dict
    required: true
seealso:
  - module: mipsou.technitium.blocklist
extends_documentation_fragment:
  - mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Enable DNSSEC validation and pin a forwarder
  mipsou.technitium.setting:
    session: "{{ tech.session }}"
    settings:
      dnssecValidation: true
      recursion: AllowOnlyForPrivateNetworks
      forwarders:
        - 1.1.1.1
        - 9.9.9.9

- name: Allow a single network to bypass blocking
  mipsou.technitium.setting:
    session: "{{ tech.session }}"
    settings:
      blockingBypassList:
        - 192.168.10.0/24
'''

RETURN = r'''
changed_settings:
  description: Mapping of changed keys to their before/after values.
  returned: success
  type: dict
settings:
  description: Full settings dict as reported by Technitium after the call.
  returned: success
  type: dict
'''

import ipaddress

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


# Setting keys whose value is documented as a list. We hold this list
# explicitly so we know to send them as repeated form fields (or the literal
# "false" when cleared) rather than as one scalar.
_LIST_SETTING_KEYS = frozenset([
    'dnsServerLocalEndPoints',
    'dnsServerIPv4SourceAddresses',
    'dnsServerIPv6SourceAddresses',
    'zoneTransferAllowedNetworks',
    'notifyAllowedNetworks',
    'socketPoolExcludedPorts',
    'qpmLimitBypassList',
    'webServiceLocalAddresses',
    'webServiceReverseProxyAddresses',
    'dnsReverseProxyNetworkACL',
    'recursionNetworkACL',
    'blockingBypassList',
    'customBlockingAddresses',
    'blockListUrls',
    'forwarders',
])


def _validate_blocking_bypass_list(values):
    """Raise ValueError on any entry that is not an IP or CIDR network.

    Technitium returns `Invalid network address was specified` with HTTP 200
    if a domain ends up in blockingBypassList. Fail loudly here instead.
    """
    bad = []
    for v in values:
        if v is None:
            continue
        try:
            ipaddress.ip_network(str(v), strict=False)
        except ValueError:
            bad.append(v)
    if bad:
        raise ValueError(
            'blockingBypassList accepts IP addresses or CIDR networks only; '
            'these entries are not valid: {0}. Domain allow-listing must use '
            'a dedicated allow-list (see /api/allowed/*).'.format(bad))


def _normalize(value):
    """Normalize values for diffing. Lists keep order; bools and ints are
    compared natively; strings are compared verbatim (no case folding)."""
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _diff_settings(current, declared):
    """Return {key: {'before': X, 'after': Y}} for keys whose declared value
    differs from current. Keys present in declared but absent from current are
    treated as changes."""
    out = {}
    for k, desired in declared.items():
        before = current.get(k)
        if _normalize(before) != _normalize(desired):
            out[k] = {'before': before, 'after': desired}
    return out


def _build_set_payload(changed):
    """Split a {key: value} dict into (scalars, lists) for TechnitiumClient.

    Empty lists become the literal string 'false' (clear all values), which
    is Technitium's documented convention for list-typed settings.
    """
    scalars = {}
    lists = {}
    for k, v in changed.items():
        if isinstance(v, list):
            if not v:
                scalars[k] = 'false'
            else:
                lists[k] = v
        elif isinstance(v, bool):
            scalars[k] = v
        elif v is None:
            scalars[k] = ''
        else:
            scalars[k] = v
    return scalars, lists


def main():
    spec = common_argument_spec()
    spec.update(dict(
        settings=dict(type='dict', required=True),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
    )

    declared = module.params['settings']
    if not declared:
        module.exit_json(changed=False, changed_settings={}, settings={})

    if 'blockingBypassList' in declared:
        try:
            _validate_blocking_bypass_list(declared['blockingBypassList'] or [])
        except ValueError as exc:
            module.fail_json(msg=str(exc))

    # Hint to the user when a key is declared as a scalar but matches the name
    # of a known list-typed setting — typical when migrating from a raw `uri`
    # task that used comma-separated strings. Wrap to a list ourselves so the
    # diff is comparable to the GET response.
    for k in list(declared):
        if k in _LIST_SETTING_KEYS and isinstance(declared[k], str):
            declared[k] = [s for s in declared[k].split(',') if s]

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        payload = client.get('/api/settings/get')
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to read settings: {0}'.format(exc),
            error_message=exc.error_message,
        )
    current = payload.get('response') or {}

    diff = _diff_settings(current, declared)
    if not diff:
        module.exit_json(changed=False, changed_settings={}, settings=current,
                         diff={'before': current, 'after': current})

    if module.check_mode:
        merged = dict(current)
        merged.update(declared)
        module.exit_json(changed=True, changed_settings=diff, settings=merged,
                         diff={'before': current, 'after': merged})

    scalars, lists = _build_set_payload({k: declared[k] for k in diff})
    try:
        post_payload = client.post('/api/settings/set', scalars=scalars, lists=lists)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to write settings: {0}'.format(exc),
            error_message=exc.error_message,
            attempted=list(diff.keys()),
        )
    updated = post_payload.get('response') or {}

    module.exit_json(
        changed=True,
        changed_settings=diff,
        settings=updated,
        diff={'before': current, 'after': updated},
    )


if __name__ == '__main__':
    main()
