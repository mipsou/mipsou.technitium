# -*- coding: utf-8 -*-
# Copyright (c) 2026, mipsou.technitium contributors
# GNU General Public License v3.0+ (see LICENSE.GPL-3.0-or-later or
# https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class ModuleDocFragment(object):

    DOCUMENTATION = r'''
options:
  host:
    description:
      - Hostname or IP address of the Technitium DNS Server. Either I(host)
        or a I(session) dict is required.
    type: str
  port:
    description: TCP port of the Technitium web admin API.
    type: int
    default: 5380
  scheme:
    description: URL scheme used to reach the API.
    type: str
    choices: [http, https]
    default: http
  validate_certs:
    description: Whether to validate TLS certificates when I(scheme=https).
    type: bool
    default: true
  timeout:
    description: HTTP timeout in seconds for every API call.
    type: int
    default: 30
  token:
    description: Pre-existing API token (alternative to I(session)).
    type: str
  session:
    description:
      - Opaque session dict produced by the C(mipsou.technitium.session)
        module. When set, supersedes I(host)/I(port)/I(scheme)/I(token).
    type: dict
'''
