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
from config import usedby_key

import logging

from bson.objectid import ObjectId

from luna import utils
from luna.base import Base
from luna.cluster import Cluster


class Network(Base):
    """Class for operating with network objects"""

    log = logging.getLogger(__name__)

    def __init__(self, name=None, mongo_db=None,
                 create=False, id=None, version=None,
                 NETWORK=None, PREFIX=None,
                 ns_hostname=None, ns_ip=None):
        """
        create  - should be True if we need create a network
        NETWORK - network
        PREFIX  - the prefix in a networks CIDR format
        """

        self.log.debug("function {} args".format(self._debug_function()))

        # Define the schema used to represent network objects

        self._collection_name = 'network'
        self._keylist = {'NETWORK': long, 'PREFIX': int,
                         'ns_hostname': type(''), 'include': str}

        # Check if this network is already present in the datastore
        # Read it if that is the case

        net = self._get_object(name, mongo_db, create, id)

        if create:
            if not version:
                version = utils.ip.get_ip_version(NETWORK)
                if version == 0:
                    self.log.error("Unable to determine protocol " +
                                   "version for given network")
                    raise RuntimeError

            if version not in [4, 6]:
                self.log.error("IP version should be 4 or 6")
                raise RuntimeError

            maxbits = 32
            if version == 6:
                maxbits = 128

            self.version = version
            self.maxbits = maxbits

            cluster = Cluster(mongo_db=self._mongo_db)
            num_subnet = utils.ip.get_num_subnet(NETWORK, PREFIX, self.version)

            flist = self._flist_to_str([{
                'start': 1,
                'end': (1 << (self.maxbits - int(PREFIX))) - 2
            }])

            # Try to guess the nameserver hostname if none provided

            if not ns_hostname:
                ns_hostname = utils.ip.guess_ns_hostname()

            # Store the new network in the datastore
            if self.version == 6:
                num_subnet = str(num_subnet)

            net = {'name': name, 'NETWORK': num_subnet, 'PREFIX': PREFIX,
                   'freelist': flist, 'ns_hostname': ns_hostname,
                   'ns_ip': None, 'version': version, 'include': None}

            self.log.debug("Saving net '{}' to the datastore".format(net))

            self.store(net)
            self._convert_to_int()

            # Link this network to the current cluster

            self.link(cluster)

            # If no IP address is provided for the nameserver, default to
            # the cluster's frontend address

            if ns_ip is None:
                ns_ip = utils.ip.reltoa(num_subnet,
                                            int(flist[0]['end']),
                                            self.version)

            self.set('ns_ip', ns_ip)

        self.version = self._json['version']
        self.maxbits = 32
        if self.version == 6:
            self.maxbits = 128
        self._convert_to_int()

        self.log = logging.getLogger(__name__ + '.' + self._name)

    def _convert_to_int(self):
        """
        Converting self._json from strings to integers
        This is required, as mongo is unable to sore int representation
        of IPv6
        """

        if self.version == 4:
            return None

        self._json['NETWORK'] = int(self._json['NETWORK'])
        flist = []
        for elem in self._json['freelist']:
            start = elem['start']
            end = elem['end']
            flist.append({
                'start': int(start),
                'end': int(end)
            })
        if self._json['ns_ip']:
            self._json['ns_ip'] = int(self._json['ns_ip'])
        self._json['freelist'] = flist

    def _nsip_to_str(self, ip):
        """
        Convert ns_ip to strings for IPv6
        """
        if self.version == 4:
            return ip
        return str(ip)

    def _flist_to_str(self, flist):
        """
        Convert flist's interegers to strings for IPv6
        """
        if self.version == 4:
            return flist
        new_flist = []
        for elem in flist:
            new_elem = {
                'start': str(elem['start']),
                'end': str(elem['end'])
            }
            new_flist.append(new_elem)
        return new_flist

    def set(self, key, value):
        self._convert_to_int()
        net = self._json

        if key == 'ns_ip':

            rel_ns_ip = utils.ip.atorel(
                value, net['NETWORK'], net['PREFIX'], self.version
            )

            old_ip = net['ns_ip']

            if old_ip:
                self.release_ip(old_ip)

            self.reserve_ip(rel_ns_ip)

            if self.version == 6:
                rel_ns_ip = str(rel_ns_ip)

            ret = super(Network, self).set('ns_ip', rel_ns_ip)

        elif key == 'NETWORK':
            prefix = net['PREFIX']
            num_subnet = utils.ip.get_num_subnet(
                value, prefix, self.version
            )

            ret = super(Network, self).set('NETWORK', str(num_subnet))

        elif key == 'PREFIX':
            num_subnet = net['NETWORK']
            new_num_subnet = utils.ip.get_num_subnet(
                num_subnet, value, self.version
            )

            limit = (1 << (self.maxbits - value)) - 1
            flist = utils.freelist.set_upper_limit(net['freelist'], limit)

            ret = super(Network, self).set('freelist', flist)
            ret &= super(Network, self).set('NETWORK', new_num_subnet)
            ret &= super(Network, self).set('PREFIX', value)

        else:
            ret = super(Network, self).set(key, value)

        self._convert_to_int()
        return ret

    def get(self, key):
        self._convert_to_int()
        net = self._json

        if key == 'NETWORK':
            value = utils.ip.ntoa(
                net[key], self.version
            )

        elif key == 'NETMASK':
            prefix = int(net['PREFIX'])
            num_mask = (((1 << self.maxbits) - 1)
                        ^ ((1 << (self.maxbits+1 - prefix) - 1) - 1)
                        )

            value = utils.ip.ntoa(
                num_mask, self.version
            )

        elif key == 'ns_ip':
            value = utils.ip.reltoa(
                net['NETWORK'], net['ns_ip'], self.version
            )

        else:
            value = super(Network, self).get(key)

        return value

    def reserve_ip(self, ip1=None, ip2=None, ignore_errors=True):
        self._convert_to_int()
        net = self._json

        if type(ip1) is str:
            ip1 = utils.ip.atorel(
                ip1, net['NETWORK'], net['PREFIX'], self.version
            )

        if type(ip2) is str:
            ip2 = utils.ip.atorel(
                ip2, net['NETWORK'], net['PREFIX'], self.version
            )

        if bool(ip2) and ip2 <= ip1:
            self.log.error("Wrong range definition.")
            return None

        if bool(ip1):
            flist, unfreed = utils.freelist.unfree_range(net['freelist'],
                                                         ip1, ip2)

        elif ignore_errors:
            flist, unfreed = utils.freelist.next_free(net['freelist'])

        self.set('freelist', self._flist_to_str(flist))

        return unfreed

    def release_ip(self, ip1, ip2=None):
        net = self._json
        self._convert_to_int()

        if type(ip1) is str:
            ip1 = utils.ip.atorel(
                ip1, net['NETWORK'], net['PREFIX'], self.version
            )

        if type(ip2) is str:
            ip2 = utils.ip.atorel(
                ip2, net['NETWORK'], net['PREFIX'], self.version
            )

        if bool(ip2) and ip2 <= ip1:
            self.log.error("Wrong range definition.")
            return None

        flist, freed = utils.freelist.free_range(net['freelist'], ip1, ip2)
        self.set('freelist', self._flist_to_str(flist))

        return True

    def resolve_used_ips(self):
        from luna.switch import Switch
        from luna.otherdev import OtherDev
        from luna.node import Group

        net = self._json

        try:
            rev_links = net[usedby_key]
        except:
            self.log.error(("No IPs configured for network '{}'"
                            .format(self.name)))
            return {}

        out_dict = {}

        def add_to_out_dict(name, relative_ip):
            try:
                out_dict[name]
                self.log.error(("Duplicate name '{}' in network '{}'"
                                .format(name, self.name)))
            except:
                out_dict[name] = utils.ip.reltoa(
                    net['NETWORK'], relative_ip, self.version
                )

        for elem in rev_links:
            if elem == "group":
                for gid in rev_links[elem]:
                    group = Group(id=ObjectId(gid), mongo_db=self._mongo_db)
                    tmp_dict = group.get_allocated_ips(self)
                    if not tmp_dict:
                        continue

                    for nodename in tmp_dict:
                        add_to_out_dict(nodename, tmp_dict[nodename])

            if elem == "switch":
                for sid in rev_links[elem]:
                    switch = Switch(id=ObjectId(sid), mongo_db=self._mongo_db)
                    add_to_out_dict(switch.name, switch.get_rel_ip())

            if elem == "otherdev":
                for oid in rev_links[elem]:
                    odev = OtherDev(id=ObjectId(oid), mongo_db=self._mongo_db)
                    add_to_out_dict(odev.name, odev.get_ip(self.id))

        add_to_out_dict(net['ns_hostname'], net['ns_ip'])

        return out_dict
