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

    def __init__(self, name=None, mongo_db=None, create=False, id=None,
                 prescript='', bmcsetup=None, bmcnetwork=None,
                 partscript='', osimage=None, interfaces=[],
                 postscript='', boot_if=None, torrent_if=None):
        """
        prescript   - preinstall script
        bmcsetup    - bmcsetup options
        bmcnetwork  - used for bmc networking
        partscript  - parition script
        osimage     - osimage
        interfaces  - list of the newtork interfaces
        postscript  - postinstall script
        """

        self.log.debug("function args {}".format(self._debug_function()))

        # Define the schema used to represent group objects

        self._collection_name = 'group'
        self._keylist = {'prescript': type(''), 'partscript': type(''),
                         'postscript': type(''), 'boot_if': type(''),
                         'torrent_if': type('')}

        # Check if this group is already present in the datastore
        # Read it if that is the case

        group = self._get_object(name, mongo_db, create, id)

        if create:
            cluster = Cluster(mongo_db=self._mongo_db)
            osimageobj = OsImage(osimage, mongo_db=self._mongo_db)

            (bmcobj, bmcnetobj) = (None, None)
            if bmcsetup:
                bmcobj = BMCSetup(bmcsetup, mongo_db=self._mongo_db).DBRef

            if bmcnetwork:
                bmcnetobj = Network(bmcnetwork, mongo_db=self._mongo_db).DBRef

            if interfaces and type(interfaces) is not list:
                self.log.error("'interfaces' should be list")
                raise RuntimeError

            if_dict = {}
            for interface in interfaces:
                if_dict[uuid.uuid4().hex] = {'name': interface, 'network': None, 'params': ''}

            if not partscript:
                partscript = "mount -t tmpfs tmpfs /sysroot"

            if not postscript:
                postscript = ("cat << EOF >> /sysroot/etc/fstab\n"
                              "tmpfs   /       tmpfs    defaults        0 0\n"
                              "EOF")

            # Store the new group in the datastore

            group = {'name': name, 'prescript':  prescript, 'bmcsetup': bmcobj,
                     'bmcnetwork': bmcnetobj, 'partscript': partscript,
                     'osimage': osimageobj.DBRef, 'interfaces': if_dict,
                     'postscript': postscript, 'boot_if': boot_if,
                     'torrent_if': torrent_if}

            self.log.debug("Saving group '{}' to the datastore".format(group))

            self.store(group)

            # Link this group to its dependencies and the current cluster

            self.link(cluster)

            if bmcobj:
                self.link(bmcobj)

            if bmcnetobj:
                self.link(bmcnetobj)

            self.link(osimageobj)

        self.log = logging.getLogger('group.' + self._name)

    @property
    def boot_params(self):
        params = {}

        osimage = OsImage(id=self.get('osimage').id, mongo_db=self._mongo_db)
        params['kernel_file'] = osimage.get('kernfile')
        params['initrd_file'] = osimage.get('initrdfile')
        params['kern_opts'] = osimage.get('kernopts')

        params['boot_if'] = self.get('boot_if')
        params['net_prefix'] = ""


        if not params['boot_if']:
            return params

        if_list = self.list_ifs()

        if not params['boot_if'] in if_list.keys():
            params['boot_if'] = ""

            self.log.error(("Unknown boot interface '{}'. Must be one of '{}'"
                            .format(params['boot_if'], if_list.keys())))
            return params

        if_uuid = if_list[params['boot_if']]
        interfaces = self.get('interfaces')
        
        if 'network' in interfaces[if_uuid] and interfaces[if_uuid]['network']:
            net = Network(id=interfaces[if_uuid]['network'].id,
                          mongo_db=self._mongo_db)

            params['net_prefix'] = net.get('PREFIX')

        else:
            self.log.error(("Boot interface '{}' has no network configured"
                            .format(params['boot_if'])))
            params['boot_if'] = ""
        return params

    @property
    def install_params(self):
        params = {}
        params['prescript'] = self.get('prescript')
        params['partscript'] = self.get('partscript')
        params['postscript'] = self.get('postscript')
        params['boot_if'] = self.get('boot_if')
        params['torrent_if'] = self.get('torrent_if')
        params['torrent_if_net_prefix'] = ""

        interfaces = self.get('interfaces')
        if_list = self.list_ifs()
        if not params['torrent_if'] in if_list.keys():
            params['torrent_if'] = ""

        if not params['boot_if'] in if_list.keys():
            params['boot_if'] = ""

        torrent_if_uuid = None
        boot_if_uuid = None

        if params['torrent_if']:
            torrent_if_uuid = if_list[params['torrent_if']]

        if params['boot_if']:
            boot_if_uuid = if_list[params['boot_if']]

        if (torrent_if_uuid 
                and 'network' in interfaces[torrent_if_uuid]
                and interfaces[torrent_if_uuid]['network']):
            net = Network(id=interfaces[torrent_if_uuid]['network'].id,
                mongo_db=self._mongo_db)
            params['torrent_if_net_prefix'] = net.get('PREFIX')
        
        # unable to find net params for torrent_if,
        # drop it
        if not params['torrent_if_net_prefix']:
            params['torrent_if'] = ""

        if (boot_if_uuid
                and 'network' in interfaces[boot_if_uuid]
                and interfaces[boot_if_uuid]['network']):
            net = Network(id=interfaces[boot_if_uuid]['network'].id,
                          mongo_db=self._mongo_db)
            params['domain'] = net.name
        else:
            params['domain'] = ""

        # unable to find net params for boot_if,
        # drop it
        if not params['domain']:
            params['boot_if'] = ""

        params['interfaces'] = {}
        interfaces = self.get('interfaces')
        for nic_uuid in interfaces:
            nic_name = interfaces[nic_uuid]['name']
            params['interfaces'][nic_name] = self.get_if_params(nic_name).strip()
            net_prefix = ""

            if 'network' in interfaces[nic_uuid] and interfaces[nic_uuid]['network']:
                net = Network(id=interfaces[nic_uuid]['network'].id,
                              mongo_db=self._mongo_db)

                net_prefix = 'PREFIX=' + str(net.get('PREFIX'))

            params['interfaces'][nic_name] += '\n' + net_prefix

        osimage = OsImage(id=self.get('osimage').id, mongo_db=self._mongo_db)

        params['kernver'] = osimage.get('kernver')
        params['kernopts'] = osimage.get('kernopts')
        params['torrent'] = osimage.get('torrent')
        params['tarball'] = osimage.get('tarball')

        params['torrent'] += ".torrent" if params['torrent'] else ''
        params['tarball'] += ".tgz" if params['tarball'] else ''

        params['bmcsetup'] = {}
        if self.get('bmcsetup'):
            bmc = BMCSetup(id=self.get('bmcsetup').id, mongo_db=self._mongo_db)

            params['bmcsetup']['mgmtchannel'] = bmc.get('mgmtchannel') or 1
            params['bmcsetup']['netchannel'] = bmc.get('netchannel') or 1
            params['bmcsetup']['userid'] = bmc.get('userid') or 3
            params['bmcsetup']['user'] = bmc.get('user') or "ladmin"
            params['bmcsetup']['password'] = bmc.get('password') or "ladmin"
            params['bmcsetup']['netmask'] = ''

            bmcnet = self.get('bmcnetwork')
            if bmcnet:
                net = Network(id=bmcnet.id, mongo_db=self._mongo_db)
                params['bmcsetup']['netmask'] = net.get('NETMASK')

        return params

    def osimage(self, osimage_name):
        osimage = OsImage(osimage_name, mongo_db=self._mongo_db)

        old_image = self.get('osimage')
        self.unlink(old_image)

        res = self.set('osimage', osimage.DBRef)
        self.link(osimage.DBRef)

        return res

    def bmcsetup(self, bmcsetup_name = None):
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

    def set_bmcnetwork(self, bmcnet):
        net = self.get('bmcnetwork')
        if net:
            self.log.error("Network is already defined for BMC interface")
            return None

        net = Network(bmcnet, mongo_db=self._mongo_db)
        res = self.set('bmcnetwork', net.DBRef)
        self.link(net.DBRef)

        reverse_links = self.get_back_links()
        for link in reverse_links:
            if link['collection'] == 'node':
                node = Node(id=link['DBRef'].id, mongo_db=self._mongo_db)
                node.add_ip(bmc=True)

        return res

    def del_bmcnetwork(self):
        bmcnet = self.get('bmcnetwork')

        if bmcnet:
            reverse_links = self.get_back_links()
            for link in reverse_links:
                if link['collection'] == 'node':
                    node = Node(id=link['DBRef'].id, mongo_db=self._mongo_db)
                    node.del_ip(bmc=True)

            self.unlink(bmcnet)

        res = self.set('bmcnetwork', None)
        return res

    def show_bmc_if(self, brief=False):
        bmcnetwork = self.get('bmcnetwork')

        if bmcnetwork:
            net = Network(id=bmcnetwork.id, mongo_db=self._mongo_db)
            NETWORK = net.get('NETWORK')
            PREFIX = str(net.get('PREFIX'))

            if brief:
                return "[" + net.name + "]:" + NETWORK + "/" + PREFIX

            return NETWORK + "/" + PREFIX

        else:
            return ''

    def get_net_name_for_if(self, interface_name):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list:
            self.log.error("Interface '{}' does not exist".format(interface_name))
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
            self.log.error("Interface '{}' does not exist".format(interface_name))
            return None

        if interface_new_name in if_list.keys():
            self.log.error("Interface '{}' already exists".format(interface_new_name))
            return None

        interface_uuid = if_list[interface_name]
        interfaces[interface_uuid]['name'] = interface_new_name

        res = self.set('interfaces', interfaces)

        if not res:
            self.log.error("Could not rename interface '{}'".format(interface_name))

        return res

    def show_if(self, interface_name, brief=False):
        interfaces = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error("Interface '{}' does not exist".format(interface_name))
            return None
        outstr = ''
        interface_uuid = if_list[interface_name]
        assigned_net_dbref = interfaces[interface_uuid]['network']
        if assigned_net_dbref:
            assigned_net_obj = Network(id=assigned_net_dbref.id, mongo_db=self._mongo_db)
            NETWORK = assigned_net_obj.get('NETWORK')
            PREFIX = str(assigned_net_obj.get('PREFIX'))

            if brief:
                return "[" + assigned_net_obj.name + "]:" + NETWORK + "/" + PREFIX

            outstr = "NETWORK=" + NETWORK + "\n"
            outstr += "PREFIX=" + PREFIX

        if interfaces[interface_uuid]['params'] and not brief:
            outstr += "\n" + nic['params']

        return outstr.rstrip()

    def add_interface(self, interface_name):
        interface_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name in if_list.keys():
            self.log.error("Interface '{}' already exists".format(interface_name))
            return None

        interface_dict[uuid.uuid4().hex] = {'name': interface_name,
                                            'network': None,
                                            'params': ''}

        res = self.set('interfaces', interface_dict)

        if not res:
            self.log.error("Could not add interface '{}'".format(interface_name))

        return res

    def get_if_params(self, interface_name):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error("Interface '{}' does not exist".format(interface_name))
            return None
        interface_uuid = if_list[interface_name]
        return interfaces_dict[interface_uuid]['params']

    def set_if_params(self, interface_name, params=''):
        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()
        if interface_name not in if_list.keys():
            self.log.error("Interface '{}' does not exist".format(interface_name))
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

        bmcnet = self.get('bmcnetwork')
        if self.get(usedby_key) and bmcnet and bmcnet.id == net_id:
            for node_id in self.get(usedby_key)['node']:
                node = Node(id=ObjectId(node_id))
                add_to_dict(node.name, node.get_ip(bmc=True, format='num'))

        ifs = self.get('interfaces')
        if self.get(usedby_key) and ifs:
            for nic in ifs:
                if 'network' in ifs[nic] and ifs[nic]['network'].id == net_id:
                    for node_id in self.get(usedby_key)['node']:
                        node = Node(id=ObjectId(node_id))
                        add_to_dict(node.name, node.get_ip(nic, format='num'))

        return ips

    def set_net_to_if(self, interface_name, network_name):

        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error("Interface '{}' does not exist".format(interface_name))
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
            self.log.error("Interface '{}' does not exist".format(interface_name))
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
                           .format(interface))
            return False

        return True

    def del_interface(self, interface_name):
        self.del_net_from_if(interface_name, mute_error=True)

        interfaces_dict = self.get('interfaces')
        if_list = self.list_ifs()

        if interface_name not in if_list.keys():
            self.log.error("Interface '{}' does not exist".format(interface_name))
            return False

        interface_uuid = if_list[interface_name]

        interfaces_dict.pop(interface_uuid)

        res = self.set('interfaces', interfaces_dict)
        if not res:
            self.log.error("Error deleting interface '{}'".format(interface_name))
            return False

        return True

    def manage_ip(self, interface_uuid=None, ip=None, bmc=False, release=False):
        """
        operations with IP: add/delete
        """
        if bmc:
            net_dbref = self.get('bmcnetwork')
        elif self.get('interfaces') and interface_uuid in self.get('interfaces'):
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

    def get_ip(self, interface_uuid=None, ip=None, bmc=False, format='num'):
        """
        Convert from relative numbers to human-readable IPs and back
        """
        if not interface_uuid and not bmc:
            self.log.error("Interface should be specified")
            return None
        if not ip:
            self.log.error("IP should be specified")
            return None
        if bmc:
            net_dbref = self.get('bmcnetwork')
        elif self.get('interfaces') and interface_uuid in self.get('interfaces'):
            net_dbref = self.get('interfaces')[interface_uuid]['network']
        else:
            net_dbref = None

        if not net_dbref:
            interface_name = 'BMC'
            if interface_uuid:
                interface_name = self.get('interfaces')[interface_uuid]['name']
            self.log.warning("Network is not configured for {} interface"
                             .format(interface_name))
            return None

        net_obj = Network(id=net_dbref.id, mongo_db=self._mongo_db)

        if ip and format is 'human':
            return utils.ip.reltoa(net_obj._json['NETWORK'], ip)
        elif ip and format is 'num':
            return utils.ip.atorel(ip, net_obj._json['NETWORK'], net_obj.get('PREFIX'))

        return None

from luna.node import Node
