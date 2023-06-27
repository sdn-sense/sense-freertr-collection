#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import time
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import string_types
from ansible.utils.display import Display
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import run_commands
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import freertr_argument_spec, check_args
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import ComplexList
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.parsing import Conditional

display = Display()

def toLines(stdout):
    for item in stdout:
        if isinstance(item, string_types):
            item = str(item).split('\n')
        yield item


def parse_commands(module, warnings):
    command = ComplexList({'command': {'key':True}, 'prompt': {}, 'answer':{}}, module)
    commands = command(module.params['commands'])
    for _index, item in enumerate(commands):
        if module.check_mode and not item['command'].startswith('show'):
            warnings.append('only show commands are supported when using check mode, not executing `%s`' % item['command'])
        elif item['command'].startswith('conf'):
            module.fail_json(msg='freertr_command does not support running config mode commands.  Please use freertr_config instead')
    return commands


def main():
    """main entry point for module execution
    """

    argument_spec = {
        'commands': {'type': 'list', 'required':True},
        'wait_for': {'type':'list', 'elements': 'str'},
        'match': {'default':'all', 'choices': ['all', 'any']},
        'retries': {'default':10, 'type': 'int'},
        'interval': {'default': 1, 'type': 'int'}}

    argument_spec.update(freertr_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    result = {'changed': False}

    warnings = []
    check_args(module, warnings)
    commands = parse_commands(module, warnings)
    result['warnings'] = warnings

    wait_for = module.params['wait_for'] or []
    conditionals = [Conditional(c) for c in wait_for]

    retries = module.params['retries']
    interval = module.params['interval']
    match = module.params['match']

    while retries > 0:
        responses = run_commands(module, commands)

        for item in conditionals:
            if item(responses):
                if match == 'any':
                    conditionals = []
                    break
                conditionals.remove(item)

        if not conditionals:
            break

        time.sleep(interval)
        retries -= 1

    if conditionals:
        failed_conditions = [item.raw for item in conditionals]
        msg = 'One or more conditional statements have not been satisfied'
        module.fail_json(msg=msg, failed_conditions=failed_conditions)

    result.update({
        'changed': False,
        'stdout': responses,
        'stdout_lines': list(toLines(responses))
    })

    module.exit_json(**result)


if __name__ == '__main__':
    main()
