import unittest

import luna
import getpass
from helper_utils import Sandbox


class InterfaceBasicTests(unittest.TestCase):
    """
    Test for group without nodes
    """

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

        self.network6 = luna.Network(
            name="testnet2",
            mongo_db=self.db,
            create=True,
            NETWORK='fe80::',
            PREFIX=64,
            version=6
        )

    def tearDown(self):
        self.sandbox.cleanup()

    def test_add_net_w_nodes_4(self):

        start_array, end_array = [], []

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.network = luna.Network(name=self.network.name, mongo_db=self.db)

        for key in self.node._json['interfaces']:

            if_dict = self.node._json['interfaces'][key]
            self.assertEqual(
                if_dict,
                {'4': 1, '6': None}
            )

    def test_add_net_w_nodes_6(self):

        start_array, end_array = [], []

        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.network = luna.Network(name=self.network6.name, mongo_db=self.db)

        for key in self.node._json['interfaces']:

            if_dict = self.node._json['interfaces'][key]
            self.assertEqual(
                if_dict,
                {'4': None, '6': 1}
            )

    def test_add_net_group_node_net4_net6(self):

        start_array, end_array = [], []

        self.group.set_net_to_if('eth0', self.network.name)
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.network = luna.Network(name=self.network6.name, mongo_db=self.db)

        for key in self.node._json['interfaces']:

            if_dict = self.node._json['interfaces'][key]
            self.assertEqual(
                if_dict,
                {'4': 1, '6': 1}
            )

    def test_add_net_group_net4_node_net6(self):

        start_array, end_array = [], []

        self.node.delete()
        self.group = luna.Group(name=self.group.name, mongo_db=self.db)
        self.group.set_net_to_if('eth0', self.network.name)
        self.node = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        for key in self.node._json['interfaces']:

            if_dict = self.node._json['interfaces'][key]
            self.assertEqual(
                if_dict,
                {'4': 1, '6': None}
            )

        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        for key in self.node._json['interfaces']:

            if_dict = self.node._json['interfaces'][key]
            self.assertEqual(
                if_dict,
                {'4': 1, '6': 1}
            )

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

    def test_node_get_ip(self):
        self.assertIsNone(self.node.get_ip('eth0'))

        self.assertIsNone(
            self.node.get_ip(interface_uuid="non-exist")
        )

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(
            name=self.node.name,
            mongo_db=self.db,
        )

        # interface by name

        self.assertEqual(
            self.node.get_ip('eth0'),
            "10.50.0.1",
        )

        self.assertEqual(
            self.node.get_ip('eth0', format="num"),
            1,
        )

        # interface by uuid

        node_json = self.db['node'].find_one({'_id': self.node._id})

        for if_uuid in node_json['interfaces']:
            self.assertEqual(
                self.node.get_ip(interface_uuid=if_uuid),
                "10.50.0.1",
            )

            self.assertEqual(
                self.node.get_ip(interface_uuid=if_uuid, format="num"),
                1,
            )
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

class InterfaceOperations(unittest.TestCase):
    """
    Tests for common administrative tasks
    """

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

        self.network1 = luna.Network(
            name="testnet1",
            mongo_db=self.db,
            create=True,
            NETWORK='10.50.0.0',
            PREFIX=16,
        )

        self.network2 = luna.Network(
            name="testnet2",
            mongo_db=self.db,
            create=True,
            NETWORK='10.51.0.0',
            PREFIX=16,
        )

    def tearDown(self):
        self.sandbox.cleanup()

    def test_add_net_to_if(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )

        self.group.set_net_to_if('eth0', self.network1.name)

        group_json = self.db['group'].find_one({'_id': self.group._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})
        net_json = self.db['network'].find_one({'_id': self.network1._id})

        self.assertEqual(len(group_json['interfaces']), 1)
        for k in group_json['interfaces']:
            self.assertEqual(
                group_json['interfaces'][k]['network'],
                self.network1.DBRef
            )

        self.assertEqual(len(node_json['interfaces']), 1)
        for k in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][k], 1)

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 2)

    def test_del_net_from_if(self):

        self.group.set_net_to_if('eth0', self.network1.name)

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        self.group.del_net_from_if('eth0')

        node_jsons = self.db['node'].find()
        net_json = self.db['network'].find_one({'_id': self.network1._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 1)

        for node_json in node_jsons:
            self.assertEqual(node_json['interfaces'], {})

    def add_interface_and_assign_net(self):

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        self.assertFalse(self.group.add_interface('eth0'))
        self.assertTrue(self.group.add_interface('eth1'))

        node_jsons = self.db['node'].find()
        group_json = self.db['group'].find_one({'_id': self.group._id})

        for node_json in node_jsons:
            self.assertEqual(node_json['interfaces'], {})

        self.assertEqual(len(group_json['interfaces']), 2)

        for k in group_json['interfaces']:
            if_dict = group_json['interfaces'][k]
            self.assertEqual(if_dict['params'], '')
            self.assertEqual(if_dict['network'], None)
            self.assertIn(if_dict['name'], ['eth0', 'eth1'])

        # add net to interface
        self.assertTrue(self.group.set_net_to_if('eth1', self.network1.name))

        group_json = self.db['group'].find_one({'_id': self.group._id})
        node_jsons = self.db['node'].find()
        net_json = self.db['network'].find_one({'_id': self.network1._id})

        if_uuid = None
        for k in group_json['interfaces']:
            if_dict = group_json['interfaces'][k]
            if if_dict['name'] == 'eth1':
                self.assertEqual(if_dict['network'], self.network1.DBRef)
                if_uuid = k
            else:
                self.assertEqual(if_dict['network'], None)

        self.assertEqual(self.group.list_ifs()['eth1'], if_uuid)

        tmp_list = range(12)[1:]
        for node_json in node_jsons:
            # ips not in order
            tmp_list.remove(node_json['interfaces'][if_uuid])
        self.assertEqual(tmp_list, [])

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 12)

    def delete_interface(self):

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        self.assertTrue(self.group.add_interface('eth1'))

        self.assertTrue(self.group.set_net_to_if('eth1', self.network1.name))

        # del interface
        self.assertFalse(self.group.del_interface('not_exist'))

        self.assertTrue(self.group.del_interface('eth1'))

        group_json = self.db['group'].find_one({'_id': self.group._id})
        node_jsons = self.db['node'].find()
        net_json = self.db['network'].find_one({'_id': self.network1._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 1)

        for node_json in node_jsons:
            self.assertEqual(node_json['interfaces'], {})

        if_uuid = self.group.list_ifs()['eth1']
        self.assertEqual(group_json['interfaces'][if_uuid]['network'], None)

if __name__ == '__main__':
    unittest.main()
