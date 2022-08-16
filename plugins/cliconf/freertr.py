#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import re
import json

from ansible.module_utils._text import to_text
from ansible.plugins.cliconf import CliconfBase, enable_mode
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import to_list

class Cliconf(CliconfBase):

    def get_device_info(self):
        """Get Device Info"""
        devInfo = {}

        devInfo['network_os'] = 'rare.freertr.freertr'
        reply = self.get('show platform')
        data = to_text(reply, errors='surrogate_or_strict').strip()

        match = re.search(r'freeRouter (\S+),', data)
        if match:
            devInfo['network_os_version'] = match.group(1)
        match = re.search(r'hwid: (\S+)', data, re.M)
        if match:
            devInfo['network_os_hwid'] = match.group(1)
        match = re.search(r'name: (\S+)', data, re.M)
        if match:
            devInfo['network_os_hostname'] = match.group(1)
        return devInfo

    @enable_mode
    def get_config(self, source='running', flags=None, format='text'):
        """Get Config"""
        if source not in ['running', 'startup']:
            return self.invalid_params("fetching configuration from %s is not supported" % source)
        if source == 'running':
            cmd = 'show running-config all'
        else:
            cmd = 'show startup-config'
        return self.send_command(cmd)

    @enable_mode
    def edit_config(self, command):
        """Edit Configuration"""
        for cmd in ['configure terminal'] + to_list(command) + ['end']:
            self.send_command(cmd)

    def get(self, command, prompt=None, answer=None, sendonly=False, newline=True, check_all=False):
        """Get command output"""
        return self.send_command(command=command, prompt=prompt, answer=answer,
                                 sendonly=sendonly, newline=newline, check_all=check_all)

    def get_capabilities(self):
        """Get capabilities"""
        result = super(Cliconf, self).get_capabilities()
        return json.dumps(result)
