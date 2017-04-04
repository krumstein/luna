import unittest

import luna
import getpass
import copy
from helper_utils import Sandbox


class InterfaceTests(unittest.TestCase):
    """
    Test for group without nodes
    """

    def setUp(self):

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

        self.osimage = luna.OsImage(
            name='testosimage',
            path=osimage_path,
            mongo_db=self.db,
            create=True
        )

        self.group = luna.Group(
            name='testgroup',
            osimage=self.osimage.name,
            mongo_db=self.db,
            interfaces=['eth0'],
            create=True,
        )

        self.node = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        self.network = luna.Network(
            name="testnet",
            mongo_db=self.db,
            create=True,
            NETWORK='10.50.0.0',
            PREFIX=16,
        )


    def test_add_del_net(self):

        start_array, end_array = [], []

        for obj_class in ['network', 'group', 'node']:
            start_array.append(
                self.db[obj_class].find_one()
            )

        self.group.set_net_to_if('eth0', self.network.name)

        for key in self.node._json['interfaces']:
            rel_ip = self.node._json['interfaces'][key]
            self.assertEqual(rel_ip, 1)

        self.group.del_net_from_if('eth0')

        for obj_class in ['network', 'group', 'node']:
            end_array.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(start_array, end_array)

    def test_node_del_ip(self):

        start_array, end_array = [], []

        for obj_class in ['network', 'group', 'node']:
            start_array.append(
                self.db[obj_class].find_one()
            )

        self.group.set_net_to_if('eth0', self.network.name)

        # otherwise node._json is outdated after group.set_net_to_if()
        self.node = luna.Node('node001', mongo_db=self.db)
        self.node.del_ip('eth0')

        self.assertEqual(self.node._json['interfaces'], {})

        node_json = self.db['node'].find_one(
            {'_id': self.node._id}
        )

        self.assertEqual(node_json['interfaces'], {})

        # check if IP released in net
        net_json = self.db['network'].find_one()

        self.assertEqual(net_json['freelist'][0]['start'], 1)

        before_mistaken_del_ip, after_mistaken_del_ip = [], []


        for obj_class in ['network', 'group', 'node']:
            before_mistaken_del_ip.append(
                self.db[obj_class].find_one()
            )

        self.node.del_ip('eth0')

        for obj_class in ['network', 'group', 'node']:
            after_mistaken_del_ip.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(before_mistaken_del_ip, after_mistaken_del_ip)

        self.group.del_net_from_if('eth0')

        for obj_class in ['network', 'group', 'node']:
            end_array.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(start_array, end_array)

    def test_node_add_ip(self):
        start_array, end_array = [], []

        for obj_class in ['network', 'group', 'node']:
            start_array.append(
                self.db[obj_class].find_one()
            )


        self.group.set_net_to_if('eth0', self.network.name)

        # otherwise node._json is outdated after group.set_net_to_if()
        self.node = luna.Node('node001', mongo_db=self.db)


        before_add_ip, after_mistaken_add_ip = [], []

        for obj_class in ['network', 'group', 'node']:
            before_add_ip.append(
                self.db[obj_class].find_one()
            )

        self.node.add_ip('eth0', 1)

        for obj_class in ['network', 'group', 'node']:
            after_mistaken_add_ip.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(before_add_ip, after_mistaken_add_ip)

        self.node.del_ip('eth0')
        self.node.add_ip('eth0', 1)

        after_add_same_ip = []

        for obj_class in ['network', 'group', 'node']:
            after_add_same_ip.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(before_add_ip, after_add_same_ip)

        self.node.del_ip('eth0')

        before_add_ip = []
        after_add_ip_from_wrong_range = []

        for obj_class in ['network', 'group', 'node']:
            before_add_ip.append(
                self.db[obj_class].find_one()
            )

        self.assertRaises(
            RuntimeError, self.node.add_ip, 'eth0', '10.51.0.1'
        )

        for obj_class in ['network', 'group', 'node']:
            after_add_ip_from_wrong_range.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(
            before_add_ip,
            after_add_ip_from_wrong_range
        )

        self.node.add_ip('eth0', '10.50.0.2')

        node_json = self.db['node'].find_one()
        network_json = self.db['network'].find_one()

        self.assertEqual(len(node_json['interfaces']), 1)
        for key in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][key], 2)

        self.assertEqual(network_json['freelist'][0]['start'], 1)
        self.assertEqual(network_json['freelist'][0]['end'], 1)
        self.assertEqual(network_json['freelist'][1]['start'], 3)

        self.group.del_net_from_if('eth0')

        for obj_class in ['network', 'group', 'node']:
            end_array.append(
                self.db[obj_class].find_one()
            )

        self.assertEqual(start_array, end_array)

    def test_add_node_to_group(self):

        self.group.set_net_to_if('eth0', self.network.name)

        node_json = self.db['node'].find_one()

        self.assertEqual(len(node_json['interfaces']), 1)
        for key in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][key], 1)

        network_json = self.db['network'].find_one()

        self.assertEqual(len(network_json['freelist']), 1)
        self.assertEqual(network_json['freelist'][0]['start'], 2)

if __name__ == '__main__':
    unittest.main()
