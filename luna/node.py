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

    def add_ip(self, interface_name=None, new_ip=None, version=None):

        interface_uuid = None

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        if not interface_name:
            self.log.error("Interface should be specified")
            return None

        interfaces = self._json['interfaces']

        # First check if we have some bits for this interface,
        # if no - create empty. Latter should be the case
        # on node creation
        if interface_uuid in interfaces:
            interface_ips = interfaces[interface_uuid]
        else:
            interface_ips = {'4': None, '6': None}

        # Tiny list for storing IPvX keys for which IP
        # can be assigned: [], ['4'], ['6'], ['4', '6']
        no_ip_keys = []
        for key in interface_ips:
            if not interface_ips[key]:
                no_ip_keys.append(key)

        # Check if passed version in that list
        # If no - we are unable to proceed
        if version and version not in no_ip_keys:
            self.log.error("Interface '{}' has IPv{} address already"
                .format(interface_name, version))
            return False

        # No we know which IPvX we need to assign
        # if version is specified - use it
        if version:
            versions_to_assign = [version]
        else:
            versions_to_assign = no_ip_keys[:]

        # on this step we have versions_to_assign, but we are not sure if we can
        # as network for this IPvX could not exist in corresponding group
        # So pop versions if we have no network configured
        tmp = versions_to_assign[:]
        versions_to_assign = []
        for v in range(len(tmp)):
            net = self.group._json['interfaces'][interface_uuid]['network'][tmp[v]]
            if net:
                versions_to_assign.append(tmp[v])

        # versions_to_assign contains all IPvX we can assign finally
        # Now we can report an error if we unable to meet assignment
        # if 'version' passed as parameter
        if version and version not in versions_to_assign:
            self.log.error(
                ("Unable to assign IP address IPv{} for interface {}, "
                 + "as network is not configured")
                .format(version, interface_name)
            )

        # Finally we can acquire IPs
        ips = {} # for rolling back if needed
        for ver in versions_to_assign:
            ip = self.group.manage_ip(interface_uuid, new_ip, version=ver)
            interface_ips[ver] = ip
            if not ip:
                self.log.error(
                    "Could not reserve IP {} (IPv{}) for {} interface"
                    .format(new_ip or '', ver, interface_name or 'this'))
                for v in ips:
                    self.group.manage_ip(
                        interface_uuid,
                        ip=ips[v],
                        release=True,
                        version=v
                    )
                return False
            ips[ver] = ip

        all_interfaces = self._json['interfaces']
        all_interfaces[interface_uuid] = interface_ips
        res = self.set('interfaces', all_interfaces)

        return res

    def del_ip(self, interface_name=None):

        self._get_group()

        interfaces = self._json['interfaces']

        if not interfaces:
            self.log.error("Node has no interfaces configured")
            return None

        new_interfaces = interfaces.copy()

        # if interface_name is not specified
        # delete all interfaces

        if not interface_name:
            for if_uuid in interfaces:
                if_ip_assigned = interfaces[if_uuid]
                self.group.manage_ip(if_uuid, ip=if_ip_assigned, release=True)
                new_interfaces.pop(if_uuid)
            res = self.set('interfaces', new_interfaces)
            return res

        # here interface_name is defined,
        # so release this IP

        interface_uuid = None

        interface_dict = self.list_ifs()
        interface_uuid = interface_dict[interface_name]

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

        params = group_params.copy()

        params['bootproto'] = 'dhcp'

        params['name'] = self.name

        params['hostname'] = self.name

        if params['domain']:
            params['hostname'] += "." + params['domain']


        # FIXME 'service' and 'localboot' should be int or bool
        # not mix, please
        params['service'] = int(self.get('service'))
        params['localboot'] = self.get('localboot')

        interfaces = self.list_ifs()
        bootif_uuid = None

        params['ip'] = ''

        if 'BOOTIF' in interfaces:
            params['ip'] = self.get_ip('BOOTIF')

        params['mac'] = self.get_mac()
        if (params['ip']
                and params['mac']
                and (params['net_prefix'] or params['net_mask'])):
            params['bootproto'] = 'static'

        return params

    @property
    def install_params(self):
        params = {}
        self._get_group()
        params = self.group.install_params

        params['name'] = self.name
        params['setupbmc'] = self.get('setupbmc')
        params['mac'] = self.get_mac() or ''

        if params['domain']:
            params['hostname'] = self.name + "." + params['domain']
        else:
            params['hostname'] = self.name

        for interface in params['interfaces']:
            ip = self.get_ip(interface)
            if ip:
                params['interfaces'][interface]['ip'] = str(ip)

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

        ips = {}

        for interface in group_interfaces:
            if_name = group_interfaces[interface]['name']
            if ('network' in group_interfaces[interface] and
                    group_interfaces[interface]['network']):
                net_id = group_interfaces[interface]['network'].id
                ip = self.get_ip(if_name)
                ips[net_id] = {'interface': if_name, 'ip': ip}

        self.del_ip()

        self.unlink(self.group)

        res = self.set('group', new_group.DBRef)

        self.link(new_group)
        self.group = None
        self._get_group()

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

    def set_ip(self, interface_name=None, ip=None):

        if not ip:
            self.log.error("IP address should be provided")
            return None

        interface_uuid = None

        if interface_name:
            interface_dict = self.list_ifs()
            interface_uuid = interface_dict[interface_name]

        if not bool(self.group.get_ip(interface_uuid, ip, format='num')):
            return None

        res = self.del_ip(interface_name)

        if res:
            return self.add_ip(interface_name, ip)

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
            return self.group.get_ip(interface_uuid, ipnum, format='human')

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
        return self.set('status', status)

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
                downloaded = tracker_record['downloaded']
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

    def release_resources(self):
        mac = self.get_mac()
        self._mongo_db['switch_mac'].remove({'mac': mac})
        self._mongo_db['mac'].remove({'mac': mac})

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
