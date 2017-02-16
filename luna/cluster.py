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

import os
import pwd
import grp
import errno
import base64
import logging
import subprocess

from bson.objectid import ObjectId
from bson.dbref import DBRef
from tornado import template

from luna.base import Base
from luna import utils


class Cluster(Base):
    """
    Class for storing options and procedures for luna
    TODO rename to 'Cluster'
    """

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    _mongo_collection = None
    _keylist = None
    _id = None
    _name = None
    _DBRef = None
    _json = None

    def __init__(self, mongo_db=None, create=False, id=None,
                 nodeprefix='node', nodedigits=3, path=None, user=None):
        """
        Constructor can be used for creating object by setting create=True
        nodeprefix='node' and nodedigits='3' will give names like node001,
        nodeprefix='compute' and nodedigits='2' will give names like compute01
        """

        self.log.debug("function args {}".format(self._debug_function()))

        self._collection_name = 'cluster'
        self._keylist = {'nodeprefix': type(''),
                         'nodedigits': type(0),
                         'debug': type(0),
                         'user': type(''),
                         'path': type(''),
                         'frontend_address': type(''),
                         'frontend_port': type(0),
                         'server_port': type(0),
                         'tracker_interval': type(0),
                         'tracker_min_interval': type(0),
                         'tracker_maxpeers': type(0),
                         'torrent_listen_port_min': type(0),
                         'torrent_listen_port_max': type(0),
                         'torrent_pidfile': type(''),
                         'lweb_pidfile': type(''),
                         'lweb_num_proc': type(0),
                         'cluster_ips': type(''),
                         'named_include_file': type(''),
                         'named_zone_dir': type(''),
                         'dhcp_range_start': long,
                         'dhcp_range_end': long,
                         'dhcp_net': type('')}

        cluster = self._get_object('general', mongo_db, create, id)

        if create:
            try:
                path = os.path.abspath(path)
            except:
                self._logger.error("No path specified.")
                raise RuntimeError
            if not os.path.exists(path):
                self._logger.error("Wrong path '{}' specified.".format(path))
                raise RuntimeError

            try:
                user_id = pwd.getpwnam(user)
            except KeyError:
                self.log.error("No such user '{}' exists.".format(user))
                raise RuntimeError

            try:
                group = grp.getgrgid(user_id.pw_gid).gr_name
                group_id = grp.getgrnam(group)
            except KeyError:
                self.log.error("No such group '{}' exists.".format(group))
                raise RuntimeError

            path_stat = os.stat(path)
            if (path_stat.st_uid != user_id.pw_uid or
                    path_stat.st_gid != group_id.gr_gid):
                self.log.error("Path is not owned by '{}:{}'"
                               .format(user, group))
                raise RuntimeError

            cluster = {'name': 'general',
                       'nodeprefix': nodeprefix,
                       'nodedigits': nodedigits,
                       'user': user, 'debug': 0,
                       'path': path,
                       'cluster_ips': None,
                       'frontend_address': '',
                       'frontend_port': '7050',
                       'server_port': 7051,
                       'torrent_listen_port_min': 7052,
                       'torrent_listen_port_max': 7200,
                       'torrent_pidfile': '/run/luna/ltorrent.pid',
                       'tracker_interval': 10,
                       'tracker_min_interval': 5,
                       'tracker_maxpeers': 200,
                       'lweb_num_proc': 0,
                       'lweb_pidfile': '/run/luna/lweb.pid',
                       'named_include_file': '/etc/named.luna.zones',
                       'named_zone_dir': '/var/named',
                       'dhcp_range_start': None,
                       'dhcp_range_end': None,
                       'dhcp_net': None}

            self.log.debug("Saving cluster '{}' to the datastore"
                           .format(cluster))

            self.store(cluster)

            try:
                logdir = os.environ['LUNA_LOGDIR']
            except KeyError:
                logdir = '/var/log/luna'

            try:
                os.makedirs(logdir)
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir(logdir):
                    pass
                else:
                    raise

            os.chown(logdir, user_id.pw_uid, group_id.gr_gid)

    def get(self, key):
        from luna.network import Network

        if key == 'dhcp_net':
            netid = super(Cluster, self).get(key)
            if not netid:
                return None

            net = Network(id=ObjectId(netid), mongo_db=self._mongo_db)
            try:
                net = Network(id=ObjectId(netid), mongo_db=self._mongo_db)
                return net.name
            except:
                self.log.error('Wrong DHCP network configured')
                return None

        if key == 'dhcp_range_start' or key == 'dhcp_range_end':
            netid = super(Cluster, self).get('dhcp_net')
            if not netid:
                return None

            net = Network(id=ObjectId(netid), mongo_db=self._mongo_db)
            return utils.ip.reltoa(net._json['NETWORK'],
                                   super(Cluster, self).get(key))

        return super(Cluster, self).get(key)

    def set(self, key, value):
        if key == 'path':
            try:
                value = os.path.abspath(value)
            except:
                self.log.error("No path specified.")
                return None
            if not os.path.exists(value):
                self.log.error("Wrong path specified.")
                return None

        elif key in ['server_address', 'tracker_address']:
            try:
                utils.ip.aton(value)
            except:
                self.log.error("Wrong ip address specified.")
                return None

        elif key == 'user':
            try:
                pwd.getpwnam(value)
            except:
                self.log.error("No such user exists.")
                return None

        elif key == 'cluster_ips':
            val = ''
            for ip in value.split(","):
                try:
                    utils.ip.aton(ip.strip())
                    val += ip + ','
                except:
                    self.log.error("Wrong ip address specified.")
                    return None

            value = val[:-1]

        return super(Cluster, self).set(key, value)

    def makedhcp(self, netname, startip, endip, no_ha=False):
        from luna.network import Network

        try:
            if netname:
                objnet = Network(name=netname, mongo_db=self._mongo_db)
        except:
            objnet = None

        if not objnet:
            self.log.error("Proper DHCP network should be specified.")
            return None

        if not startip or not endip:
            self.log.error("First and last IPs of range should be specified.")
            return None

        if not self.get_cluster_ips():
            no_ha = True

        startip = utils.ip.atorel(startip, objnet._json['NETWORK'],
                                  objnet._json['PREFIX'])
        endip = utils.ip.atorel(endip, objnet._json['NETWORK'],
                                objnet._json['PREFIX'])

        if not startip or not endip:
            self.log.error("Error in acquiring IPs.")
            return None

        oldnetid = self._json['dhcp_net']
        oldstartip = self._json['dhcp_range_start']
        oldendip = self._json['dhcp_range_end']

        if str(oldnetid) == str(objnet.id):
            objnet.release_ip(oldstartip, oldendip)
            self.unlink(objnet)
            (oldnetid, oldstartip, oldendip) = (None, None, None)

        res = objnet.reserve_ip(startip, endip)
        if not res:
            self.log.error("Cannot reserve IP range for DHCP.")

        super(Cluster, self).set('dhcp_net', str(objnet.id))
        super(Cluster, self).set('dhcp_range_start', startip)
        super(Cluster, self).set('dhcp_range_end', endip)
        self.link(objnet)

        if oldnetid and oldstartip and oldendip:
            oldnet = Network(id=ObjectId(oldnetid), mongo_db=self._mongo_db)
            self.unlink(oldnet)
            oldnet.release_ip(oldstartip, oldendip)

        self._create_dhcp_config(no_ha)

        return True

    def _create_dhcp_config(self, no_ha):
        from luna.network import Network

        c = {}
        conf_primary = {}
        conf_secondary = {}

        if self.is_ha() and not no_ha:
            cluster_ips = self.get_cluster_ips()
            conf_primary['my_addr'] = cluster_ips[0]
            conf_secondary['my_addr'] = cluster_ips[1]
            conf_primary['peer_addr'] = conf_secondary['my_addr']
            conf_secondary['peer_addr'] = conf_primary['my_addr']

        c['frontend_ip'] = self.get('frontend_address')
        c['dhcp_start'] = self.get('dhcp_range_start')
        c['dhcp_end'] = self.get('dhcp_range_end')
        c['frontend_port'] = self.get('frontend_port')
        netname = self.get('dhcp_net')
        objnet = Network(name=netname, mongo_db=self._mongo_db)
        c['NETMASK'] = objnet.get('NETMASK')
        c['NETWORK'] = objnet.get('NETWORK')
        c['hmac_key'] = str(base64.b64encode(bytearray(os.urandom(32))).decode())
        tloader = template.Loader(self.get('path') + '/templates')
        if self.is_ha() and not no_ha:
            dhcpd_conf_primary = tloader.load('templ_dhcpd.cfg').generate(c=c, conf_primary=conf_primary, conf_secondary=None)
            dhcpd_conf_secondary = tloader.load('templ_dhcpd.cfg').generate(c=c, conf_primary=None, conf_secondary=conf_secondary)
            f1 = open('/etc/dhcp/dhcpd.conf', 'w')
            f2 = open('/etc/dhcp/dhcpd-secondary.conf', 'w')
            f1.write(dhcpd_conf_primary)
            f2.write(dhcpd_conf_secondary)
            f1.close()
            f2.close()
        else:
            dhcpd_conf = tloader.load('templ_dhcpd.cfg').generate(c=c, conf_primary=None, conf_secondary=None)
            f1 = open('/etc/dhcp/dhcpd.conf', 'w')
            f2 = open('/etc/dhcp/dhcpd-secondary.conf', 'w')
            f1.write(dhcpd_conf)
            f2.write(dhcpd_conf)
            f1.close()
            f2.close()
        return True

    def get_cluster_ips(self):
        cluster_ips = []
        ips = self.get('cluster_ips')

        if ips == '':
            self.log.info('No cluster IPs are configured.')
            return cluster_ips

        ips = ips.split(",")

        local_ip = ''
        for ip in ips:
            stdout = subprocess.Popen(['/usr/sbin/ip', 'addr',
                                       'show', 'to', ip],
                                      stdout=subprocess.PIPE).stdout.read()
            if not stdout == '':
                local_ip = ip
                break

        if not local_ip:
            self.log.info('No proper cluster IPs are configured.')
            return cluster_ips

        cluster_ips.append(local_ip)
        for ip in ips:
            if not ip == local_ip:
                cluster_ips.append(ip)

        return cluster_ips

    def is_active(self):
        cluster_ips = self.get('cluster_ips')

        if not cluster_ips:
            return True

        ip = self.get('frontend_address')
        if not ip:
            return True

        stdout = subprocess.Popen(['/usr/sbin/ip', 'addr',
                                   'show', 'to', ip],
                                  stdout=subprocess.PIPE).stdout.read()
        if stdout:
            return True

        return False

    def is_ha(self):
        try:
            cluster_ips = self.get('cluster_ips')
        except:
            return False

        if cluster_ips:
            return True
        return False

    def makedns(self):
        from luna.network import Network

        rlinks = self.get(usedby_key)
        if not rlinks or 'network' not in rlinks or not rlinks['network']:
            self.log.error("No networks configured in this cluster")
            return None

        netids = []
        for netid in rlinks['network']:
            netids.append(netid)

        # fill network dictionary
        # {'netname': {'ns_hostname': 'servername', 'ns_ip': 'IP',
        #              'hosts' {'name': 'IP'}}}
        networks = {}
        for netid in netids:
            netobj = Network(id=ObjectId(netid))
            networks[netobj.name] = {}
            master_ip = netobj.get('ns_ip')
            networks[netobj.name]['ns_hostname'] = netobj.get('ns_hostname')
            networks[netobj.name]['ns_ip'] = master_ip
            networks[netobj.name]['hosts'] = netobj.resolve_used_ips()

            # some inout for reverse zones
            # here is steps to figure out which octets in ipadresses
            # are common for all ips in network.
            # we can not rely on mask here, as mask can not be devisible
            # by 8 (/12, /15, /21, etc)

            arr1 = [int(elem) for elem in master_ip.split('.')]
            logical_arr1 = [True, True, True, True]
            for host in networks[netobj.name]['hosts']:
                ip = networks[netobj.name]['hosts'][host]
                arr2 = [int(elem) for elem in ip.split('.')]
                logical_arr = [bool(arr1[n] == arr2[n]) for n in range(len(arr1))]
                logical_arr2 = [logical_arr[n] & logical_arr1[n] for n in range(len(logical_arr))]
                arr1 = arr2[:]
                logical_arr1 = logical_arr2[:]
            # get fist octet in ip adresses which is changing
            try:
                mutable_octet = [i for i in range(len(logical_arr1)) if not logical_arr1[i]][0]
            except IndexError:
                mutable_octet = 3
            # generate zone file name
            revzonename = '.'.join(list(reversed(master_ip.split('.')[:mutable_octet]))) + ".in-addr.arpa"
            networks[netobj.name]['mutable_octet'] = mutable_octet
            networks[netobj.name]['rev_zone_name'] = revzonename

        # figure out paths
        includefile = self.get('named_include_file')
        zonedir = self.get('named_zone_dir')
        if not includefile:
            self.log.error("named_include_file should be configured")
            return None
        if not zonedir:
            self.log.error("named_zone_dir should be configured")
            return None

        # load templates
        tloader = template.Loader(self.get('path') + '/templates')

        # create include file for named.conf
        namedconffile = open(includefile, 'w')
        zonenames = []
        for network in networks:
            zonenames.extend([network, networks[network]['rev_zone_name']])

        namedconffile.write(tloader.load('templ_named_conf.cfg').generate(networks=zonenames))
        namedconffile.close()
        nameduid = pwd.getpwnam("named").pw_uid
        namedgid = grp.getgrnam("named").gr_gid
        os.chown(includefile, 0, namedgid)
        self.log.info("Created '{}'".format(includefile))

        # remove zone files
        filelist = [f for f in os.listdir(zonedir) if f.endswith(".luna.zone")]
        for f in filelist:
            filepath = zonedir + "/" + f
            try:
                os.remove(filepath)
                self.log.info("Removed old '{}'".format(filepath))
            except:
                self.log.info("Unable to remove '{}'".format(filepath))
        # create zone files
        for network in networks:
            # create zone
            z = {}
            z['master_hostname'] = networks[network]['ns_hostname']
            z['master_ip'] = networks[network]['ns_ip']
            z['serial_num'] = 1
            z['hosts'] = networks[network]['hosts']
            zonefilepath = zonedir + "/" + network + ".luna.zone"
            zonefile = open(zonefilepath, 'w')
            zonefile.write(tloader.load('templ_zone.cfg').generate(z=z))
            zonefile.close()
            os.chown(zonefilepath, nameduid, namedgid)
            self.log.info("Created '{}'".format(zonefilepath))
            revzonepath = zonedir + "/" + networks[network]['rev_zone_name'] + ".luna.zone"
            z['master_hostname'] = networks[network]['ns_hostname'] + "." + network
            z['hosts'] = {}
            for host in networks[network]['hosts']:
                hostname = host + "." + network
                iparr = [int(elem) for elem in networks[network]['hosts'][host].split('.')]
                reverseiplist = list(reversed(iparr[networks[network]['mutable_octet']:]))
                reverseip = '.'.join([str(elem) for elem in reverseiplist])
                z['hosts'][hostname] = reverseip
            zonefile = open(revzonepath, 'w')
            zonefile.write(tloader.load('templ_zone_arpa.cfg').generate(z=z))
            zonefile.close()
            os.chown(revzonepath, nameduid, namedgid)
            self.log.info("Created '{}'".format(revzonepath))
        return True
