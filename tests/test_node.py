import unittest

import sys
import luna
import getpass
import copy
from helper_utils import Sandbox

dbtype = 'auto'


class NodeCreateTests(unittest.TestCase):

    def setUp(self):

        self.sandbox = Sandbox(dbtype=dbtype)
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
            out = "WARNING: Backend database is incomatible. Skipping '{}'"
            print out.format(sys._getframe().f_code.co_name)
            return True

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

        self.sandbox = Sandbox(dbtype=dbtype)
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
            out = "WARNING: Backend database is incompatible. Skipping '{}'"
            print out.format(sys._getframe().f_code.co_name)
            return True

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
        self.node.set_mac('00:01:02:aa:bb:cc')
        self.node.set_mac('')
        d = self.db['mac'].find()
        self.assertEqual(d.count(), 0)

if __name__ == '__main__':
    unittest.main()
