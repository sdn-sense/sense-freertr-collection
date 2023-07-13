#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__metaclass__ = type

import json

from unittest.mock import *
from ansible_collections.sense.freertr.tests.unit.modules.freertr_module import TestFreeRTRModule, load_fixture
from ansible_collections.sense.freertr.tests.unit.modules.freertr_module import set_module_args
from ansible_collections.sense.freertr.plugins.modules import freertr_facts


class TestFreeRTRFacts(TestFreeRTRModule):

    module = freertr_facts

    def setUp(self):
        super(TestFreeRTRFacts, self).setUp()

        self.mock_run_command = patch(
            'ansible_collections.sense.freertr.plugins.modules.freertr_facts.run_commands')
        self.run_commands = self.mock_run_command.start()

    def tearDown(self):
        super(TestFreeRTRFacts, self).tearDown()

        self.mock_run_command.stop()

    def load_fixtures(self, commands=None):

        def load_from_file(*args, **kwargs):
            module, commands = args
            output = list()

            for item in commands:
                try:
                    obj = json.loads(item)
                    command = obj['command']
                except ValueError:
                    command = item
                if '|' in command:
                    command = str(command).replace('|', '')
                filename = str(command).replace(' ', '_')
                filename = filename.replace('/', '7')
                output.append(load_fixture(filename))
            return output

        self.run_commands.side_effect = load_from_file

    def test_freertr_facts_gather_subset_default(self):
        set_module_args(dict())
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertEquals('rare', ansible_facts['ansible_net_hostname'])
        self.assertEquals('accton_as9516_32d', ansible_facts['ansible_net_hwid'])
        self.assertEquals('v23.4.21-cur', ansible_facts['ansible_net_version'])

    def test_freertr_facts_gather_subset_hardware(self):
        set_module_args({'gather_subset': 'hardware'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertEquals("100m", ansible_facts['ansible_net_memfree_mb'])
        self.assertEquals("2147m", ansible_facts['ansible_net_memtotal_mb'])
        self.assertEquals("306m", ansible_facts['ansible_net_memused_mb'])

    def test_freertr_facts_gather_subset_config(self):
        set_module_args({'gather_subset': 'config'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_config', ansible_facts)

    def test_freertr_facts_gather_subset_interfaces(self):
        set_module_args({'gather_subset': 'interfaces'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_interfaces', ansible_facts)
        self.assertIn('ethernet1', ansible_facts['ansible_net_interfaces'])
        self.assertEquals("out of band management port", ansible_facts['ansible_net_interfaces']['ethernet1']['description'])
        self.assertEquals("172.16.1.225/23", ansible_facts['ansible_net_interfaces']['ethernet1']['ipv4'])
        self.assertEquals("fe80::201:bff:fead:c0de/64", ansible_facts['ansible_net_interfaces']['ethernet1']['ipv6'])
        self.assertEquals("00:01:0b:ad:c0:de", ansible_facts['ansible_net_interfaces']['ethernet1']['mac'])
        self.assertEquals(1500, ansible_facts['ansible_net_interfaces']['ethernet1']['mtu'])
        self.assertEquals(100, ansible_facts['ansible_net_interfaces']['ethernet1']['speed'])
        self.assertEquals("ethernet", ansible_facts['ansible_net_interfaces']['ethernet1']['type'])
        self.assertEquals("up", ansible_facts['ansible_net_interfaces']['ethernet1']['state'])
        self.assertEquals("oob", ansible_facts['ansible_net_interfaces']['ethernet1']['vrf'])
        self.assertIn('ansible_net_neighbors', ansible_facts)
        self.assertIn("sdn12000", ansible_facts['ansible_net_lldp'])
        self.assertIn("local_port_id", ansible_facts['ansible_net_lldp']['sdn12000'])
        self.assertEquals("sdn12000", ansible_facts['ansible_net_lldp']['sdn12000']['local_port_id'])
        self.assertIn("remote_chassis_id", ansible_facts['ansible_net_lldp']['sdn12000'])
        self.assertEquals("b8:59:9f:ed:29:8e", ansible_facts['ansible_net_lldp']['sdn12000']['remote_chassis_id'])
        self.assertIn("remote_port_id", ansible_facts['ansible_net_lldp']['sdn12000'])
        self.assertEquals("b859.9fed.298e", ansible_facts['ansible_net_lldp']['sdn12000']['remote_port_id'])
        self.assertIn("remote_system_name", ansible_facts['ansible_net_lldp']['sdn12000'])
        self.assertEquals("sdn-sc-05.ultra.org", ansible_facts['ansible_net_lldp']['sdn12000']['remote_system_name'])

        self.assertIn('ansible_net_all_ipv4_addresses', ansible_facts)
        self.assertIn('172.16.1.225/255.255.254.0', ansible_facts['ansible_net_all_ipv4_addresses'])
        self.assertIn('ansible_net_all_ipv6_addresses', ansible_facts)
        self.assertIn('fe80::201:bff:fead:c0de/ffff:ffff:ffff:ffff::', ansible_facts['ansible_net_all_ipv6_addresses'])

    def test_freertr_facts_gather_subset_routing(self):
        set_module_args({'gather_subset': 'routing'})
        result = self.execute_module()
        ansible_facts = result['ansible_facts']
        self.assertIn('ansible_net_routing', ansible_facts)
        self.assertIn("ipv4", ansible_facts['ansible_net_routing'])
        self.assertIn("ipv6", ansible_facts['ansible_net_routing'])
