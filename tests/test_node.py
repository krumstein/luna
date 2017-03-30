import unittest

import luna
import getpass
import copy
from helper_utils import Sandbox


class NodeCreateTests(unittest.TestCase):

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

    def test_create_node_with_defaults(self):

        node = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        doc = self.db['node'].find_one({'_id': node._id})

        expected = {
            'name': 'node001',
            'bmcnetwork': None,
            'localboot': False,
            'interfaces': {},
            'setupbmc': True,
            'switch': None,
            'service': False,
            '_use_': {
                'cluster': {str(self.cluster._id): 1},
                'group': {str(self.group._id): 1},
            },
            'group': self.group.DBRef,
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])

    def test_create_named_node(self):

        node = luna.Node(
            name='n01',
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        doc = self.db['node'].find_one({'_id': node._id})

        expected = {
            'name': 'n01',
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])

    def test_delete_node(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )

        node = luna.Node(
            name='n02',
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )

        nodeid = node._id
        node.delete()

        doc = self.db['node'].find_one({'_id': nodeid})
        self.assertIsNone(doc)


class NodeChangeTests(unittest.TestCase):

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

        self.group_new = luna.Group(
            name='testgroup_new',
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

    def test_change_group(self):
        start_dict = self.db['node'].find_one({'_id': self.node._id})

        self.node.set_group(self.group_new.name)
        expected_dict = copy.deepcopy(start_dict)
        expected_dict['group'] = self.group_new.DBRef
        expected_dict['_use_']['group'] = {
            u'' + str(self.group_new._id): 1,
        }

        actual_dict = self.db['node'].find_one({'_id': self.node._id})
        self.maxDiff = None
        self.assertEqual(expected_dict, actual_dict)

        self.node.set_group(self.group.name)

        end_dict = self.db['node'].find_one({'_id': self.node._id})
        self.assertEqual(start_dict, end_dict)

    def test_set_mac(self):
        self.node.set_mac('00:01:02:aa:bb:cc')
        d = self.db['mac'].find({'mac': '00:01:02:aa:bb:cc'})
        self.assertEqual(d.count(), 1)
        for e in d:
            self.assertEqual(self.node.DBRef, e['node'])

    def test_change_mac(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )

        self.node.set_mac('00:01:02:aa:bb:cc')
        node2 = luna.Node(
            group=self.group.name,
            mongo_db=self.db,
            create=True,
        )
        node2.set_mac('00:01:02:aa:bb:cc')
        d = self.db['mac'].find({'mac': '00:01:02:aa:bb:cc'})
        self.assertEqual(d.count(), 1)
        for e in d:
            self.assertEqual(node2.DBRef, e['node'])

    def test_clear_mac(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )
        self.node.set_mac('00:01:02:aa:bb:cc')
        self.node.set_mac('')
        d = self.db['mac'].find()
        self.assertEqual(d.count(), 0)

    def test_get_mac(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )
        mac = '00:01:02:aa:bb:cc'
        self.node.set_mac(mac)
        self.assertEqual(self.node.get_mac(), mac)

    def test_set_switch(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )
        net = luna.Network(
            'testnet',
            mongo_db=self.db,
            create=True,
            NETWORK='10.50.0.0',
            PREFIX=16,
        )

        switch = luna.Switch(
            'test1',
            network=net.name,
            mongo_db=self.db,
            create=True,
        )

        self.node.set_switch(switch.name)
        d1 = self.db['node'].find_one({'name': self.node.name})
        d2 = self.db['switch'].find_one({'name': switch.name})
        self.assertEqual(d1['switch'], switch.DBRef)
        self.assertEqual(len(d2['_usedby_']['node']), 1)
        self.assertEqual(d2['_usedby_']['node'][str(self.node._id)], 1)

    def test_change_switch(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )
        net = luna.Network(
            'testnet',
            mongo_db=self.db,
            create=True,
            NETWORK='10.50.0.0',
            PREFIX=16,
        )

        switch1 = luna.Switch(
            'test1',
            network=net.name,
            mongo_db=self.db,
            create=True,
        )

        switch2 = luna.Switch(
            'test2',
            network=net.name,
            mongo_db=self.db,
            create=True,
        )

        self.node.set_switch(switch1.name)
        self.node.set_switch(switch2.name)
        d1 = self.db['node'].find_one({'name': self.node.name})
        d2 = self.db['switch'].find_one({'name': switch1.name})
        d3 = self.db['switch'].find_one({'name': switch2.name})
        self.assertEqual(d1['switch'], switch2.DBRef)
        self.assertEqual(len(d2['_usedby_']), 0)
        self.assertEqual(len(d3['_usedby_']['node']), 1)
        self.assertEqual(d1['switch'], switch2.DBRef)

if __name__ == '__main__':
    unittest.main()
