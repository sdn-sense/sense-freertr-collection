#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import sys
import copy

from ansible import constants as C
from ansible.utils.display import Display
from ansible.module_utils._text import to_text
from ansible.module_utils.connection import Connection
from ansible_collections.ansible.netcommon.plugins.action.network import ActionModule as ActionNetworkModule
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import load_provider
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import freertr_provider_spec

display = Display()


class ActionModule(ActionNetworkModule):
    """ Ansible Action Module"""

    def run(self, tmp=None, task_vars=None):
        """FreeRTR Ansible Run"""

        self._config_module = self._task.action.split('.')[-1] == 'freertr_config'
        sockPath = None
        persConn = self._play_context.connection.split('.')[-1]

        if persConn == 'network_cli':
            provider = self._task.args.get('provider', {})
            if provider.values():
                display.warning('provider is unnecessary when using network_cli and will be ignored')
                del self._task.args['provider']
        elif self._play_context.connection == 'local':
            provider = load_provider(freertr_provider_spec, self._task.args)
            plc = copy.deepcopy(self._play_context)
            plc.connection = 'network_cli'
            plc.network_os = 'sense.freertr.freertr'
            plc.remote_addr = provider['host'] or self._play_context.remote_addr
            plc.port = int(provider['port'] or self._play_context.port or 22)
            plc.remote_user = provider['username'] or self._play_context.connection_user
            plc.password = provider['password'] or self._play_context.password
            plc.private_key_file = provider['ssh_keyfile'] or self._play_context.private_key_file
            command_timeout = int(provider['timeout'] or C.PERSISTENT_COMMAND_TIMEOUT)
            plc.become = provider['authorize'] or False
            if plc.become:
                plc.become_method = 'enable'
            plc.become_pass = provider['auth_pass']

            display.vvv('using connection plugin %s' % plc.connection, plc.remote_addr)
            connection = self._shared_loader_obj.connection_loader.get('persistent', plc, sys.stdin)
            connection.set_options(direct={'persistent_command_timeout': command_timeout})

            sockPath = connection.run()
            display.vvvv('socket_path: %s' % sockPath, plc.remote_addr)
            if not sockPath:
                return {'failed': True,
                        'msg': 'unable to open shell. Please see: https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell'}

            task_vars['ansible_socket'] = sockPath

        if not sockPath:
            sockPath = self._connection.socket_path

        conn = Connection(sockPath)
        out = conn.get_prompt()
        while to_text(out, errors='surrogate_then_replace').strip().endswith(')#'):
            display.vvvv('wrong context, send exit...', self._play_context.remote_addr)
            conn.send_command('exit')
            out = conn.get_prompt()

        result = super(ActionModule, self).run(task_vars=task_vars)
        return result
