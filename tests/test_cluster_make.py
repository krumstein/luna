import unittest

import luna
import getpass
import copy
import datetime
import socket
from helper_utils import Sandbox


class ClusterMakeDNSTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path
        osimage_path = self.sandbox.create_osimage()

        self.cluster = luna.Cluster(
            mongo_db=self.db,
            create=True,
            path=self.path,
            user=getpass.getuser()
        )

        self.osimage = luna.OsImage(name='testosimage', path=osimage_path,
                                    mongo_db=self.db, create=True)

        self.group = luna.Group(name='testgroup', osimage=self.osimage.name,
                                mongo_db=self.db, interfaces=['eth0'],
                                create=True)

        self.net11 = luna.Network(name='net11',
                                  NETWORK='10.11.0.0', PREFIX=16,
                                  mongo_db=self.db, create=True)
        self.net11.set('ns_hostname', 'master')

        self.net61 = luna.Network(name='net61',
                                  NETWORK='fe90::', PREFIX=64,
                                  mongo_db=self.db, create=True)
        self.net61.set('ns_hostname', 'master')

        self.group.set_net_to_if('eth0', self.net11.name)
        self.group.set_net_to_if('eth0', self.net61.name)

        self.group = luna.Group(name=self.group.name, mongo_db=self.db)

        self.node = luna.Node(group=self.group.name, mongo_db=self.db,
                              create=True)

        self.switch = luna.Switch(name='sw01', network=self.net11.name,
                                  mongo_db=self.db, create=True)
        self.switch.set('ip', '10.11.1.1')

        self.otherdev = luna.OtherDev(name='pdu01', network=self.net11.name,
                                      ip="10.11.2.1", mongo_db=self.db,
                                      create=True)

        self.net11 = luna.Network(name=self.net11.name, mongo_db=self.db)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.group = luna.Group(name=self.group.name, mongo_db=self.db)

    def tearDown(self):
        self.sandbox.cleanup()

    def test_get_allocated_ips_wrong(self):
        self.assertFalse(self.group.get_allocated_ips("wrong"))

    def test_get_allocated_ips_simple(self):
        self.assertEqual(self.group.get_allocated_ips(self.net11),
                         {'node001': 1})

    def test_get_allocated_ips_duplicate_ifs(self):
        self.group.add_interface('BMC')
        self.group.set_net_to_if('BMC', self.net11.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.assertEqual(self.group.get_allocated_ips(self.net11),
                         {'node001-eth0': 1, 'node001-bmc': 2})

    def test_get_allocated_ips_duplicate_ifs(self):
        self.group.add_interface('BMC')
        self.group.set_net_to_if('BMC', self.net11.name)
        self.group.add_interface('Eth0')
        self.group.set_net_to_if('Eth0', self.net11.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.assertEqual(self.group.get_allocated_ips(self.net11),
                         {'node001-eth0': 1,
                          'node001-BMC': 2,
                          'node001-Eth0': 3})

    def test_resolve_used_ips_simple(self):
        self.assertEqual(self.net11.resolve_used_ips(),
                         {'node001': '10.11.0.1',
                          'sw01': '10.11.1.1',
                          'pdu01': '10.11.2.1',
                          'master': '10.11.255.254'}
                        )


if __name__ == '__main__':
    unittest.main()
