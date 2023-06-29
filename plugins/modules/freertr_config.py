#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = ""
EXAMPLES = ""
RETURN = ""
from ansible.module_utils.basic import AnsibleModule
from ansible.utils.display import Display
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import get_config
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import freertr_argument_spec, check_args
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import load_config, run_commands
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.config import NetworkConfig, dumps


display = Display()


def get_candidate(module):
    candidate = NetworkConfig(indent=1)
    if module.params['src']:
        candidate.load(module.params['src'])
    elif module.params['lines']:
        parents = module.params['parents'] or list()
        commands = module.params['lines'][0]
        if (isinstance(commands, dict)) and (isinstance(commands['command'], list)):
            candidate.add(commands['command'], parents=parents)
        elif (isinstance(commands, dict)) and (isinstance(commands['command'], str)):
            candidate.add([commands['command']], parents=parents)
        else:
            candidate.add(module.params['lines'], parents=parents)
    return candidate


def get_running_config(module):
    contents = module.params['config']
    if not contents:
        contents = get_config(module)
    return contents


def main():
    backup_spec = dict(
        filename=dict(),
        dir_path=dict(type='path')
    )
    argument_spec = dict(
        lines=dict(aliases=['commands'], type='list'),
        parents=dict(type='list'),

        src=dict(type='path'),

        before=dict(type='list'),
        after=dict(type='list'),

        match=dict(default='line',
                   choices=['line', 'strict', 'exact', 'none']),
        replace=dict(default='line', choices=['line', 'block']),

        update=dict(choices=['merge', 'check'], default='merge'),
        save=dict(type='bool', default=False),
        config=dict(),
        backup=dict(type='bool', default=False),
        backup_options=dict(type='dict', options=backup_spec)
    )

    argument_spec.update(freertr_argument_spec)

    mutually_exclusive = [('lines', 'src'),
                          ('parents', 'src')]
    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    parents = module.params['parents'] or list()

    match = module.params['match']
    replace = module.params['replace']

    warnings = list()
    check_args(module, warnings)

    result = dict(changed=False, saved=False, warnings=warnings)

    candidate = get_candidate(module)

    if module.params['backup']:
        if not module.check_mode:
            result['__backup__'] = get_config(module)
    commands = list()

    if any((module.params['lines'], module.params['src'])):
        if match != 'none':
            config = get_running_config(module)
            config = NetworkConfig(contents=config, indent=1)
            configobjs = candidate.difference(config, match=match, replace=replace)
        else:
            configobjs = candidate.items

        if configobjs:
            commands = dumps(configobjs, 'commands')
            if ((isinstance(module.params['lines'], list)) and
                    (isinstance(module.params['lines'][0], dict)) and
                    set(['prompt', 'answer']).issubset(module.params['lines'][0])):

                cmd = {'command': commands,
                       'prompt': module.params['lines'][0]['prompt'],
                       'answer': module.params['lines'][0]['answer']}
                commands = [module.jsonify(cmd)]
            else:
                commands = commands.split('\n')

            if module.params['before']:
                commands[:0] = module.params['before']

            if module.params['after']:
                commands.extend(module.params['after'])

            if not module.check_mode and module.params['update'] == 'merge':
                load_config(module, commands)

            result['changed'] = True
            result['commands'] = commands
            result['updates'] = commands

    if module.params['save']:
        result['changed'] = True
        if not module.check_mode:
            cmd = {'command': 'copy running-config startup-config',
                   'prompt': r'\[confirm yes/no\]:\s?$', 'answer': 'yes'}
            run_commands(module, [cmd])
            result['saved'] = True
        else:
            module.warn('Skipping command `copy running-config startup-config`'
                        'due to check_mode.  Configuration not copied to '
                        'non-volatile storage')

    module.exit_json(**result)


if __name__ == '__main__':
    main()
