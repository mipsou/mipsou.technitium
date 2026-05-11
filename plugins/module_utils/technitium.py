# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json as _json
from urllib.parse import urlencode

from ansible.module_utils.urls import fetch_url


COLLECTION_VERSION = '0.1.0'
USER_AGENT = 'ansible-mipsou.technitium/' + COLLECTION_VERSION


class TechnitiumError(Exception):
    """Raised when Technitium returns status != 'ok' or transport fails."""

    def __init__(self, message, status_code=None, error_message=None, path=None):
        super(TechnitiumError, self).__init__(message)
        self.status_code = status_code
        self.error_message = error_message
        self.path = path


def common_argument_spec():
    """Argument spec shared by all modules that talk to Technitium.

    Used either directly (the `session` module) or merged into the per-module
    spec when a module accepts a pre-built `session` dict from a previous
    `mipsou.technitium.session` task.
    """
    return dict(
        host=dict(type='str'),
        port=dict(type='int', default=5380),
        scheme=dict(type='str', choices=['http', 'https'], default='http'),
        validate_certs=dict(type='bool', default=True),
        timeout=dict(type='int', default=30),
        token=dict(type='str', no_log=True),
        session=dict(type='dict', no_log=True),
    )


class TechnitiumClient(object):
    """Thin HTTP client around the Technitium DNS Server API.

    Handles the three quirks that make raw `uri` painful:
    - status check on every call (errors come back as HTTP 200)
    - list params serialised as repeated form fields
    - token kept as a URL query parameter, not a header
    """

    def __init__(self, module, host, port=5380, scheme='http',
                 validate_certs=True, timeout=30, token=None):
        self.module = module
        self.host = host
        self.port = port
        self.scheme = scheme
        self.validate_certs = validate_certs
        self.timeout = timeout
        self.token = token

    @classmethod
    def from_module(cls, module):
        """Build a client from an AnsibleModule's params.

        Accepts either a `session` dict (output of `mipsou.technitium.session`)
        or the individual fields. The session dict wins if both are set.
        """
        params = module.params
        session = params.get('session') or {}
        host = session.get('host') or params.get('host')
        if not host:
            module.fail_json(msg="Either 'host' or a 'session' dict is required.")
        return cls(
            module=module,
            host=host,
            port=session.get('port') or params.get('port') or 5380,
            scheme=session.get('scheme') or params.get('scheme') or 'http',
            validate_certs=session.get('validate_certs')
                if session.get('validate_certs') is not None
                else params.get('validate_certs', True),
            timeout=session.get('timeout') or params.get('timeout') or 30,
            token=session.get('token') or params.get('token'),
        )

    def base_url(self):
        return '{0}://{1}:{2}'.format(self.scheme, self.host, self.port)

    def to_session(self):
        return dict(
            host=self.host,
            port=self.port,
            scheme=self.scheme,
            validate_certs=self.validate_certs,
            timeout=self.timeout,
            token=self.token,
        )

    def _build_body(self, scalars=None, lists=None):
        """Build a form-urlencoded body with repeated keys for list values.

        Technitium only accepts list parameters as repeated form fields, e.g.
        `blockListUrls=a&blockListUrls=b`. We flatten the inputs into a list
        of (key, value) pairs ourselves so a list-valued parameter becomes
        N pairs, then call urlencode on the already-flat pair list.
        """
        pairs = []
        if self.token:
            pairs.append(('token', self.token))
        if scalars:
            for k, v in scalars.items():
                if v is None:
                    continue
                if isinstance(v, bool):
                    v = 'true' if v else 'false'
                pairs.append((k, v))
        if lists:
            for k, values in lists.items():
                if values is None:
                    continue
                for v in values:
                    if v is None:
                        continue
                    pairs.append((k, v))
        return urlencode(pairs, doseq=False)

    def _request(self, path, scalars=None, lists=None, method='POST'):
        url = self.base_url() + path
        body = self._build_body(scalars=scalars, lists=lists)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        }

        # For GET, append the body as query string instead.
        request_url = url
        request_data = None
        if method.upper() == 'GET':
            sep = '&' if '?' in url else '?'
            request_url = url + (sep + body if body else '')
        else:
            request_data = body

        response, info = fetch_url(
            self.module,
            request_url,
            data=request_data,
            headers=headers,
            method=method,
            timeout=self.timeout,
        )

        status_code = info.get('status')
        if status_code is None or status_code >= 400 or status_code < 0:
            raise TechnitiumError(
                'HTTP error contacting Technitium at {0}: {1}'.format(
                    request_url, info.get('msg')),
                status_code=status_code,
                path=path,
            )

        raw = b''
        if response is not None:
            try:
                raw = response.read()
            finally:
                try:
                    response.close()
                except Exception:
                    pass

        if not raw:
            return {}

        try:
            payload = _json.loads(raw.decode('utf-8'))
        except ValueError as exc:
            raise TechnitiumError(
                'Invalid JSON from Technitium ({0}): {1}'.format(path, exc),
                status_code=status_code,
                path=path,
            )

        status = payload.get('status')
        if status != 'ok':
            raise TechnitiumError(
                'Technitium API error on {0}: {1}'.format(
                    path, payload.get('errorMessage') or status),
                status_code=status_code,
                error_message=payload.get('errorMessage'),
                path=path,
            )
        return payload

    def call(self, path, scalars=None, lists=None, method='POST'):
        return self._request(path, scalars=scalars, lists=lists, method=method)

    def get(self, path, scalars=None):
        return self._request(path, scalars=scalars, method='GET')

    def post(self, path, scalars=None, lists=None):
        return self._request(path, scalars=scalars, lists=lists, method='POST')

    def login(self, user, password, include_info=True):
        """Authenticate and store the resulting token on the client.

        Login must not send any prior token, so the current token is cleared
        before the call and restored only on failure.
        """
        scalars = {'user': user, 'pass': password}
        if include_info:
            scalars['includeInfo'] = 'true'
        saved_token = self.token
        self.token = None
        try:
            payload = self._request('/api/user/login', scalars=scalars, method='POST')
        except TechnitiumError:
            self.token = saved_token
            raise
        token = payload.get('token')
        if not token:
            self.token = saved_token
            raise TechnitiumError(
                'Login succeeded but no token returned by Technitium.',
                path='/api/user/login',
            )
        self.token = token
        return payload

    def logout(self):
        if not self.token:
            return None
        try:
            return self._request('/api/user/logout', method='POST')
        finally:
            self.token = None

    def change_password(self, current_password, new_password):
        """Rotate the password of the currently logged-in user.

        Technitium requires both `pass` (current) and `newPass`.
        """
        scalars = {'pass': current_password, 'newPass': new_password}
        return self._request('/api/user/changePassword', scalars=scalars, method='POST')


def is_zone_listed(client, prefix, name):
    """Return True iff `name` appears as a listed entry in /api/{prefix}/list.

    The /api/allowed/list and /api/blocked/list endpoints always echo back the
    queried domain, but only return an SOA/NS record on it when the domain has
    actually been added to the corresponding zone. We use the presence of an
    SOA or NS record exactly named `name` as the existence signal.
    """
    payload = client.get('/api/' + prefix + '/list', scalars={'domain': name})
    records = (payload.get('response') or {}).get('records') or []
    needle = name.rstrip('.').lower()
    for r in records:
        if (r.get('name', '').rstrip('.').lower() == needle
                and r.get('type') in ('SOA', 'NS')):
            return True
    return False
