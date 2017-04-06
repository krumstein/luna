import unittest

import luna
import getpass
from helper_utils import Sandbox


class InterfaceBasicTests(unittest.TestCase):
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


class BMCTests(unittest.TestCase):
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

    def test_add_del_bmcnet_to_group(self):

        start_array, end_array = [], []

        for obj_class in ['network', 'group', 'node']:
            start_array.append(
                self.db[obj_class].find_one()
            )
        self.group.set_bmcnetwork(self.network.name)
        self.group.del_bmcnetwork()

        for obj_class in ['network', 'group', 'node']:
            end_array.append(
                self.db[obj_class].find_one()
            )
        self.assertEqual(start_array, end_array)

    def test_add_bmcnet_to_group_mistaken(self):

        net2 = luna.Network(
            name="testnet2",
            NETWORK="10.51.0.0",
            PREFIX=24,
            mongo_db=self.db,
            create=True,
        )

        self.group.set_bmcnetwork(self.network.name)

        start_array, end_array = [], []

        for obj_class in ['network', 'group', 'node']:
            start_array.append(
                self.db[obj_class].find_one()
            )

        self.group.set_bmcnetwork(net2.name)
        for obj_class in ['network', 'group', 'node']:
            end_array.append(
                self.db[obj_class].find_one()
            )
        self.assertEqual(start_array, end_array)

    def test_add_node_with_bmcnet_configured(self):

        self.group.set_bmcnetwork(self.network.name)

        node2 = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node1_json = self.db['node'].find_one({'_id': self.node._id})
        node2_json = self.db['node'].find_one({'_id': node2._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 3)
        self.assertEqual(node1_json['bmcnetwork'], 1)
        self.assertEqual(node2_json['bmcnetwork'], 2)

    def test_del_bmc_ip(self):

        self.group.set_bmcnetwork(self.network.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.del_ip(bmc=True)

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 1)

        self.assertEqual(node_json['bmcnetwork'], None)

    def test_add_bmc_ip(self):

        self.group.set_bmcnetwork(self.network.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.del_ip(bmc=True)
        self.node.add_ip(new_ip=2, bmc=True)

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 2)
        self.assertEqual(net_json['freelist'][0]['start'], 1)
        self.assertEqual(net_json['freelist'][0]['end'], 1)
        self.assertEqual(net_json['freelist'][1]['start'], 3)

        self.assertEqual(node_json['bmcnetwork'], 2)

    def test_set_bmc_ip_same(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.set_ip(ip="10.50.0.1", bmc=True)

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 2)

        self.assertEqual(node_json['bmcnetwork'], 1)

    def test_set_bmc_ip_other(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.set_ip(ip="10.50.0.10", bmc=True)

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 2)
        self.assertEqual(net_json['freelist'][0]['start'], 1)
        self.assertEqual(net_json['freelist'][0]['end'], 9)
        self.assertEqual(net_json['freelist'][1]['start'], 11)

        self.assertEqual(node_json['bmcnetwork'], 10)

    def test_set_bmc_ip_if_prev_ip_is_none(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.node.del_ip(bmc=True)

        self.node.set_ip(ip="10.50.0.10", bmc=True)

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 2)
        self.assertEqual(net_json['freelist'][0]['start'], 1)
        self.assertEqual(net_json['freelist'][0]['end'], 9)
        self.assertEqual(net_json['freelist'][1]['start'], 11)

        self.assertEqual(node_json['bmcnetwork'], 10)

    def test_set_bmc_ip_garbage(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertRaises(
            RuntimeError, self.node.set_ip, ip="garbage", bmc=True
        )

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 2)

        self.assertEqual(node_json['bmcnetwork'], 1)

    def test_set_bmc_ip_wrong_ip(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertRaises(
            RuntimeError, self.node.set_ip, ip="192.168.1.1", bmc=True
        )

        net_json = self.db['network'].find_one({'_id': self.network._id})
        node_json = self.db['node'].find_one({'_id': self.node._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 2)

        self.assertEqual(node_json['bmcnetwork'], 1)

    def test_add_nodes_w_bmcnet_configured(self):

        self.group.set_bmcnetwork(self.network.name)

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        node_jsons = self.db['node'].find()

        net_json = self.db['network'].find_one({'_id': self.network._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 12)

        reserved_ips = []
        for node_json in node_jsons:
            reserved_ips.append(node_json['bmcnetwork'])

        self.assertEqual(len(set(reserved_ips)), 11)

    def test_delete_node_w_bmcnet_configured(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        self.node.delete()

        node_jsons = self.db['node'].find()

        net_json = self.db['network'].find_one({'_id': self.network._id})

        self.assertEqual(len(net_json['freelist']), 2)
        self.assertEqual(net_json['freelist'][0]['start'], 1)
        self.assertEqual(net_json['freelist'][0]['end'], 1)
        self.assertEqual(net_json['freelist'][1]['start'], 12)

        reserved_ips = []
        for node_json in node_jsons:
            reserved_ips.append(node_json['bmcnetwork'])

        self.assertEqual(len(set(reserved_ips)), 10)

    def test_delete_bmcnet_if_nodes_are_configured(self):

        self.group.set_bmcnetwork(self.network.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        nodes = []
        for i in range(10):
            nodes.append(
                luna.Node(
                    group=self.group.name,
                    mongo_db=self.db,
                    create=True,
                )
            )

        self.group.del_bmcnetwork()

        net_json = self.db['network'].find_one({'_id': self.network._id})

        self.assertEqual(len(net_json['freelist']), 1)
        self.assertEqual(net_json['freelist'][0]['start'], 1)

        node_jsons = self.db['node'].find()

        for node_json in node_jsons:
            self.assertEqual(node_json['bmcnetwork'], None)


class InterfaceOperations(unittest.TestCase):
    """
    Tests for common administrative tasks
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
