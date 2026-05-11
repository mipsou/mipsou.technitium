# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
name: record
author:
  - mipsou.technitium contributors
version_added: "0.1.0"
short_description: Look up DNS records from a Technitium DNS Server
description:
  - Queries C(/api/zones/records/get) for each domain name in I(terms) and
    returns matching records.
  - The lookup runs on the Ansible controller, so it needs a session token
    obtained beforehand by the C(mipsou.technitium.session) module (or any
    other way of producing the C(session) dict).
options:
  _terms:
    description: One or more fully-qualified domain names to look up.
    required: true
    type: list
    elements: str
  session:
    description:
      - Session dict produced by C(mipsou.technitium.session). Provides
        host, port, scheme, TLS settings and token.
      - Alternatively, set I(host), I(port), and I(token) explicitly.
    type: dict
  host:
    description: Technitium host (used when I(session) is not provided).
    type: str
  port:
    description: Technitium port (used when I(session) is not provided).
    type: int
    default: 5380
  scheme:
    description: URL scheme.
    type: str
    choices: [http, https]
    default: http
  validate_certs:
    description: Validate TLS certificates when I(scheme=https).
    type: bool
    default: true
  token:
    description: Technitium API token (used when I(session) is not provided).
    type: str
  zone:
    description: Authoritative zone hint, passed as the C(zone) query parameter.
    type: str
  type:
    description:
      - Optional record type filter. When set, only records of this type are
        returned.
    type: str
  default:
    description: Value to return when no record matches. When unset and no
      record matches, the lookup returns an empty list. Pass a string; the
      caller can post-process with C(| from_json) for structured defaults.
    type: str
'''

EXAMPLES = r'''
- name: Resolve every A record for host1
  ansible.builtin.debug:
    msg: "{{ lookup('mipsou.technitium.record', 'host1.example.lan',
                    type='A', session=tech.session, wantlist=True) }}"

- name: First IP of host1 as a scalar
  ansible.builtin.set_fact:
    host1_ip: "{{ (lookup('mipsou.technitium.record', 'host1.example.lan',
                          type='A', session=tech.session,
                          wantlist=True) | first).rData.ipAddress }}"
'''

RETURN = r'''
_raw:
  description: List of record dicts (C(name), C(type), C(ttl), C(rData)).
  type: list
  elements: dict
'''

import json
from urllib.parse import urlencode

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.module_utils.urls import open_url


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        session = self.get_option('session') or {}
        host = session.get('host') or self.get_option('host')
        if not host:
            raise AnsibleError("mipsou.technitium.record: 'session' or 'host' is required.")
        port = session.get('port') or self.get_option('port') or 5380
        scheme = session.get('scheme') or self.get_option('scheme') or 'http'
        validate_certs = session.get('validate_certs')
        if validate_certs is None:
            validate_certs = self.get_option('validate_certs')
            if validate_certs is None:
                validate_certs = True
        token = session.get('token') or self.get_option('token')
        if not token:
            raise AnsibleError("mipsou.technitium.record: a token is required "
                               "(set via 'session' or 'token').")

        zone = self.get_option('zone')
        type_filter = self.get_option('type')
        default = self.get_option('default')

        base = '{0}://{1}:{2}/api/zones/records/get'.format(scheme, host, port)

        results = []
        for term in terms:
            params = [('token', token), ('domain', term)]
            if zone:
                params.append(('zone', zone))
            url = base + '?' + urlencode(params)
            try:
                resp = open_url(url, method='GET',
                                validate_certs=bool(validate_certs),
                                timeout=30,
                                headers={'Accept': 'application/json'})
                payload = json.loads(resp.read().decode('utf-8'))
            except Exception as exc:
                raise AnsibleError(
                    "mipsou.technitium.record: HTTP error for {0!r}: {1}".format(term, exc))

            if payload.get('status') != 'ok':
                raise AnsibleError(
                    "mipsou.technitium.record: API error for {0!r}: {1}".format(
                        term, payload.get('errorMessage') or payload.get('status')))

            records = (payload.get('response') or {}).get('records') or []
            matched = []
            needle = term.rstrip('.').lower()
            for r in records:
                if r.get('name', '').rstrip('.').lower() != needle:
                    continue
                if type_filter and r.get('type') != type_filter:
                    continue
                matched.append(r)
            if not matched and default is not None:
                matched = [default]
            results.extend(matched)
        return results
