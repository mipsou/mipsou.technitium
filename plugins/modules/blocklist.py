#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: blocklist
short_description: Manage Technitium DNS blocklist URLs idempotently
version_added: "0.1.0"
description:
  - Manages C(blockListUrls) and the related C(enableBlocking) flag on a
    Technitium DNS Server through C(/api/settings/{get,set}).
  - This is a higher-level wrapper around C(setting) that also handles two
    blocklist-specific operations -- forcing a download via
    C(/api/settings/forceUpdateBlockLists), and waiting for the blocklist to
    be effectively active by probing DNS resolution.
  - The C(blockListLastUpdatedOn) settings field is not used as a readiness
    signal because Technitium often leaves it C(null) even when blocklists
    are loaded. Instead, set I(wait_for_active) to resolve a known-blocked
    domain and expect C(NXDOMAIN).
options:
  urls:
    description: Authoritative list of blocklist URLs. Replaces the existing
      value entirely. An empty list disables blocklist downloads.
    type: list
    elements: str
    required: true
  enabled:
    description: Whether C(enableBlocking) should be set on the server.
    type: bool
    default: true
  force_update:
    description:
      - When C(true), trigger C(/api/settings/forceUpdateBlockLists) at the
        end of the task even if I(urls) was unchanged.
      - When C(false) (the default), the force-update is only issued when
        the URL list changed in this run.
    type: bool
    default: false
  wait_for_active:
    description:
      - When set, repeatedly resolve I(probe_domain) against this Technitium
        server until the rcode matches I(expect_rcode) (or until the
        I(timeout) elapses). Use to detect that the blocklist is actually in
        force, since C(blockListLastUpdatedOn) is unreliable.
      - Uses a minimal stdlib UDP DNS probe -- no external dependency.
    type: dict
    suboptions:
      probe_domain:
        description: Domain to resolve. Should be a domain present in one of
          the configured blocklists.
        type: str
        required: true
      expect_rcode:
        description: Expected DNS response code.
        type: str
        choices: [NXDOMAIN, NOERROR, REFUSED, SERVFAIL]
        default: NXDOMAIN
      timeout:
        description: Total wait time in seconds.
        type: int
        default: 300
      interval:
        description: Delay in seconds between probe attempts.
        type: int
        default: 10
      qtype:
        description: DNS query type used by the probe.
        type: str
        default: A
seealso:
  - module: mipsou.technitium.setting
extends_documentation_fragment:
  - mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Set blocklist URLs, force a download, wait until active
  mipsou.technitium.blocklist:
    session: "{{ tech.session }}"
    urls:
      - https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
      - https://big.oisd.nl/
    enabled: true
    wait_for_active:
      probe_domain: doubleclick.net
      expect_rcode: NXDOMAIN
      timeout: 300
      interval: 10
'''

RETURN = r'''
urls:
  description: blockListUrls as reported by Technitium after the call.
  returned: success
  type: list
  elements: str
enabled:
  description: enableBlocking value after the call.
  returned: success
  type: bool
probe:
  description:
    - Result of the DNS readiness probe, when I(wait_for_active) was set.
    - C(rcode) is the final DNS response code observed. C(elapsed) is how
      long the probe loop ran for.
  returned: when wait_for_active is set
  type: dict
'''

import os
import socket
import struct
import time

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


# Minimal DNS probe -- we only need the response code, so a hand-rolled UDP
# query against the configured Technitium server is enough. Avoids pulling
# dnspython for what amounts to one struct.pack and one struct.unpack.

_QTYPES = {
    'A': 1, 'NS': 2, 'CNAME': 5, 'SOA': 6, 'PTR': 12,
    'MX': 15, 'TXT': 16, 'AAAA': 28, 'SRV': 33,
}

_RCODES = {
    0: 'NOERROR', 1: 'FORMERR', 2: 'SERVFAIL', 3: 'NXDOMAIN',
    4: 'NOTIMP', 5: 'REFUSED',
}


def _encode_qname(name):
    """Encode a domain name as a DNS wire-format QNAME (length-prefixed labels)."""
    out = bytearray()
    for label in name.strip('.').split('.'):
        if not label:
            continue
        encoded = label.encode('idna')
        if len(encoded) > 63:
            raise ValueError('DNS label too long: {0!r}'.format(label))
        out.append(len(encoded))
        out.extend(encoded)
    out.append(0)
    return bytes(out)


def _build_query(name, qtype_str):
    qtype = _QTYPES.get(qtype_str.upper(), 1)
    txid = int.from_bytes(os.urandom(2), 'big')
    flags = 0x0100  # standard query, recursion desired
    header = struct.pack('>HHHHHH', txid, flags, 1, 0, 0, 0)
    question = _encode_qname(name) + struct.pack('>HH', qtype, 1)  # class IN
    return txid, header + question


def _probe_once(server, port, name, qtype, lifetime):
    """Send one UDP DNS query and return the response code as a string."""
    try:
        txid, packet = _build_query(name, qtype)
    except ValueError:
        return 'ERROR'

    family = socket.AF_INET6 if ':' in server else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(max(0.5, float(lifetime)))
    try:
        sock.sendto(packet, (server, int(port) or 53))
        while True:
            data, _addr = sock.recvfrom(4096)
            if len(data) < 12:
                continue
            # Only accept responses matching our transaction id; ignore stray
            # packets that may have arrived on this ephemeral port.
            if struct.unpack('>H', data[:2])[0] != txid:
                continue
            rcode_bits = data[3] & 0x0F
            return _RCODES.get(rcode_bits, 'ERROR')
    except socket.timeout:
        return 'TIMEOUT'
    except OSError:
        return 'ERROR'
    finally:
        sock.close()


def _wait_for_rcode(server, dns_port, opts):
    expect = opts.get('expect_rcode', 'NXDOMAIN')
    deadline = time.time() + int(opts.get('timeout', 300))
    interval = int(opts.get('interval', 10))
    last_rcode = None
    while time.time() < deadline:
        last_rcode = _probe_once(server, dns_port, opts['probe_domain'],
                                 opts.get('qtype', 'A'),
                                 max(2, min(interval, 5)))
        if last_rcode == expect:
            return last_rcode, True
        time.sleep(interval)
    return last_rcode, False


def main():
    spec = common_argument_spec()
    spec.update(dict(
        urls=dict(type='list', elements='str', required=True),
        enabled=dict(type='bool', default=True),
        force_update=dict(type='bool', default=False),
        wait_for_active=dict(type='dict', options=dict(
            probe_domain=dict(type='str', required=True),
            expect_rcode=dict(type='str', default='NXDOMAIN',
                              choices=['NXDOMAIN', 'NOERROR', 'REFUSED', 'SERVFAIL']),
            timeout=dict(type='int', default=300),
            interval=dict(type='int', default=10),
            qtype=dict(type='str', default='A'),
            dns_port=dict(type='int', default=53),
        )),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
    )

    p = module.params
    desired_urls = list(p['urls'] or [])
    desired_enabled = bool(p['enabled'])
    wait_opts = p.get('wait_for_active')

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
    current_urls = list(current.get('blockListUrls') or [])
    current_enabled = bool(current.get('enableBlocking'))

    urls_changed = current_urls != desired_urls
    enabled_changed = current_enabled != desired_enabled
    settings_changed = urls_changed or enabled_changed

    diff_before = {'blockListUrls': current_urls, 'enableBlocking': current_enabled}
    diff_after = {'blockListUrls': desired_urls, 'enableBlocking': desired_enabled}

    will_force = settings_changed or p['force_update']
    will_wait = bool(wait_opts) and will_force

    if module.check_mode:
        module.exit_json(
            changed=settings_changed or p['force_update'],
            urls=desired_urls,
            enabled=desired_enabled,
            diff={'before': diff_before, 'after': diff_after},
        )

    if settings_changed:
        scalars = {}
        lists = {}
        if enabled_changed:
            scalars['enableBlocking'] = desired_enabled
        if urls_changed:
            if desired_urls:
                lists['blockListUrls'] = desired_urls
            else:
                scalars['blockListUrls'] = 'false'
        try:
            client.post('/api/settings/set', scalars=scalars, lists=lists)
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to update blocklist settings: {0}'.format(exc),
                error_message=exc.error_message,
            )

    if will_force:
        try:
            client.get('/api/settings/forceUpdateBlockLists')
        except TechnitiumError as exc:
            module.fail_json(
                msg='blockListUrls were saved but forceUpdateBlockLists failed: '
                    '{0}'.format(exc),
                error_message=exc.error_message,
            )

    result = dict(
        changed=settings_changed or p['force_update'],
        urls=desired_urls,
        enabled=desired_enabled,
        diff={'before': diff_before, 'after': diff_after},
    )

    if will_wait:
        start = time.time()
        rcode, ok = _wait_for_rcode(client.host,
                                    wait_opts.get('dns_port', 53),
                                    wait_opts)
        result['probe'] = dict(
            rcode=rcode,
            expected=wait_opts.get('expect_rcode', 'NXDOMAIN'),
            ok=ok,
            elapsed=int(time.time() - start),
        )
        if not ok:
            module.fail_json(
                msg='Blocklist did not become active within {0}s '
                    '(probe {1!r} returned {2!r}, expected {3!r}).'.format(
                        wait_opts.get('timeout', 300),
                        wait_opts['probe_domain'],
                        rcode,
                        wait_opts.get('expect_rcode', 'NXDOMAIN')),
                **result)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
