#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# Licensed under the EUPL-1.2 (see LICENSE)
# SPDX-License-Identifier: EUPL-1.2

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app
short_description: Manage Technitium DNS Apps from the App Store idempotently
version_added: "0.2.0"
description:
  - Installs, updates, removes or reconfigures DNS Apps on a Technitium DNS Server
    through
    C(/api/apps/{list,listStoreApps,downloadAndInstall,downloadAndUpdate,uninstall,config/get,config/set}).
  - With I(state=present) the app is installed if missing; any installed
    version is accepted as up-to-date (no pull from the store on re-runs).
  - With I(state=latest) the installed version is compared with the current
    store version and updated when they differ. Use this when you want
    auto-tracking of upstream releases.
  - When I(config) is set, the current app configuration is fetched, diffed
    against the desired dict and pushed only on difference. The configuration
    schema is app-specific and is forwarded as-is — Technitium validates
    server-side.
options:
  name:
    description: DNS App name as displayed in Technitium (exact, case-sensitive).
    type: str
    required: true
  state:
    description:
      - C(present) ensures the app is installed (any version).
      - C(latest) ensures the installed version matches the current store version.
      - C(absent) uninstalls the app.
    type: str
    choices: [present, latest, absent]
    default: present
  url:
    description:
      - Explicit store URL for the app installer ZIP. When unset, the URL is
        resolved automatically from C(/api/apps/listStoreApps).
      - Provide this when installing an app that is not in the store
        (e.g. a custom in-house app from a private repository).
    type: str
  config:
    description:
      - Desired app configuration as a dict. Forwarded as a JSON string to
        C(/api/apps/config/set). Only effective with I(state=present) or
        I(state=latest).
      - Omit to leave the configuration untouched.
    type: dict
extends_documentation_fragment:
  - mipsou.technitium.session
author:
  - mipsou (@mipsou)
'''

EXAMPLES = r'''
- name: Install Query Logs (Sqlite) at latest store version
  mipsou.technitium.app:
    session: "{{ tech.session }}"
    name: "Query Logs (Sqlite)"
    state: latest
    config:
      enableLogging: true
      maxLogDays: 30
      maxLogFileSizeBytes: 1073741824

- name: Install DNS over TLS Forwarder with explicit upstream
  mipsou.technitium.app:
    session: "{{ tech.session }}"
    name: "DNS over TLS Forwarder"
    state: present
    config:
      forwarders:
        - "tls://1.1.1.1"
        - "tls://9.9.9.9"

- name: Remove a deprecated app
  mipsou.technitium.app:
    session: "{{ tech.session }}"
    name: "Advanced Blocking App"
    state: absent

- name: Install an out-of-store community DNS App (LANCache for game CDN caching)
  mipsou.technitium.app:
    session: "{{ tech.session }}"
    name: "LAN Cache"
    state: present
    # Apps not listed in /api/apps/listStoreApps require an explicit installer
    # ZIP URL — community example: ruifung/LANCache-TDNSApp.
    url: "https://github.com/ruifung/LANCache-TDNSApp/releases/latest/download/LANCache-TDNSApp.zip"
'''

RETURN = r'''
app:
  description:
    - App attributes as reported by Technitium, or C(null) when state=absent.
    - Includes C(name), C(version), C(details) and the C(dnsApps) sub-list
      when applicable.
  returned: success
  type: dict
installed_version:
  description: Version installed after the call.
  returned: when state in (present, latest)
  type: str
store_version:
  description:
    - Latest version offered by the App Store at the time of the call.
    - Useful with state=latest to confirm what the update target was.
  returned: when the app appears in /api/apps/listStoreApps
  type: str
config_changed:
  description: Whether the app config was pushed in this run.
  returned: when I(config) was supplied
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.mipsou.technitium.plugins.module_utils.technitium import (
    TechnitiumClient,
    TechnitiumError,
    common_argument_spec,
)


def _list_installed(client):
    """Return list of installed app dicts as reported by /api/apps/list."""
    payload = client.get('/api/apps/list')
    return (payload.get('response') or {}).get('apps') or []


def _list_store(client):
    """Return list of store app dicts as reported by /api/apps/listStoreApps."""
    payload = client.get('/api/apps/listStoreApps')
    return (payload.get('response') or {}).get('storeApps') or []


def _find_named(apps, name):
    """Find an app by exact name in a list; return the dict or None."""
    for app in apps:
        if app.get('name') == name:
            return app
    return None


def _get_config(client, name):
    """Read the current app config as a dict.

    Technitium returns the config as a JSON-encoded string under
    C(response.config). We parse it back to a dict for diffing. An app
    that has never been configured returns an empty string, which we map
    to an empty dict so diffing against a desired config works cleanly.
    """
    payload = client.get('/api/apps/config/get', scalars={'name': name})
    raw = (payload.get('response') or {}).get('config')
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # Non-JSON config (rare, app-specific) — diff opaque so we still
        # detect changes via raw string comparison.
        return {'_raw': raw}


def _set_config(client, name, config_dict):
    """Push a config dict to /api/apps/config/set, serialised as JSON."""
    body = json.dumps(config_dict, separators=(',', ':'), sort_keys=True)
    return client.post('/api/apps/config/set',
                       scalars={'name': name, 'config': body})


def main():
    spec = common_argument_spec()
    spec.update(dict(
        name=dict(type='str', required=True),
        state=dict(type='str', choices=['present', 'latest', 'absent'],
                   default='present'),
        url=dict(type='str'),
        config=dict(type='dict'),
    ))

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True,
    )

    p = module.params
    name = p['name']
    desired_state = p['state']
    explicit_url = p.get('url')
    desired_config = p.get('config')

    client = TechnitiumClient.from_module(module)
    if not client.token:
        module.fail_json(msg='No token in session — call mipsou.technitium.session first.')

    try:
        installed = _find_named(_list_installed(client), name)
    except TechnitiumError as exc:
        module.fail_json(
            msg='Failed to list installed apps: {0}'.format(exc),
            error_message=exc.error_message,
        )

    # ── state: absent ────────────────────────────────────────────────────────
    if desired_state == 'absent':
        if installed is None:
            module.exit_json(changed=False, app=None,
                             diff={'before': None, 'after': None})
        if module.check_mode:
            module.exit_json(changed=True, app=None,
                             diff={'before': installed, 'after': None})
        try:
            client.post('/api/apps/uninstall', scalars={'name': name})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to uninstall {0!r}: {1}'.format(name, exc),
                error_message=exc.error_message,
            )
        module.exit_json(changed=True, app=None,
                         diff={'before': installed, 'after': None})

    # ── state: present | latest ──────────────────────────────────────────────
    store_entry = None
    # Auto-resolve from /api/apps/listStoreApps unless caller provided a URL.
    # We tolerate not finding the app there — only fail later if we actually
    # need a URL (fresh install or `latest` update).
    if explicit_url is None:
        try:
            store_entry = _find_named(_list_store(client), name)
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to list store apps: {0}'.format(exc),
                error_message=exc.error_message,
            )

    install_url = explicit_url or (store_entry or {}).get('url')
    store_version = (store_entry or {}).get('version')

    install_needed = installed is None
    update_needed = (
        desired_state == 'latest'
        and installed is not None
        and store_version is not None
        and installed.get('version') != store_version
    )

    if install_needed and not install_url:
        module.fail_json(
            msg='App {0!r} not found in store and no explicit url= given.'.format(name),
        )
    if update_needed and not install_url:
        module.fail_json(
            msg='App {0!r} update requested but no URL available '
                '(absent from store and no explicit url=).'.format(name),
        )

    install_action = None
    if install_needed:
        install_action = ('downloadAndInstall', install_url)
    elif update_needed:
        install_action = ('downloadAndUpdate', install_url)

    # ── config diff (only computed if app will be installed or already is) ───
    config_changed = False
    current_config = None
    if desired_config is not None and (installed is not None or install_action):
        if installed is None:
            # About to install — current config is by definition empty.
            current_config = {}
        else:
            try:
                current_config = _get_config(client, name)
            except TechnitiumError as exc:
                msg = (exc.error_message or str(exc) or '').lower()
                if any(k in msg for k in ('no config', 'not found', 'does not exist')):
                    current_config = {}
                else:
                    module.fail_json(
                        msg='Failed to read config for {0!r}: {1}'.format(name, exc),
                        error_message=exc.error_message,
                    )
        config_changed = current_config != desired_config

    overall_changed = bool(install_action) or config_changed

    if module.check_mode:
        projected = installed or {'name': name}
        if install_action:
            projected = dict(projected,
                             version=store_version or projected.get('version'))
        result = dict(
            changed=overall_changed,
            app=projected,
            installed_version=projected.get('version'),
            diff={'before': installed, 'after': projected},
        )
        if store_version:
            result['store_version'] = store_version
        if desired_config is not None:
            result['config_changed'] = config_changed
        module.exit_json(**result)

    # ── install or update ────────────────────────────────────────────────────
    if install_action:
        endpoint, url = install_action
        try:
            client.post('/api/apps/' + endpoint,
                        scalars={'name': name, 'url': url})
        except TechnitiumError as exc:
            module.fail_json(
                msg='Failed to {0} app {1!r}: {2}'.format(endpoint, name, exc),
                error_message=exc.error_message,
            )
        try:
            installed = _find_named(_list_installed(client), name)
        except TechnitiumError:
            installed = installed or {'name': name, 'version': store_version}

    # ── push config if different ─────────────────────────────────────────────
    if config_changed:
        try:
            _set_config(client, name, desired_config)
        except TechnitiumError as exc:
            module.fail_json(
                msg='App installed/updated but config push failed for {0!r}: {1}'.format(
                    name, exc),
                error_message=exc.error_message,
            )

    result = dict(
        changed=overall_changed,
        app=installed,
        installed_version=(installed or {}).get('version'),
        diff={'before': None if install_needed else installed, 'after': installed},
    )
    if store_version:
        result['store_version'] = store_version
    if desired_config is not None:
        result['config_changed'] = config_changed
    module.exit_json(**result)


if __name__ == '__main__':
    main()
