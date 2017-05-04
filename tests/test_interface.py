import unittest

import luna
import getpass
from helper_utils import Sandbox


class AddNetToGroupTests(unittest.TestCase):
    """
    Add network to group with nodes
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

        self.node.delete()
        self.group = luna.Group(name=self.group.name, mongo_db=self.db)
        self.group.set_net_to_if('eth0', self.network.name)
        self.node = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

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


class DeleteIPTests(unittest.TestCase):
    """
    Test for delete ip addresses from node
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

    def test_node_del_ip_net4(self):

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.node.del_ip('eth0')

        net_json = self.db['network'].find_one({'_id': self.network._id})

        node_json = self.db['node'].find_one({'_id': self.node._id})

        for if_uuid in node_json['interfaces']:
            if_dict = node_json['interfaces'][if_uuid]
            self.assertEqual(if_dict, {'4': None, '6': None})

        self.assertEqual(net_json['freelist'], [{'start': 1, 'end': 65533L}])

    def test_node_del_ip_net6(self):

        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.node.del_ip('eth0')

        net_json = self.db['network'].find_one({'_id': self.network6._id})

        node_json = self.db['node'].find_one({'_id': self.node._id})

        for if_uuid in node_json['interfaces']:
            if_dict = node_json['interfaces'][if_uuid]
            self.assertEqual(if_dict, {'4': None, '6': None})

        self.assertEqual(net_json['freelist'],
                         [{'start': '1', 'end': '18446744073709551613'}])

    def test_node_del_ip_mistaken(self):

        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.node.del_ip('eth0')

        self.assertFalse(self.node.del_ip('eth0'))

    def test_node_del_ip_w_version(self):

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertTrue(self.node.del_ip('eth0', version=4))

        node_json = self.db['node'].find_one({'_id': self.node._id})

        for k in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][k],
                             {'4': None, '6': None})

    def test_node_del_ip_wrong_version(self):

        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertFalse(self.node.del_ip('eth0', version=4))

        node_json = self.db['node'].find_one({'_id': self.node._id})

        for k in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][k],
                             {'4': None, '6': 1})

    def test_node_del_ip_both_ver(self):
        self.group.set_net_to_if('eth0', self.network.name)
        self.group.set_net_to_if('eth0', self.network6.name)
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.assertTrue(self.node.del_ip('eth0', version='all'))
        node_json = self.db['node'].find_one({'_id': self.node._id})

        for k in node_json['interfaces']:
            self.assertEqual(node_json['interfaces'][k],
                             {'4': None, '6': None})

        net_json = self.db['network'].find_one({'_id': self.network._id})
        net6_json = self.db['network'].find_one({'_id': self.network6._id})
        self.assertEqual(net_json['freelist'], [{'start': 1, 'end': 65533}])
        self.assertEqual(net6_json['freelist'],
                         [{'start': '1', 'end': '18446744073709551613'}])


class GetIPTests(unittest.TestCase):
    """
    Test for Node.get_ip
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

    def test_get_ip_wrong_ver(self):
        self.assertFalse(self.node.get_ip('eth0', version=5))

    def test_wo_uuid_or_name(self):
        self.assertFalse(self.node.get_ip(version=4))

    def test_wrong_uuid(self):
        self.assertFalse(self.node.get_ip(interface_uuid='wrong-uuid'))

    def test_wrong_name(self):
        self.assertFalse(self.node.get_ip(interface_name='wrong-name'))

    def test_by_uuid_net4(self):
        interface_uuid = None
        for k in self.node._json['interfaces']:
            interface_uuid = k

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertEqual(self.node.get_ip(interface_uuid=interface_uuid),
                         '10.50.0.1')

        self.assertEqual(self.node.get_ip(interface_uuid=interface_uuid,
                                          format='num'),
                         1)

        self.assertEqual(self.node.get_ip(interface_uuid=interface_uuid,
                                          version=4),
                         '10.50.0.1')

    def test_by_name_net6(self):
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertEqual(self.node.get_ip(interface_name='eth0'),
                         'fe80::1')

        self.assertEqual(self.node.get_ip(interface_name='eth0',
                                          format='num'),
                         1)

        self.assertEqual(self.node.get_ip(interface_name='eth0',
                                          version=6),
                         'fe80::1')

    def test_wrong_version6(self):
        interface_uuid = None
        for k in self.node._json['interfaces']:
            interface_uuid = k

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertFalse(self.node.get_ip(interface_uuid=interface_uuid,
                                          version=6))

    def test_wrong_version4(self):
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertFalse(self.node.get_ip(interface_name='eth0',
                                          version=4))

    def test_ambiguous_ver(self):
        self.group.set_net_to_if('eth0', self.network.name)
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertFalse(self.node.get_ip(interface_name='eth0'))

    def test_both_vers_confgured(self):
        self.group.set_net_to_if('eth0', self.network.name)
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertEqual(self.node.get_ip(interface_name='eth0',
                                          version=6),
                         'fe80::1')

        self.assertEqual(self.node.get_ip(interface_name='eth0',
                                          version=4),
                         '10.50.0.1')


class SetIPTests(unittest.TestCase):
    """
    Test for Node.get_ip
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

    def test_get_ip_wrong_name(self):
        self.assertFalse(self.node.set_ip(interface_name='wrong-interface',
                                          ip='10.50.0.2'))

    def test_get_ip_wrong_uuid(self):
        self.assertFalse(self.node.set_ip(interface_uuid='wrong-uuid',
                                          ip='10.50.0.2'))

    def test_get_ip_for_unconfigured_if(self):
        self.assertFalse(self.node.set_ip(interface_name='eth0',
                                          ip='10.50.0.2'))

    def test_set_ip_by_name(self):
        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertTrue(self.node.set_ip(interface_name='eth0',
                                         ip='10.50.0.2'))

        self.network = luna.Network(name=self.network.name,
                                    mongo_db=self.db)

        self.assertEqual(
            self.network._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 65533}],
        )

    def test_set_ip_by_uuid(self):
        interface_uuid = None
        for k in self.node._json['interfaces']:
            interface_uuid = k

        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertTrue(self.node.set_ip(interface_uuid=interface_uuid,
                                         ip='10.50.0.2'))

        self.network = luna.Network(name=self.network.name,
                                    mongo_db=self.db)

        self.assertEqual(
            self.network._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 65533}],
        )

    def test_set_both_ips(self):
        self.group.set_net_to_if('eth0', self.network.name)
        self.group.set_net_to_if('eth0', self.network6.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)


        self.assertTrue(self.node.set_ip(interface_name='eth0',
                                          ip='10.50.0.2'))

        self.assertTrue(self.node.set_ip(interface_name='eth0',
                                          ip='fe80::2'))

        self.network = luna.Network(name=self.network.name,
                                    mongo_db=self.db)

        self.network6 = luna.Network(name=self.network6.name,
                                    mongo_db=self.db)

        self.assertEqual(
            self.network._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 65533}],
        )

        self.assertEqual(
            self.network6._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 18446744073709551613}]
        )

    def test_set_ip_force_wo_net_configured(self):
        self.assertFalse(self.node.set_ip(interface_name='eth0',
                                          ip='10.50.0.2', force=True))

    def test_set_ip_force(self):
        self.group.set_net_to_if('eth0', self.network.name)

        self.node = luna.Node(name=self.node.name,
                              mongo_db=self.db)

        self.assertTrue(self.node.set_ip(interface_name='eth0',
                                          ip='10.50.0.2', force=True))

        self.network = luna.Network(name=self.network.name,
                                    mongo_db=self.db)

        self.assertEqual(
            self.network._json['freelist'],
            [{'start': 3, 'end': 65533}],
        )


class ChangeGroupTests(unittest.TestCase):
    """
    Test for Node.get_ip
    """

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path
        osimage_path = self.sandbox.create_osimage()

        self.cluster = luna.Cluster(mongo_db=self.db, create=True,
                                    path=self.path, user=getpass.getuser())

        self.osimage = luna.OsImage(name='testosimage', path=osimage_path,
                                    mongo_db=self.db, create=True)

        self.group = luna.Group(name='testgroup',
                                osimage=self.osimage.name, mongo_db=self.db,
                                interfaces=['eth0'], create=True)

        self.new_group1 = luna.Group(name='new1',
                                osimage=self.osimage.name, mongo_db=self.db,
                                interfaces=['eth0'], create=True)

        self.node = luna.Node(group=self.group.name, mongo_db=self.db,
                              create=True)

        self.network11 = luna.Network(name="net11", mongo_db=self.db,
                                     create=True, NETWORK='10.51.0.0',
                                     PREFIX=16)

        self.network61 = luna.Network(name="net61", mongo_db=self.db,
                                     create=True, NETWORK='fe80::',
                                     PREFIX=64, version=6)

    def test_wo_interfaces_configured(self):

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.assertEqual(self.node._json['group'], self.new_group1.DBRef)

        self.assertEqual(
            self.node._json['_use_']['group'],
            {str(self.new_group1._id): 1}
        )

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': None, '6': None}
        )

        self.assertEqual(self.group._json['_usedby_'], {})

    def test_w_interfaces_configured_in_new_group_net4(self):
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.new_group1.set_net_to_if('eth0', self.network11.name)

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.network11 = luna.Network(name=self.network11.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': 1, '6': None}
        )

        self.assertEqual(
            self.network11._json['freelist'],
            [{'start': 2, 'end': 65533}]
        )

    def test_w_interfaces_configured_in_new_group_net6(self):
        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.new_group1.set_net_to_if('eth0', self.network61.name)

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.network61 = luna.Network(name=self.network61.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': None, '6': 1}
        )

        self.assertEqual(
            self.network61._json['freelist'],
            [{'start': 2, 'end': 18446744073709551613}]
        )

    def test_w_interfaces_configured_in_old_group_net4(self):
        self.group.set_net_to_if('eth0', self.network11.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.network11 = luna.Network(name=self.network11.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': None, '6': None}
        )

        self.assertEqual(
            self.network11._json['freelist'],
            [{'start': 1, 'end': 65533}]
        )

    def test_w_interfaces_configured_in_both_groups_same_net(self):
        self.group.set_net_to_if('eth0', self.network11.name)
        self.new_group1.set_net_to_if('eth0', self.network11.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.network11 = luna.Network(name=self.network11.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': 1, '6': None}
        )

        self.assertEqual(
            self.network11._json['freelist'],
            [{'start': 2, 'end': 65533}]
        )

    def test_w_interfaces_configured_in_both_groups_same_net2(self):
        self.group.set_net_to_if('eth0', self.network11.name)
        self.new_group1.set_net_to_if('eth0', self.network11.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.set_ip(interface_name='eth0', ip='10.51.0.2')

        self.assertTrue(self.node.set_group(self.new_group1.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group1 = luna.Group(name=self.new_group1.name,
                                     mongo_db=self.db)

        self.network11 = luna.Network(name=self.network11.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group1._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': 2, '6': None}
        )

        self.assertEqual(
            self.network11._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 65533}]
        )

    def test_same_net_different_ifs(self):

        self.new_group2 = luna.Group(name='new2',
                                osimage=self.osimage.name, mongo_db=self.db,
                                interfaces=['em1'], create=True)

        self.group.set_net_to_if('eth0', self.network11.name)
        self.new_group2.set_net_to_if('em1', self.network11.name)

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)
        self.node.set_ip(interface_name='eth0', ip='10.51.0.2')

        self.assertTrue(self.node.set_group(self.new_group2.name))

        self.node = luna.Node(name=self.node.name, mongo_db=self.db)

        self.group = luna.Group(name=self.group.name,
                                     mongo_db=self.db)

        self.new_group2 = luna.Group(name=self.new_group2.name,
                                     mongo_db=self.db)

        self.network11 = luna.Network(name=self.network11.name,
                                      mongo_db=self.db)

        group_if_uid = None

        for uuid in self.new_group2._json['interfaces']:
            group_if_uid = uuid

        self.assertEqual(
            self.node._json['interfaces'][group_if_uid],
            {'4': 2, '6': None}
        )

        self.assertEqual(
            self.network11._json['freelist'],
            [{'start': 1, 'end': 1}, {'start': 3, 'end': 65533}]
        )

class OtherInterfaceTests(unittest.TestCase):
    """
    Test for Node.get_ip
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
