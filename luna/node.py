'''
Written by Dmitry Chirikov <dmitry@chirikov.ru>
This file is part of Luna, cluster provisioning tool
https://github.com/dchirikov/luna

This file is part of Luna.

Luna is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Luna is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Luna.  If not, see <http://www.gnu.org/licenses/>.

'''

from config import *

import re
import socket
import logging
import datetime

from luna import utils
from luna.base import Base
from luna.cluster import Cluster
from luna.switch import Switch
from luna.group import Group


class Node(Base):
    """Class for operating with node objects"""

    log = logging.getLogger(__name__)

    def __init__(self, name=None, mongo_db=None, create=False, id=None,
                 group=None, localboot=False, setupbmc=True, service=False):
        """
        name  - optional
        group - the group the node belongs to; required

        FLAGS:
        localboot - boot from localdisk
        setupbmc  - whether we setup ipmi on install
        service   - do not install, boot into installer (dracut environment)
        """

        self.log.debug("function {} args".format(self._debug_function()))

        # Define the schema used to represent node objects

        self._collection_name = 'node'
        self._keylist = {'port': type(''), 'localboot': type(True),
                         'setupbmc': type(True), 'service': type(True),
                         'mac': type('')}

        # Check if this node is already present in the datastore
        # Read it if that is the case

        node = self._get_object(name, mongo_db, create, id)

        if create:
            cluster = Cluster(mongo_db=self._mongo_db)
            group = Group(group, mongo_db=self._mongo_db)

            # If a name is not provided, generate one

            if not bool(name):
                name = self._generate_name(cluster, mongo_db=mongo_db)

            # Store the new node in the datastore

            node = {'name': name, 'group': group.DBRef, 'interfaces': {},
                    'mac': None, 'switch': None, 'port': None,
                    'localboot': localboot, 'setupbmc': setupbmc,
                    'service': service, 'bmcnetwork': None}

            self.log.debug("Saving node '{}' to the datastore".format(node))

            self.store(node)

            for interface in group._json['interfaces']:
                self._add_ip(interface)

            self._add_ip(bmc=True)

            # Link this node to its group and the current cluster

            self.link(group)
            self.link(cluster)

        self.log = logging.getLogger(__name__ + '.' + self._json['name'])

    def _generate_name(self, cluster, mongo_db):
        """Based on every node linked to the cluster
           generate a name for the new node"""

        prefix = cluster.get('nodeprefix')
        digits = cluster.get('nodedigits')
        back_links = cluster.get_back_links()

        max_num = 0

        for link in back_links:

            # Skip non node objects

            if link['collection'] != self._collection_name:
                continue

            node = Node(id=link['DBRef'].id, mongo_db=mongo_db)
            name = node.name

            try:
                node_number = int(name.lstrip(prefix))
            except ValueError:
                continue

            if node_number > max_num:
                max_num = node_number

        new_name = prefix + str(max_num + 1).zfill(digits)

        return new_name

    def _add_ip(self, interface=None, new_ip=None, bmc=False):
        if not bmc and not interface:
            self.log.error("Interface should be specified")
            return None

        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)

        if bmc and self._json['bmcnetwork']:
            self.log.error(("Node already has a BMC IP address"
                            .format(interface)))
            return None

        elif interface in self._json['interfaces']:
            self.log.error(("Interface '{}' already has an IP address"
                            .format(interface)))
            return None

        ip = group._manage_ip(interface, new_ip, bmc=bmc)

        if not ip:
            self.log.warning(("Could not reserve IP {} for {} interface"
                              .format(new_ip or '', interface or 'BMC')))
            return None

        if bmc and ip:
            res = self.set('bmcnetwork', ip)
        elif ip:
            self._json['interfaces'][interface] = ip
            res = self.set('interfaces', self._json['interfaces'])

        return res

    def _del_ip(self, interface=None, bmc=False):
        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)
        interfaces = self._json['interfaces']
        bmcip = self._json['bmcnetwork']

        if bmc and not bmcip:
            return True

        elif interfaces:
            new_interfaces = interfaces.copy()

        else:
            self.log.error("Node has no interfaces configured")
            return None

        if bmc:
            group._manage_ip(ip=bmcip, bmc=bmc, release=True)
            res = self.set('bmcnetwork', None)

        elif not interface:
            for iface in interfaces:
                group._manage_ip(iface, ip=interfaces[iface], release=True)
                new_interfaces.pop(iface)

            res = self.set('interfaces', new_interfaces)

        elif interface in interfaces:
            group._manage_ip(interface, interfaces[interface], release=True)
            new_interfaces.pop(interface)
            res = self.set('interfaces', new_interfaces)

        else:
            self.log.warning(("Node does not have an '{}' interface"
                              .format(interface)))
            return None

        return res

    @property
    def boot_params(self):
        """will return dictionary with all needed params for booting:
           kernel, initrd, kernel opts, ip, net, prefix"""

        params = {}
        group = Group(id=self.get('group').id, mongo_db=self._mongo_db)
        group_params = group.boot_params

        params['boot_if'] = group_params['boot_if']
        params['kernel_file'] = group_params['kernel_file']
        params['initrd_file'] = group_params['initrd_file']
        params['kern_opts'] = group_params['kern_opts']
        params['boot_if'] = group_params['boot_if']
        params['net_prefix'] = group_params['net_prefix']
        params['name'] = self.name
        params['service'] = int(self.get('service'))
        params['localboot'] = self.get('localboot')

        if params['boot_if']:
            params['ip'] = self.get_ip(params['boot_if'])

        return params

    @property
    def install_params(self):
        params = {}
        group = Group(id=self.get('group').id, mongo_db=self._mongo_db)
        params = group.install_params

        params['name'] = self.name
        params['setupbmc'] = self.get('setupbmc')

        if params['domain']:
            params['hostname'] = self.name + "." + params['domain']
        else:
            params['hostname'] = self.name

        if params['torrent_if']:
            params['torrent_if_ip'] = self.get_ip(params['torrent_if'])

        for interface in params['interfaces']:
            ip = self.get_ip(interface)
            if ip:
                params['interfaces'][interface] += "\n" + "IPADDR=" + ip

        if params['bmcsetup']:
            try:
                params['bmcsetup']['ip'] = self.get_ip(bmc=True)
            except:
                pass

        return params

    def show(self):
        def get_value(dbref):
            mongo_collection = self._mongo_db[dbref.collection]
            try:
                name = mongo_collection.find_one({'_id': dbref.id})['name']
                name = '[' + name + ']'
            except:
                name = '[id_' + str(dbref.id) + ']'
            return name

        json = self._json.copy()

        for attr in self._json:
            if attr in ['_id', use_key, usedby_key]:
                json.pop(attr)

        json['group'] = get_value(json['group'])

        return json

    def set_group(self, new_group_name=None):
        if not new_group_name:
            self.log.error("Group needs to be specified")
            return None

        new_group = Group(new_group, mongo_db=self._mongo_db)
        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)
        group_interfaces = group._json['interfaces']

        if 'bmcnetwork' in group._json:
            bmc_net_id = group._json['bmcnetwork'].id
            bmc_ip = self.get_ip(bmc=True)
        else:
            bmc_net_id = None
            bmc_ip = None

        self._del_ip(bmc=True)

        ips = {}
        for interface in group_interfaces:
            if 'network' in group_interfaces[interface]:
                net_id = group_interfaces[interface]['network'].id
                ip = self.get_ip(interface)
                ips[net_id] = {'interface': interface, 'ip': ip}
            else:
                net_id = None

            self._del_ip(interface)

        self.unlink(group)
        res = self.set('group', new_group.DBRef)
        self.link(new_group)

        if 'bmcnetwork' in new_group._json:
            newbmc_net_id = new_group._json['bmcnetwork'].id
        else:
            newbmc_net_id = None

        if bool(bmc_net_id) and newbmc_net_id == bmc_net_id:
            self._add_ip(bmc_ip, bmc=True)
        else:
            self._add_ip(bmc=True)

        new_group_interfaces = new_group._json['interfaces']
        for interface in new_group_interfaces:
            if 'network' in new_group_interfaces[interface]:
                net_id = new_group_interfaces[interface]['network'].id

                if net_id in ips:
                    self._add_ip(interface, ips[net_id]['ip'])
                else:
                    self._add_ip(interface)

            else:
                net_id = None

            self._add_ip(interface, ip)

        return res

    def set_ip(self, interface=None, ip=None, bmc=False):
        if not ip:
            self.log.error("IP address should be provided")
            return None

        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)

        if not bool(group.get_ip(interface, ip, bmc=bmc, format='num')):
            return None

        res = self._del_ip(interface=interface, bmc=bmc)

        if res:
            return self._add_ip(interface, ip, bmc=bmc)

        return None

    def set_mac(self, mac=None):
        if not mac:
            mac = self.get_mac()
            self._mongo_db['switch_mac'].remove({'mac': mac})
            self._mongo_db['mac'].remove({'mac': mac})

        elif re.match('(([a-fA-F0-9]{2}:){5}([a-fA-F0-9]{2}))$', mac):
            mac = mac.lower()
            utils.helpers.set_mac_node(mac, self.DBRef, (self._mongo_db))

        else:
            self.log.error("Invalid MAC address '{}'".format(mac))
            return False

        return True

    def set_switch(self, value):
        if value:
            switch = self._json['switch']
            new_switch = Switch(value).DBRef

        elif self._json['switch'] is None:
            return True

        else:
            switch = self._json['switch']
            new_switch = None

        res = self.set('switch', new_switch)

        if res and value:
            self.link(new_switch)

        if res and switch:
            self.unlink(Switch(id=switch.id).DBRef)

        return bool(res)

    def get_ip(self, interface=None, bmc=False, format='human'):
        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)
        if bmc:
            ipnum = self._json['bmcnetwork']
        elif interface in self._json['interfaces']:
            ipnum = self._json['interfaces'][interface]
        else:
            self.log.warning(("{} interface has no IP"
                              .format(interface or 'BMC')))
            return None
        return group.get_ip(interface, ipnum, bmc=bmc, format=format)

    def get_mac(self):
        try:
            mac = str(self._mongo_db['mac']
                      .find_one({'node': self.DBRef})['mac'])
        except:
            mac = None

        return mac

    def update_status(self, step=None):
        if not bool(step):
            self.log.error("No data to update status of the node.")
            return None

        if not bool(re.match('^[ a-zA-Z0-9\.\-_]+?$', step)):
            self.log.error(("'Step' parameter in contains invalid string."
                            .format(self.name)))
            return None

        status = {'step': step, 'time': datetime.datetime.utcnow()}
        self.set('status', status)

    def get_status(self, relative=True):
        try:
            status = self._json['status']
            step = str(status['step'])
            time = status['time']
        except:
            return None

        now = datetime.datetime.utcnow()
        tracker_records = []
        tracker_record = {}
        tor_time = datetime.datetime(1, 1, 1)
        perc = 0.0

        if step == 'install.download':
            name = "%20s" % self.name
            peer_id = ''.join(["{:02x}".format(ord(l)) for l in name])
            self._mongo_db
            tracker_collection = self._mongo_db['tracker']
            tracker_records = tracker_collection.find({'peer_id': peer_id})

        for doc in tracker_records:
            try:
                tmp_time = doc['updated']
            except:
                continue
            if tmp_time > tor_time:
                tracker_record = doc
                tor_time = tmp_time

        if bool(tracker_record):
            try:
                left = tracker_record['left']
                perc = 100.0*downloaded/(downloaded+left)
            except:
                tor_time = datetime.datetime(1, 1, 1)
                perc = 0.0

        if bool(perc) and (tor_time > time):
            status = ("%s (%.2f%% / last update %isec)"
                      % (step, perc, (now - tor_time).seconds))
        else:
            status = step

        if relative:
            sec = (now - time).seconds
            ret_time = str(datetime.timedelta(seconds=sec))
        else:
            ret_time = str(time)

        return {'status': status, 'time': ret_time}

    def check_avail(self, timeout=1, bmc=True, net=None):
        avail = {'bmc': None, 'nets': {}}
        bmc_ip = self.get_ip(bmc=True)

        if bmc and bmc_ip:
            ipmi_message = ("0600ff07000000000000000000092018c88100388e04b5"
                            .decode('hex'))
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(ipmi_message, (bmc_ip, 623))

            try:
                data, addr = sock.recvfrom(1024)
                avail['bmc'] = True
            except socket.timeout:
                avail['bmc'] = False

        group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)
        test_ips = []

        try:
            ifs = self._json['interfaces']
        except:
            ifs = {}

        for interface in ifs:
            tmp_net = group.get_net_name_for_if(interface)
            tmp_json = {'network': tmp_net,
                        'ip': self.get_ip(interface)}

            if bool(net):
                if tmp_net == net:
                    test_ips.append(tmp_json)
            else:
                if bool(tmp_net):
                    test_ips.append(tmp_json)

        for elem in test_ips:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((elem['ip'], 22))

            if result == 0:
                avail['nets'][elem['network']] = True
            else:
                avail['nets'][elem['network']] = False
        return avail

    def release_resource(self):
        mac = self.get_mac()
        self._mongo_db['switch_mac'].remove({'mac': mac})
        self._mongo_db['mac'].remove({'mac': mac})

        self._del_ip(bmc=True)
        self._del_ip()

        return True
