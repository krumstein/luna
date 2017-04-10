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
from tornado import template


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
        self.group = None
        if group:
            if type(group) == Group:
                self.group = group
            if type(group) == str:
                self.group = Group(group, mongo_db=self._mongo_db)

        if create:

            if not group:
                self.log.error("Group needs to be specified when creating node.")
                raise RuntimeError

            cluster = Cluster(mongo_db=self._mongo_db)

            # If a name is not provided, generate one

            if not bool(name):
                name = self._generate_name(cluster, mongo_db=mongo_db)

            # Store the new node in the datastore

            node = {'name': name, 'group': self.group.DBRef, 'interfaces': {},
                    'mac': None, 'switch': None, 'port': None,
                    'localboot': localboot, 'setupbmc': setupbmc,
                    'service': service, 'bmcnetwork': None}

            self.log.debug("Saving node '{}' to the datastore".format(node))

            self.store(node)

            for interface_name in self.group.list_ifs().keys():
                self.add_ip(interface_name)

            self.add_ip(bmc=True)

            # Link this node to its group and the current cluster

            self.link(self.group)
            self.link(cluster)

        if group:
            # check if group specified is the group node belongs to
            if self.group.DBRef != self._json['group']:
                raise RuntimeError

        self.log = logging.getLogger(__name__ + '.' + self._json['name'])

    def _get_group(self):
        if not self.group:
            self.group = Group(id=self._json['group'].id, mongo_db=self._mongo_db)
        return True

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

    def list_ifs(self):
        self._get_group()
        return self.group.list_ifs()

    def add_ip(self, interface_name=None, new_ip=None, bmc=False):

        interface_uuid = None

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        if bmc:
            self._get_group()

        if not bmc and not interface_name:
            self.log.error("Interface should be specified")
            return None

        if bmc and self.get('bmcnetwork'):
            self.log.error(("Node already has a BMC IP address"
                            .format(interface_name)))
            return None

        if (interface_name
                and interface_uuid in self._json['interfaces']
                and self._json['interfaces'][interface_uuid]):
            self.log.error(("Interface '{}' has IP address already"
                            .format(interface_name)))
            return None

        ip = self.group.manage_ip(interface_uuid, new_ip, bmc=bmc)

        if not ip:
            self.log.warning(("Could not reserve IP {} for {} interface"
                              .format(new_ip or '', interface_name or 'BMC')))
            return None

        if bmc:
            res = self.set('bmcnetwork', ip)
        else:
            self._json['interfaces'][interface_uuid] = ip
            res = self.set('interfaces', self._json['interfaces'])

        return res

    def del_ip(self, interface_name=None, bmc=False):

        self._get_group()

        # first work with BMC

        bmcip = self._json['bmcnetwork']

        if bmc and not bmcip:
            self.log.error("Node has no BMC interface configured")
            return True

        if bmc:
            self.group.manage_ip(ip=bmcip, bmc=bmc, release=True)
            res = self.set('bmcnetwork', None)
            return res

        # regular interfaces

        interface_uuid = None

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        interfaces = self._json['interfaces']

        if not interfaces:
            self.log.error("Node has no interfaces configured")
            return None

        new_interfaces = interfaces.copy()


        if not interface_name:
            for if_uuid in interfaces:
                if_ip_assigned = interfaces[if_uuid]
                self.group.manage_ip(if_uuid, ip=if_ip_assigned, release=True)
                new_interfaces.pop(if_uuid)
            res = self.set('interfaces', new_interfaces)
            return res

        if interface_uuid in interfaces:
            if_ip_assigned = interfaces[interface_uuid]
            self.group.manage_ip(interface_uuid, if_ip_assigned, release=True)
            new_interfaces.pop(interface_uuid)
            res = self.set('interfaces', new_interfaces)
            return res

        self.log.warning(("Node does not have an '{}' interface"
            .format(interface)))
        return None


    @property
    def boot_params(self):
        """will return dictionary with all needed params for booting:
           kernel, initrd, kernel opts, ip, net, prefix"""

        params = {}
        self._get_group()
        group_params = self.group.boot_params

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
        self._get_group
        params = self.group.install_params

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

        new_group = Group(new_group_name, mongo_db=self._mongo_db)
        self._get_group()
        group_interfaces = self.group._json['interfaces']

        if 'bmcnetwork' in self.group._json and self.group._json['bmcnetwork']:
            bmc_net_id = self.group._json['bmcnetwork'].id
            bmc_ip = self.get_ip(bmc=True)
        else:
            bmc_net_id = None
            bmc_ip = None

        self.del_ip(bmc=True)

        ips = {}

        for interface in group_interfaces:
            if_name = group_interfaces[interface]['name']
            if ('network' in group_interfaces[interface] and
                    group_interfaces[interface]['network']):
                net_id = group_interfaces[interface]['network'].id
                ip = self.get_ip(if_name)
                ips[net_id] = {'interface': if_name, 'ip': ip}
            else:
                net_id = None

            self.del_ip(if_name)

        self.unlink(self.group)
        res = self.set('group', new_group.DBRef)
        self.link(new_group)
        self.group = None
        self._get_group()

        if 'bmcnetwork' in new_group._json and new_group._json['bmcnetwork']:
            newbmc_net_id = new_group._json['bmcnetwork'].id
        else:
            newbmc_net_id = None

        if bool(bmc_net_id) and newbmc_net_id == bmc_net_id:
            self.add_ip(new_ip=bmc_ip, bmc=True)
        else:
            self.add_ip(bmc=True)

        new_group_interfaces = new_group._json['interfaces']
        for interface in new_group_interfaces:
            if_name = new_group_interfaces[interface]['name']
            if ('network' in new_group_interfaces[interface] and
                    new_group_interfaces[interface]['network']):
                net_id = new_group_interfaces[interface]['network'].id

                if net_id in ips:
                    self.add_ip(if_name, ips[net_id]['ip'])
                else:
                    self.add_ip(if_name)

            else:
                self.add_ip(if_name)

            #self.add_ip(if_name, ip)

        return True

    def set_ip(self, interface_name=None, ip=None, bmc=False):

        if not ip:
            self.log.error("IP address should be provided")
            return None

        interface_uuid = None

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        if bmc:
            self._get_group()

        if not bool(self.group.get_ip(interface_uuid, ip, bmc=bmc, format='num')):
            return None

        res = self.del_ip(interface_name, bmc=bmc)

        if res:
            return self.add_ip(interface_name, ip, bmc=bmc)

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
            new_switch = Switch(value, mongo_db=self._mongo_db).DBRef

        elif self._json['switch'] is None:
            return True

        else:
            switch = self._json['switch']
            new_switch = None

        res = self.set('switch', new_switch)

        if res and value:
            self.link(new_switch)

        if res and switch:
            self.unlink(Switch(id=switch.id, mongo_db=self._mongo_db).DBRef)

        return bool(res)

    def get_ip(self, interface_name=None, interface_uuid = None, bmc=False, format='human'):

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        if not interface_uuid and not bmc:
            self.log.error('Unable to find UUID for interface {}'
                    .format(interface_name))
            return None


        if bmc and 'bmcnetwork' in self._json:
            ipnum = self._json['bmcnetwork']
        elif interface_uuid and  interface_uuid in self._json['interfaces']:
            ipnum = self._json['interfaces'][interface_uuid]
        else:
            self.log.warning(('{} interface has no IP'
                              .format(interface_name or 'BMC')))
            return None

        if format == 'num':
            return ipnum
        else:
            self._get_group()
            return self.group.get_ip(interface_uuid, ipnum, bmc=bmc, format='human')

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

        self._get_group()
        test_ips = []

        try:
            ifs = self._json['interfaces']
        except:
            ifs = {}

        for interface in ifs:
            tmp_net = group.group.get_net_name_for_if(interface)
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

    def release_resources(self):
        mac = self.get_mac()
        self._mongo_db['switch_mac'].remove({'mac': mac})
        self._mongo_db['mac'].remove({'mac': mac})

        self.del_ip(bmc=True)
        self.del_ip()

        return True

    def render_script(self, name):
        scripts = ['boot', 'install']
        if name not in scripts:
            self.log.error(
                    "'{}' is not correct script. Valid options are: '{}'"
                    .format(name, scripts)
                    )
            return None
        cluster = Cluster(mongo_db=self._mongo_db)
        self._get_group()
        path = cluster.get('path')
        server_ip = cluster.get('frontend_address')
        server_port = cluster.get('frontend_port')
        tloader = template.Loader(path + '/templates')
        if name == 'boot':
            p = self.boot_params
            p['server_ip'] = server_ip
            p['server_port'] = server_port
            p['delay'] = 10
            if not p['boot_if']:
                p['ifcfg'] = 'dhcp'
            else:
                p['ifcfg'] = (p['boot_if'] + ":" +
                                        p['ip'] + "/" +
                                        str(p['net_prefix']))
            return tloader.load('templ_nodeboot.cfg').generate(p=p)
        if name == 'install':
            return tloader.load('templ_install.cfg').generate(
                    p=self.install_params,
                    server_ip=server_ip,
                    server_port=server_port
                    )



