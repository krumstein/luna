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
import uuid

from bson.objectid import ObjectId

from luna import utils
from luna.base import Base
from luna.cluster import Cluster
from luna.network import Network
from luna.osimage import OsImage
from luna.bmcsetup import BMCSetup


class Group(Base):
    """Class for operating with group records"""

    log = logging.getLogger(__name__)

    def __init__(self, name=None, mongo_db=None, create=False,
                 id=None, prescript='', bmcsetup=None,
                 partscript='', osimage=None, interfaces=[],
                 postscript='', torrent_if=None, domain=None):
        """
        prescript   - preinstall script
        bmcsetup    - bmcsetup options
        partscript  - parition script
        osimage     - osimage
        interfaces  - list of the newtork interfaces
        postscript  - postinstall script
        """

        self.log.debug("function args {}".format(self._debug_function()))

        # Define the schema used to represent group objects

        self._collection_name = 'group'
        self._keylist = {'prescript': type(''), 'partscript': type(''),
                         'postscript': type(''), 'torrent_if': type('')}

        # Check if this group is already present in the datastore
        # Read it if that is the case

        group = self._get_object(name, mongo_db, create, id)

        if create:
            cluster = Cluster(mongo_db=self._mongo_db)
            osimageobj = OsImage(osimage, mongo_db=self._mongo_db)

            (bmcobj, bmcnetobj, domainobj) = (None, None, None)
            if bmcsetup:
                bmcobj = BMCSetup(bmcsetup, mongo_db=self._mongo_db).DBRef

            if domain:
                domainobj = Network(domain, mongo_db=self._mongo_db).DBRef

            if interfaces and type(interfaces) is not list:
                self.log.error("'interfaces' should be list")
                raise RuntimeError

            if not interfaces:
                interfaces = []

            if_dict = {}
            for interface in interfaces:
                if_dict[uuid.uuid4().hex] = {
                    'name': interface,
                    'network': None,
                    'params': ''
                }

            if not partscript:
                partscript = "mount -t tmpfs tmpfs /sysroot"

            if not postscript:
                postscript = ("cat << EOF >> /sysroot/etc/fstab\n"
                              "tmpfs   /       tmpfs    defaults        0 0\n"
                              "EOF")

            # Store the new group in the datastore

            group = {'name': name, 'prescript':  prescript,
                'bmcsetup': bmcobj, 'partscript': partscript,
                'osimage': osimageobj.DBRef, 'interfaces': if_dict,
                'postscript': postscript, 'domain': domainobj,
                'torrent_if': torrent_if
            }

            self.log.debug("Saving group '{}' to the datastore".format(group))

            self.store(group)

            # Link this group to its dependencies and the current cluster

            self.link(cluster)

            if bmcobj:
                self.link(bmcobj)

            if domainobj:
                self.link(domainobj)

            self.link(osimageobj)

        self.log = logging.getLogger('group.' + self._name)

    @property
    def boot_params(self):
        params = {}

        osimage = OsImage(id=self.get('osimage').id, mongo_db=self._mongo_db)
        params['kernel_file'] = osimage.get('kernfile')
        params['initrd_file'] = osimage.get('initrdfile')
        params['kern_opts'] = osimage.get('kernopts')
        params['domain'] = ''
        params['net_prefix'] = ''
        params['net_mask'] = ''

        domaindbref = self.get('domain')

        if domaindbref:

            domainnet = Network(
                id=domaindbref.id,
                mongo_db=self._mongo_db
            )

            params['domain'] = domainnet.name

        if_list = self.list_ifs()
        bootif_uuid = None

        if 'BOOTIF' in if_list:
            bootif_uuid = if_list['BOOTIF']

        if not bootif_uuid:
            return params

        interfaces = self.get('interfaces')
        if ('network' in interfaces[bootif_uuid]
                and interfaces[bootif_uuid]['network']):
            net = Network(
                id=interfaces[bootif_uuid]['network'].id,
                mongo_db=self._mongo_db
            )
            params['net_prefix'] = str(net.get('PREFIX'))
            params['net_mask'] = str(net.get('NETMASK'))

        return params

    @property
    def install_params(self):
        params = {}
        params['prescript'] = self.get('prescript')
        params['partscript'] = self.get('partscript')
        params['postscript'] = self.get('postscript')
        params['torrent_if'] = self.get('torrent_if')
        params['domain'] = ""

        domaindbref = self.get('domain')

        if domaindbref:
            domainnet = Network(
                id=domaindbref.id,
                mongo_db=self._mongo_db
            )

            params['domain'] = domainnet.name

        interfaces = self.get('interfaces')
        if_list = self.list_ifs()

        # now find torrent_if name and net prefix

        if not params['torrent_if'] in if_list.keys():
            params['torrent_if'] = ""

        torrent_if_uuid = None

        if params['torrent_if']:
            torrent_if_uuid = if_list[params['torrent_if']]

        net_for_torrent_if = False
        if (torrent_if_uuid
                and 'network' in interfaces[torrent_if_uuid]
                and interfaces[torrent_if_uuid]['network']):
            net = Network(
                id=interfaces[torrent_if_uuid]['network'].id,
                mongo_db=self._mongo_db
            )
            net_for_torrent_if = True

        # unable to find net params for torrent_if,
        # drop it
        if not net_for_torrent_if:
            params['torrent_if'] = ""

        params['interfaces'] = {}

        for nic_uuid in interfaces:
            nic_name = interfaces[nic_uuid]['name']
            nicopts = self.get_if_params(nic_name).strip()

            params['interfaces'][nic_name] = {}

            params['interfaces'][nic_name]['options'] = nicopts
            net_prefix = ""
            net_mask = ""

            if ('network' in interfaces[nic_uuid]
                    and interfaces[nic_uuid]['network']):
                net = Network(id=interfaces[nic_uuid]['network'].id,
                              mongo_db=self._mongo_db)

                net_prefix = str(net.get('PREFIX'))
                net_mask = str(net.get('NETMASK'))

            params['interfaces'][nic_name]['prefix'] = net_prefix
            params['interfaces'][nic_name]['netmask'] = net_mask

        osimage = OsImage(id=self.get('osimage').id, mongo_db=self._mongo_db)

        params['kernver'] = osimage.get('kernver')
        params['kernopts'] = osimage.get('kernopts')
        params['torrent'] = osimage.get('torrent')
        params['tarball'] = osimage.get('tarball')

        if params['torrent']:
            params['torrent'] += ".torrent"
        else:
            params['torrent'] = ''

        if params['tarball']:
            params['tarball'] += ".tgz"
        else:
            params['tarball'] = ''

        params['bmcsetup'] = {}
        if self.get('bmcsetup'):

            bmc = BMCSetup(id=self.get('bmcsetup').id, mongo_db=self._mongo_db)
            params['bmcsetup']['mgmtchannel'] = bmc.get('mgmtchannel') or 1
            params['bmcsetup']['netchannel'] = bmc.get('netchannel') or 1
            params['bmcsetup']['userid'] = bmc.get('userid') or 3
            params['bmcsetup']['user'] = bmc.get('user') or "ladmin"
            params['bmcsetup']['password'] = bmc.get('password') or "ladmin"

        return params

    def osimage(self, osimage_name):
        osimage = OsImage(osimage_name, mongo_db=self._mongo_db)

        old_image = self.get('osimage')
        self.unlink(old_image)

        res = self.set('osimage', osimage.DBRef)
        self.link(osimage.DBRef)

        return res

    def bmcsetup(self, bmcsetup_name=None):
        bmcsetup = None
        old_bmc = self.get('bmcsetup')

        if bmcsetup_name:
            bmcsetup = BMCSetup(bmcsetup_name, mongo_db=self._mongo_db)

        if old_bmc:
            self.unlink(old_bmc)

        if bmcsetup:
            res = self.set('bmcsetup', bmcsetup.DBRef)
            self.link(bmcsetup.DBRef)
        else:
            res = self.set('bmcsetup', None)

        return res

    def get_net_name_for_if(self, interface_name):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list:
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return ''

        nic_uuid = if_list[interface_name]
        nic = interfaces_dict[nic_uuid]
        if nic['network']:
            net = Network(id=nic['network'].id, mongo_db=self._mongo_db)
            return net.name
        else:
            return ''

    def list_ifs(self):
        """
        Inverts 'interfaces' dictionary
        Returns dictionary like {'eth0': 'uuid'}
        """
        interfaces = self.get('interfaces')
        if_list = {}
        for elem in interfaces:
            if_list[interfaces[elem][u'name']] = elem
        return if_list

    def rename_interface(self, interface_name, interface_new_name):
        interfaces = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return None

        if interface_new_name in if_list.keys():
            self.log.error(
                "Interface '{}' already exists".format(interface_new_name)
            )
            return None

        interface_uuid = if_list[interface_name]
        interfaces[interface_uuid]['name'] = interface_new_name

        res = self.set('interfaces', interfaces)

        if not res:
            self.log.error(
                "Could not rename interface '{}'".format(interface_name)
            )

        return res

    def show_if(self, interface_name, brief=False):
        interfaces = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return None
        outstr = ''
        interface_uuid = if_list[interface_name]
        assigned_net_dbref = interfaces[interface_uuid]['network']
        if assigned_net_dbref:
            assigned_net_obj = Network(
                id=assigned_net_dbref.id,
                mongo_db=self._mongo_db
            )
            NETWORK = assigned_net_obj.get('NETWORK')
            PREFIX = str(assigned_net_obj.get('PREFIX'))

            if brief:
                outstr = (
                    "[" + assigned_net_obj.name + "]:"
                    + NETWORK + "/" + PREFIX
                )
                return outstr

            outstr = "NETWORK=" + NETWORK + "\n"
            outstr += "PREFIX=" + PREFIX

        if interfaces[interface_uuid]['params'] and not brief:
            outstr += "\n" + nic['params']

        return outstr.rstrip()

    def add_interface(self, interface_name):
        interface_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name in if_list.keys():
            self.log.error(
                "Interface '{}' already exists".format(interface_name)
            )
            return None

        interface_dict[uuid.uuid4().hex] = {'name': interface_name,
                                            'network': None,
                                            'params': ''}

        res = self.set('interfaces', interface_dict)

        if not res:
            self.log.error(
                "Could not add interface '{}'".format(interface_name)
            )

        return res

    def get_if_params(self, interface_name):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return None
        interface_uuid = if_list[interface_name]
        return interfaces_dict[interface_uuid]['params']

    def set_if_params(self, interface_name, params=''):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return None

        interface_uuid = if_list[interface_name]
        interfaces_dict[interface_uuid]['params'] = params.strip()
        res = self.set('interfaces', interfaces_dict)

        if not res:
            self.log.error("Could not configure '{}'".format(interface_name))

        return res

    def get_allocated_ips(self, net_id):
        ips = {}

        def add_to_dict(key, val):
            if key in ips:
                self.log.error(("Duplicate IP detected in the group '{}'."
                                "Could not process '{}'")
                               .format(self.name, key))
            else:
                ips[key] = val

        ifs = self.get('interfaces')
        if self.get(usedby_key) and ifs:
            for if_uuid in ifs:
                if_name = ifs[if_uuid]['name']
                if ('network' in ifs[if_uuid]
                        and ifs[if_uuid]['network']
                        and ifs[if_uuid]['network'].id == net_id):
                    for node_id in self.get(usedby_key)['node']:
                        node_id = ObjectId(node_id)
                        node = Node(
                            id=node_id,
                            group=self,
                            mongo_db=self._mongo_db,
                        )
                        add_to_dict(
                            node.name,
                            node.get_ip(if_name, format='num')
                        )

        return ips

    def set_net_to_if(self, interface_name, network_name):

        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return False

        interface_uuid = if_list[interface_name]

        if interfaces_dict[interface_uuid]['network']:
            self.log.error("Network is already defined for interface '{}'"
                           .format(interface_name))
            return False

        network_obj = Network(network_name, mongo_db=self._mongo_db)
        interfaces_dict[interface_uuid]['network'] = network_obj.DBRef

        res = self.set('interfaces', interfaces_dict)

        if not res:
            self.log.error("Error adding network for interface '{}'"
                           .format(interface_name))
            return False

        self.link(network_obj)

        reverse_links = self.get_back_links()

        # Now we need to assign ip for every node in group
        # TODO sort nodes
        for link in reverse_links:
            if link['collection'] == 'node':
                node_obj = Node(id=link['DBRef'].id, mongo_db=self._mongo_db)
                node_obj.add_ip(interface_name)

        return True

    def del_net_from_if(self, interface_name, mute_error=False):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return False

        interface_uuid = if_list[interface_name]
        if not interfaces_dict[interface_uuid]['network']:
            if not mute_error:
                self.log.error("Network is not configured for interface '{}'"
                               .format(interface_name))
            return False

        reverse_links = self.get_back_links()
        for link in reverse_links:
            if link['collection'] == 'node':
                node = Node(id=link['DBRef'].id, mongo_db=self._mongo_db)
                node.del_ip(interface_name)

        self.unlink(interfaces_dict[interface_uuid]['network'])
        interfaces_dict[interface_uuid]['network'] = None
        res = self.set('interfaces', interfaces_dict)
        if not res:
            self.log.error("Error deleting network for interface '{}'"
                           .format(interface_name))
            return False

        return True

    def del_interface(self, interface_name):
        self.del_net_from_if(interface_name, mute_error=True)

        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error(
                "Interface '{}' does not exist".format(interface_name)
            )
            return False

        interface_uuid = if_list[interface_name]

        interfaces_dict.pop(interface_uuid)

        res = self.set('interfaces', interfaces_dict)
        if not res:
            self.log.error(
                "Error deleting interface '{}'".format(interface_name)
            )
            return False

        return True

    def manage_ip(self, interface_uuid=None,
            ip=None, release=False):
        """
        operations with IP: add/delete
        """
        if (self.get('interfaces')
                and interface_uuid in self.get('interfaces')):
            net_dbref = self.get('interfaces')[interface_uuid]['network']
        else:
            net_dbref = None

        if not net_dbref:
            #self.log.warning("Network is not configured for {} interface"
            #                 .format(interface_uuid or 'BMC'))
            return None

        net_obj = Network(id=net_dbref.id, mongo_db=self._mongo_db)

        if release and ip:
            return net_obj.release_ip(ip)

        else:
            return net_obj.reserve_ip(ip)

    def get_ip(self, interface_uuid=None, ip=None, format='num'):
        """
        Convert from relative numbers to human-readable IPs and back
        """
        if not interface_uuid:
            self.log.error("Interface should be specified")
            return None

        if not ip:
            self.log.error("IP should be specified")
            return None

        if (self.get('interfaces')
                and interface_uuid in self.get('interfaces')):
            net_dbref = self.get('interfaces')[interface_uuid]['network']
        else:
            net_dbref = None

        if not net_dbref:
            interface_name = ''
            if interface_uuid:
                interface_name = self.get('interfaces')[interface_uuid]['name']
            self.log.warning("Network is not configured for {} interface"
                             .format(interface_name))
            return None

        net_obj = Network(id=net_dbref.id, mongo_db=self._mongo_db)

        if ip and format is 'human':
            iphuman = utils.ip.reltoa(net_obj._json['NETWORK'], ip)
            return iphuman

        elif ip and format is 'num':
            ipnum = utils.ip.atorel(
                ip,
                net_obj._json['NETWORK'],
                net_obj.get('PREFIX')
            )
            return ipnum

        return None

    def set_domain(self, domain_name=None):

        newnet, oldnet = None, None
        newnet_dbref = None

        if domain_name:
            newnet = Network(name=domain_name, mongo_db=self._mongo_db)
            newnet_dbref = newnet.DBRef

        if 'domain' in self._json and self._json['domain']:
            oldnet = Network(
                id=self._json['domain'].id,
                mongo_db=self._mongo_db
            )

        if oldnet:
            self.unlink(oldnet)

        if newnet:
            self.link(newnet)

        self.set('domain', newnet_dbref)

        return True

from luna.node import Node
