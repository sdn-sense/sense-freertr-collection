#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.utils.display import Display
from ansible_collections.rare.freertr.plugins.module_utils.network.freertr import run_commands
from ansible_collections.rare.freertr.plugins.module_utils.network.freertr import freertr_argument_spec, check_args

display = Display()

class FactsBase():
    """Base class for Facts"""

    COMMANDS = []

    def __init__(self, module):
        self.module = module
        self.facts = {}
        self.responses = None

    def populate(self):
        """Populate responses"""
        self.responses = run_commands(self.module, self.COMMANDS, check_rc=False)

    def run(self, cmd):
        """Run commands"""
        return run_commands(self.module, cmd, check_rc=False)


class Default(FactsBase):
    """Default Class to get basic info"""
    COMMANDS = [
        'show platform',
    ]

    def populate(self):
        super(Default, self).populate()
        data = self.responses[0]
        self.facts['version'] = self.parse_version(data)
        self.facts['hwid'] = self.parse_hwid(data)
        self.facts['hostname'] = self.parse_hostname(data)

    @staticmethod
    def parse_version(data):
        """Parse version"""
        match = re.search(r'freeRouter (\S+),', data)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def parse_hostname(data):
        """Parse Hostname"""
        match = re.search(r'name: (\S+)', data, re.M)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def parse_hwid(data):
        """Parse HWID"""
        match = re.search(r'hwid: (\S+)', data)
        if match:
            return match.group(1)
        return ""


class Hardware(FactsBase):
    """Hardware Information Class"""
    COMMANDS = [
        'show platform',
    ]

    def populate(self):
        super(Hardware, self).populate()
        data = self.responses[0]
        match= re.search(r'^mem: \S+=(\S+), \S+=(\S+), \S+=(\S+)', data, re.M)
        if match:
            self.facts['memfree_mb'] = match[1]
            self.facts['memtotal_mb'] = match[2]
            self.facts['memused_mb'] = match[3]
        # cpu: 16*amd64


class Config(FactsBase):
    """Configuration info Class"""
    COMMANDS = ['show running-config']

    def populate(self):
        super(Config, self).populate()
        self.facts['config'] = self.responses[0]


class Interfaces(FactsBase):
    """All Interfaces Class"""
    COMMANDS = ['show interfaces',
                'show ipv4 interface',
                'show ipv6 interface',
                'show lldp neighbor']

    def populate(self):
        super(Interfaces, self).populate()

        self.facts['interfaces'] = {}
        interfaceData = self.parseInterfaces(self.responses[0])
        for intfName, intfDict in interfaceData.items():
            tmpD = self.facts['interfaces'].setdefault(intfName, {})
            tmpD['state'] = intfDict['state']
            unpLines = "\n".join(intfDict['unparsed'])
            tmpD['description'] = self.parseDesc(unpLines)
            tmpD['type'] = self.parseType(unpLines)
            tmpD['hwaddr'] = self.parseHwaddr(unpLines)
            tmpD['mtu'] = self.parseMTU(unpLines)
            tmpD['bw'] = self.parseBW(unpLines)
            tmpD['vrf'] = self.parseVrf(unpLines)
            # TODO: It could be multiple IPs. Need to test and identify that
            tmpD['ipv4'] = self.parseIpv4(unpLines)
            tmpD['ipv6'] = self.parseIpv6(unpLines)

        self.facts['all_ipv4_addresses'] = self.populateIPv4Addresses(self.responses[1])
        self.facts['all_ipv6_addresses'] = self.populateIPv4Addresses(self.responses[2])

        self.facts['neighbors'] = self.populateLLDPInfo(self.responses[3])

    def populateLLDPInfo(self, data):
        """Get all lldp information"""
        out = {}
        for line in data.split('\n'):
            splLine = list(filter(None, line.split(' ')))
            if len(splLine) >= 5:
                if splLine[0] == 'interface':
                    # Ignore first line
                    continue
                tmpD = out.setdefault(splLine[0], [])
                tmpD.append(self.getLLDPIntfInfo(splLine))
        return out

    def getLLDPIntfInfo(self, splLine):
        """Get lldp info of specific interface"""
        out = {'remote_system_name': splLine[1], 'local_port_id': splLine[0]}
        lldpInfo = self.run(["show lldp detail %s" % splLine[0]])
        for line in lldpInfo[0].split('\n'):
            if not line:
                continue
            match = re.search(r'peer *(\S+)$', line, re.M)
            if match:
                out['remote_chassis_id'] = match.group(1).strip().replace('.', '')
            match = re.search(r'port id *([^$]*)$', line, re.M)
            if match:
                out['remote_port_id'] = match.group(1).strip()
        return out

    @staticmethod
    def populateIPv6Addresses(data):
        """Get all IPv6 address info"""
        out = []
        for line in data.split('\n'):
            splLine = list(filter(None, line.split(' ')))
            if len(splLine) == 4:
                if splLine[0] == 'interface':
                    # Ignore first line
                    continue
                out.append('%s/%s' % (splLine[2], splLine[3]))
        return out

    @staticmethod
    def populateIPv4Addresses(data):
        """Get all IPv4 address info"""
        out = []
        for line in data.split('\n'):
            splLine = list(filter(None, line.split(' ')))
            if len(splLine) == 4:
                if splLine[0] == 'interface':
                    continue
                out.append('%s/%s' % (splLine[2], splLine[3]))
        return out


    @staticmethod
    def parseIpv6(data):
        """Parse IPv6 address from output"""
        #  ipv6 address=fd00:67:7e69::a:8:e:2/120, mask=ffff:ffff:ffff:ffff:ffff:ffff:ffff:ff00, ifcid=325883999
        match = re.search(r'ipv6 address=([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseIpv4(data):
        """Parse IPv4 address from output"""
        #  ipv4 address=10.8.14.2/24, mask=255.255.255.0, ifcid=684917826
        match = re.search(r'ipv4 address=([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseVrf(data):
        """Parse vrf from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'vrf=([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseBW(data):
        """Parse bw from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'bw=([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseMTU(data):
        """Parse mtu from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'mtu=([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseHwaddr(data):
        """Parse hwaddr from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'hwaddr=([^ ,]*)', data, re.M)
        if match and match.group(1).strip() != 'none':
            return match.group(1).strip().replace('.', '')
        return ""

    @staticmethod
    def parseType(data):
        """Parse intf type from output"""
        # #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'type is ([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseDesc(data):
        """Parse description from output"""
        match = re.search(r'description: (.+)$', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseInterfaces(data):
        """Parse interfaces from output"""
        parsed = {}
        intName = ""

        for line in data.split('\n'):
            if line:
                if line.startswith(' '):
                    parsed[intName]['unparsed'].append(line)
                else:
                    match = re.match(r'^(\S+) is (\S+)$', line)
                    if match:
                        intName = match[1]
                        parsed.setdefault(intName, {'state': match[2], 'unparsed': []})
        return parsed


# Add New Class for Routing:
        # 4 and 5 gives:
# BUR0051#show vrf routing
#                     ifc     uni     mlt     flw     lab     con
# name      rd        v4  v6  v4  v6  v4  v6  v4  v6  v4  v6  v4  v6
# CORE      0:0       12  5   33  20  33  20  0   0   0   0   10  5
# INB_MGNT  20965:14  1   0   1   0   1   0   0   0   0   0   1   0
# lin       0:0       1   0   2   0   2   0   0   0   0   0   1   0
# oob       0:0       1   1   4   2   4   2   0   0   0   0   2   1
# p4        0:0       0   0   0   0   0   0   0   0   0   0   0   0
# v1        0:0       1   0   2   0   2   0   0   0   0   0   1   0
# v2        0:0       1   0   2   0   2   0   0   0   0   0   1   0

#
#
# And by taking vrf name:
# BUR0051#show ipv6 route CORE
# typ  prefix                             metric  iface      hop                    time
# C    fd00:67:7e69::a:8:e:0/120          0/0     sdn5.3607  null                   3d5h
# LOC  fd00:67:7e69::a:8:e:2/128          0/1     sdn5.3607  null                   3d5h
# O    fd00:515e:898::a:6:6:6/128         110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  09:11:46
# O    fd00:51e5::a:1:1:1/128             110/30  sdn5.3607  fd00:67:7e69::a:8:e:1  09:11:46
# O    fd00:51e5::a:2:2:2/128             110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  09:14:43
# O    fd00:51e5::a:3:3:3/128             110/50  sdn5.3607  fd00:67:7e69::a:8:e:1  09:08:38
# O    fd00:51e5::a:4:4:4/128             110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  09:17:16
# O    fd00:51e5::a:5:5:5/128             110/60  sdn5.3607  fd00:67:7e69::a:8:e:1  06:52:08
# O    fd00:51e5::a:a:a:a/128             110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  09:11:43
# O    fd00:51e5::a:c:c:c/128             110/50  sdn5.3607  fd00:67:7e69::a:8:e:1  00:05:22
# O    fd00:51e5::a:63:63:63/128          110/50  sdn5.3607  fd00:67:7e69::a:8:e:1  01:37:48
# O    fd00:51e5:4bd::a:9:9:9/128         110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  1d4h
# O    fd00:51e5:4e70::a:f:f:f/128        110/20  sdn5.3607  fd00:67:7e69::a:8:e:1  3d5h
# O    fd00:51e5:4e70:4e3:a:10:10:10/128  110/40  sdn5.3607  fd00:67:7e69::a:8:e:1  3d5h
# C    fd00:51e5:7e69::a:e:e:e/128        0/0     loopback0  null                   39d6h
# C    fd00:51e5:7e69::a:e:f:0/120        0/0     sdn1       null                   39d6h
# LOC  fd00:51e5:7e69::a:e:f:e/128        0/1     sdn1       null                   39d6h
# C    fd00:7e69:4e70::a:13:10:0/120      0/0     sdn5.3610  null                   31d3h
# LOC  fd00:7e69:4e70::a:13:10:1/128      0/1     sdn5.3610  null                   31d3h
# C    fe80::/64                          0/0     sdn5.3607  null                   3d5h




FACT_SUBSETS = {'default': Default,
                'hardware': Hardware,
                'interfaces': Interfaces,
                'config': Config}

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())


def main():
    """main entry point for module execution
    """
    argument_spec = {'gather_subset': {'default': ['!config'], 'type': 'list'}}
    argument_spec.update(freertr_argument_spec)
    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)
    gather_subset = module.params['gather_subset']
    runable_subsets = set()
    exclude_subsets = set()

    for subset in gather_subset:
        if subset == 'all':
            runable_subsets.update(VALID_SUBSETS)
            continue
        if subset.startswith('!'):
            subset = subset[1:]
            if subset == 'all':
                exclude_subsets.update(VALID_SUBSETS)
                continue
            exclude = True
        else:
            exclude = False
        if subset not in VALID_SUBSETS:
            module.fail_json(msg='Bad subset')
        if exclude:
            exclude_subsets.add(subset)
        else:
            runable_subsets.add(subset)
    if not runable_subsets:
        runable_subsets.update(VALID_SUBSETS)

    runable_subsets.difference_update(exclude_subsets)
    runable_subsets.add('default')

    facts = {}
    facts['gather_subset'] = [runable_subsets]

    instances = []
    for key in runable_subsets:
        instances.append(FACT_SUBSETS[key](module))

    for inst in instances:
        inst.populate()
        facts.update(inst.facts)

    ansible_facts = {}
    for key, value in iteritems(facts):
        key = 'ansible_net_%s' % key
        ansible_facts[key] = value

    warnings = []
    check_args(module, warnings)
    module.exit_json(ansible_facts=ansible_facts, warnings=warnings)


if __name__ == '__main__':
    main()
