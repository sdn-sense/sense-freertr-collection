#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import re
from netaddr import IPAddress
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.utils.display import Display
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import run_commands
from ansible_collections.sense.freertr.plugins.module_utils.network.freertr import freertr_argument_spec, check_args

display = Display()


class FactsBase:
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


class Interfaces(FactsBase):
    """All Interfaces Class"""
    COMMANDS = ['show interfaces',
                'show ipv4 interface',
                'show ipv6 interface',
                'show lldp neighbor']

    def populate(self):
        super(Interfaces, self).populate()

        self.facts.setdefault('interfaces', {})
        self.facts.setdefault('info', {'macs': []})
        interfaceData = self.parseInterfaces(self.responses[0])
        for intfName, intfDict in interfaceData.items():
            tmpD = self.facts['interfaces'].setdefault(intfName, {})
            tmpD['operstatus'] = intfDict['operstatus']
            unpLines = "\n".join(intfDict['unparsed'])
            tmpD['description'] = self.parseDesc(unpLines)
            # display.vvv(str(unpLines))
            # tmpD['type'] = self.parseType(unpLines)
            tmpD['macaddress'] = self.parseHwaddr(unpLines)
            if tmpD['macaddress'] and tmpD['macaddress'] not in self.facts['info']['macs']:
                self.facts['info']['macs'].append(tmpD['macaddress'])
            tmpD['mtu'] = self.parseMTU(unpLines)
            tmpD['bandwidth'] = self.parseBW(unpLines)
            splIntf = intfName.split('.')
            if len(splIntf) == 2:
                self.facts['interfaces'][intfName].setdefault('tagged', [])
                self.facts['interfaces'][intfName]['tagged'].append(splIntf[0])

        self.populateIPs(self.responses[1].split('\n'), 'ipv4')
        self.populateIPs(self.responses[2].split('\n'), 'ipv6')

        self.facts['lldp'] = self.populateLLDPInfo(self.responses[3])

    def populateLLDPInfo(self, data):
        """Get all lldp information"""
        out = {}
        for line in data.split('\n'):
            splLine = list(filter(None, line.split(' ')))
            if len(splLine) >= 5:
                if splLine[0] == 'interface':
                    # Ignore first line
                    continue
                out.setdefault(splLine[0], self.getLLDPIntfInfo(splLine))
        return out

    def getLLDPIntfInfo(self, splLine):
        """Get lldp info of specific interface"""
        def checkIfMac(inEntry):
            """ FreeRTR Check if return value is mac. It returns weird state"""
            # "b859.9fed.2bee"
            tmp = inEntry.split('.')
            if len(tmp) != 3:
                return False
            for item in tmp:
                if len(item) != 4:
                    return False
            return True

        def normalizeMac(input):
            """Normalize mac to normal format"""
            macaddr = input.strip().replace('.', '')
            split_mac = [macaddr[index: index + 2] for index in range(0, len(macaddr), 2)]
            return ":".join(split_mac)

        out = {'remote_system_name': splLine[1], 'local_port_id': splLine[0]}
        lldpInfo = self.run(["show lldp detail %s" % splLine[0]])
        for line in lldpInfo[0].split('\n'):
            if not line:
                continue
            match = re.search(r'peer *(\S+)$', line, re.M)
            if match:
                out['remote_chassis_id'] = normalizeMac(match.group(1))
            match = re.search(r'port id *([^$]*)$', line, re.M)
            if match:
                tmpout = match.group(1).strip()
                if checkIfMac(tmpout):
                    tmpout = normalizeMac(tmpout)
                out['remote_port_id'] = tmpout
        return out

    @staticmethod
    def _getIP(data):
        """Get IP address info"""
        out = {}
        for line in data:
            splLine = list(filter(None, line.split(' ')))
            if len(splLine) == 4:
                if splLine[0] == 'interface':
                    # Ignore first line
                    continue
                out[splLine[0]] = {'address': splLine[2],
                                   'masklen': IPAddress(splLine[3]).netmask_bits()}
        return out

    def populateIPs(self, data, iptype):
        """Populate IPs in interfaces output"""
        for intName, intDict in self._getIP(data).items():
            if intName in self.facts['interfaces']:
                self.facts['interfaces'][intName].setdefault(iptype, [])
                self.facts['interfaces'][intName][iptype].append(intDict)

    @staticmethod
    def parseIpv6(data):
        """Parse IPv6 address from output"""
        #  ipv6 address=fd00:67:7e69::a:8:e:2/120, mask=ffff:ffff:ffff:ffff:ffff:ffff:ffff:ff00, ifcid=325883999
        match = re.search(r'ipv6 address is ([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseIpv4(data):
        """Parse IPv4 address from output"""
        #  ipv4 address=10.8.14.2/24, mask=255.255.255.0, ifcid=684917826
        match = re.search(r'ipv4 address is ([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseVrf(data):
        """Parse vrf from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        match = re.search(r'vrf is ([^ ,]*)', data, re.M)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def parseBW(data):
        """Parse bw from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        #  type is ethernet, hwaddr=0000.0bad.c0de, mtu=1500, bw=100mbps, vrf=oob
        for reg in [r'bw is ([^ ,]*)', r'bw=([^ ,]*)']:
            match = re.search(reg, data, re.M)
            if match:
                speed = match.group(1).strip()
                if speed.endswith('kbps'):
                    return int(speed[:-4]) // 1000000
                if speed.endswith('mbps'):
                    return int(speed[:-4]) // 1000
                if speed.endswith('gbps'):
                    return int(speed[:-4])
        return 0

    @staticmethod
    def parseMTU(data):
        """Parse mtu from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        #  type is ethernet, hwaddr=0000.0bad.c0de, mtu=1500, bw=100mbps, vrf=oob
        for reg in [r'mtu is ([^ ,]*)', r'mtu=([^ ,]*)']:
            match = re.search(reg, data, re.M)
            if match:
                return int(match.group(1).strip())
        return 0

    @staticmethod
    def parseHwaddr(data):
        """Parse hwaddr from output"""
        #  type is sdn, hwaddr=0015.180b.6038, mtu=1496, bw=8000kbps, vrf=CORE
        #  type is ethernet, hwaddr=0000.0bad.c0de, mtu=1500, bw=100mbps, vrf=oob
        for reg in [r'hwaddr is ([^ ,]*)', r'hwaddr=([^ ,]*)?']:
            match = re.search(reg, data, re.M)
            if match and match.group(1).strip() != 'none':
                macaddr = match.group(1).strip().replace('.', '')
                split_mac = [macaddr[index: index + 2] for index in range(0, len(macaddr), 2)]
                return ":".join(split_mac)
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
                if line.startswith(' ') and intName:
                    parsed[intName]['unparsed'].append(line)
                else:
                    match = re.match(r'^([a-zA-Z0-9.]+) is ([a-zA-Z]+),? ?(promisc)?.*', line)
                    if match:
                        intName = match[1]
                        parsed.setdefault(intName, {'operstatus': match[2], 'unparsed': []})
        return parsed


class Routing(FactsBase):
    """Routing Information Class"""
    COMMANDS = [
        'show vrf routing',
    ]

    def populate(self):
        super(Routing, self).populate()
        parsedRoutes = self.parserouting(self.responses[0])
        for key, vals in parsedRoutes.items():
            self.facts.setdefault(key, [])
            for item in vals:
                tmpout = {'vrf': item['vrf'], 'intf': item['iface'], 'from': item['prefix']}
                if item['hop'] != 'null':
                    tmpout['to'] = item['hop']
                self.facts[key].append(tmpout)

    def parserouting(self, data):
        """Parse routing"""
        vrfs = []
        out = {}
        lineNum = 0
        for line in data.split('\n'):
            lineNum += 1
            # Ignoring first 2 lines
            if lineNum <= 2:
                continue
            splLine = line.split(' ')
            vrfs.append(splLine[0])
        out = self.parseallvrfs(vrfs, 'ipv4', out)
        out = self.parseallvrfs(vrfs, 'ipv6', out)
        return out

    def parseallvrfs(self, vrfs, iptype, out):
        """Get and Parse all vrfs for iptype (ipv4/ipv6)"""
        out.setdefault(iptype, [])
        for vrf in vrfs:
            if not vrf:
                continue
            vrfInfo = self.run([f"show {iptype} route {vrf}"])
            keys = []
            lineNum = 0
            for vrfEntry in vrfInfo[0].split('\n'):
                lineNum += 1
                values = list(filter(None, vrfEntry.split(' ')))
                if lineNum == 1:
                    keys = values
                    continue
                tmpDict = dict(zip(keys, values))
                tmpDict['vrf'] = vrf
                out[iptype].append(tmpDict)
        return out


FACT_SUBSETS = {'default': Default,
                'interfaces': Interfaces,
                'routing': Routing}

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

    facts = {'gather_subset': [runable_subsets]}

    instances = []
    for key in runable_subsets:
        instances.append(FACT_SUBSETS[key](module))

    for inst in instances:
        if inst:
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
