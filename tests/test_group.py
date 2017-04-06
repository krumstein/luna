import unittest

import os
import sys
import luna
import getpass
from helper_utils import Sandbox


class GroupCreateTests(unittest.TestCase):

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

#    def tearDown(self):
#       self.sandbox.cleanup()
        

    def test_create_group_with_defaults(self):

        group = luna.Group(
            name='testgroup1',
            osimage=str(self.osimage.name),
            mongo_db=self.db,
            interfaces=['eth0'],
            create=True
        )

        doc = self.db['group'].find_one({'_id': group._id})
        expected = {
            'torrent_if': None,
            'partscript': 'mount -t tmpfs tmpfs /sysroot',
            'postscript': (
                'cat << EOF >> /sysroot/etc/fstab\n' +
                'tmpfs   /       tmpfs    defaults        0 0\n' +
                'EOF'
            ),
            'name': 'testgroup1',
            'bmcnetwork': None,
            'bmcsetup': None,
            'boot_if': None,
            '_use_': {
                'cluster': {str(self.cluster._id): 1},
                'osimage': {str(self.osimage._id): 1}
            },
            'osimage': self.osimage.DBRef
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])
        # check interfaces
        if_dict = doc['interfaces']
        self.assertEqual(len(if_dict), 1)
        for uuid in if_dict:
            self.assertEqual(if_dict[uuid]['name'], 'eth0')
            self.assertEqual(if_dict[uuid]['params'], '')
            self.assertEqual(if_dict[uuid]['network'], None)

    def test_create_broken(self):
        self.assertRaises(
            RuntimeError,
            luna.Group,
            name='testgroup1',
            osimage=str(self.osimage.name),
            mongo_db=self.db,
            interfaces='eth0',
            create=True
        )

    def test_delete_group(self):
        if self.sandbox.dbtype != 'mongo':
            raise unittest.SkipTest(
                'This test can be run only with MondoDB as a backend.'
            )

        group = luna.Group(
            name='testgroup',
            osimage=str(self.osimage.name),
            mongo_db=self.db,
            interfaces=['eth0'],
            create=True
        )
        groupid = group._id
        group.delete()

        doc = self.db['group'].find_one({'_id': groupid})
        self.assertIsNone(doc)

    def test_creation_group(self):
        bmcsetup = luna.BMCSetup(
            name='bmcsetup',
            mongo_db=self.db,
            create=True
        )
        bmcnet = luna.Network(
            name='ipmi',
            NETWORK='10.10.0.0',
            PREFIX=16,
            mongo_db=self.db,
            create=True
        )
        nics = ['eth0', 'eth1']
        group = luna.Group(
            name='testgroup2',
            osimage=self.osimage.name,
            bmcnetwork=bmcnet.name,
            bmcsetup=bmcsetup.name,
            mongo_db=self.db,
            interfaces=nics,
            boot_if=nics[0],
            torrent_if=nics[1],
            create=True
        )

        doc = self.db['group'].find_one({'_id': group._id})
        expected = {
            'torrent_if': nics[1],
            'partscript': 'mount -t tmpfs tmpfs /sysroot',
            'postscript': (
                'cat << EOF >> /sysroot/etc/fstab\n' +
                'tmpfs   /       tmpfs    defaults        0 0\n' +
                'EOF'
            ),
            'name': 'testgroup2',
            'bmcnetwork': bmcnet.DBRef,
            'bmcsetup': bmcsetup.DBRef,
            'boot_if': nics[0],
            '_use_': {
                'cluster': {str(self.cluster._id): 1},
                'osimage': {str(self.osimage._id): 1},
                'network': {str(bmcnet._id): 1},
                'bmcsetup': {str(bmcsetup._id): 1},
            },
            'osimage': self.osimage.DBRef
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])
        # check interfaces
        if_dict = doc['interfaces']
        self.assertEqual(len(if_dict), len(nics))
        for uuid in if_dict:
            self.assertIn(if_dict[uuid]['name'], nics)
            self.assertEqual(if_dict[uuid]['params'], '')
            self.assertEqual(if_dict[uuid]['network'], None)
            nics.remove(if_dict[uuid]['name'])


class GroupConfigTests(unittest.TestCase):

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

        self.bmcsetup = luna.BMCSetup(
            name='bmcsetup',
            mongo_db=self.db,
            create=True
        )

        self.bmcnet = luna.Network(
            name='ipmi',
            NETWORK='10.10.0.0',
            PREFIX=16,
            mongo_db=self.db,
            create=True
        )

        self.net1 = luna.Network(
            name='cluster',
            NETWORK='10.11.0.0',
            PREFIX=16,
            mongo_db=self.db,
            create=True
        )
        self.net2 = luna.Network(
            name='external',
            NETWORK='10.12.0.0',
            PREFIX=16,
            mongo_db=self.db,
            create=True
        )
        self.net3 = luna.Network(
            name='ib',
            NETWORK='10.13.0.0',
            PREFIX=16,
            mongo_db=self.db,
            create=True
        )

        self.prescript = 'pre'
        self.postscript = 'post'
        self.partscript = 'part'
        self.nics = {'eth0': 'PARM=1', 'eth1': 'PARM=2', 'ib0': 'PARM=3'}

        self.group = luna.Group(
            name='compute',
            osimage=self.osimage.name,
            mongo_db=self.db,
            interfaces=['eth0'],
            create=True)

#    def tearDown(self):
#        self.sandbox.cleanup()

    def test_add_remove_net_to_if(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})

        self.group.set_net_to_if('eth0', self.net1.name)

        self.assertEqual(
            self.group.show_if('eth0'),
            'NETWORK=10.11.0.0\nPREFIX=16'
        )

        self.assertEqual(
            self.group.show_if('eth0', brief=True),
            '[cluster]:10.11.0.0/16'
        )

        self.group.del_net_from_if('eth0')
        self.assertEqual(self.group.show_if('eth0'), '')

        # check if we get the same dictionary at the and
        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_osimage(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})

        osimage_name = 'osimage2'
        osimage_path = self.sandbox.create_osimage()

        osimage = luna.OsImage(
            name=osimage_name,
            path=osimage_path,
            mongo_db=self.db,
            create=True
        )

        self.group.osimage(osimage.name)

        self.assertEqual(
            self.group.show()['osimage'],
            '[' + osimage.name + ']'
        )

        self.group.osimage(self.osimage.name)

        self.assertEqual(
            self.group.show()['osimage'],
            '[' + self.osimage.name + ']'
        )

        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_bmcsetup(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})

        self.group.bmcsetup(self.bmcsetup.name)

        self.assertEqual(
            self.group.show()['bmcsetup'],
            '[' + self.bmcsetup.name + ']'
        )

        self.group.bmcsetup()
        self.assertIsNone(self.group.show()['bmcsetup'])

        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_add_remove_bmcnet(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})

        self.group.set_bmcnetwork(self.bmcnet.name)
        self.assertEqual(
            self.group.show()['bmcnetwork'],
            '[' + self.bmcnet.name + ']'
        )
        self.group.set_bmcnetwork(self.bmcnet.name)
        self.assertEqual(
            self.group.show()['bmcnetwork'],
            '[' + self.bmcnet.name + ']'
        )
        self.group.del_bmcnetwork()
        self.assertIsNone(self.group.show()['bmcnetwork'])

        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_show_bmc_if(self):
        self.group.set_bmcnetwork(self.bmcnet.name)
        self.assertEqual(self.group.show_bmc_if(), '10.10.0.0/16')
        self.assertEqual(
            self.group.show_bmc_if(brief=True),
            '[ipmi]:10.10.0.0/16'
        )
        self.group.del_bmcnetwork()
        self.assertEqual(self.group.show_bmc_if(), '')

    def test_get_net_name_for_if(self):
        self.assertEqual(self.group.get_net_name_for_if('eth0'), '')
        self.assertEqual(self.group.get_net_name_for_if('unexisting_if'), '')
        self.group.set_net_to_if('eth0', self.net1.name)
        self.assertEqual(
            self.group.get_net_name_for_if('eth0'),
            self.net1.name
        )
        self.group.del_net_from_if('eth0')

    def test_add_del_interface(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})
        if1 = start_dict['interfaces']
        self.assertIsNone(self.group.add_interface('eth0'))
        if2 = self.db['group'].find_one({'_id': self.group._id})['interfaces']
        # chech if dictionary did not change
        self.assertEqual(if1, if2)
        self.assertTrue(self.group.add_interface('eth1'))
        if3 = self.db['group'].find_one({'_id': self.group._id})['interfaces']

        for e in if2.keys():
            # we should pop all the interfaces except eth1
            self.assertEqual(if3.pop(e)['name'], 'eth0')
        # last one should be eth1
        self.assertEqual(if3.values()[0]['name'], 'eth1')
        # should be the only last
        self.assertEqual(len(if3.keys()), 1)

        self.assertTrue(self.group.del_interface('eth1'))
        if4 = self.db['group'].find_one({'_id': self.group._id})['interfaces']
        self.assertEqual(if1, if4)
        self.assertFalse(self.group.del_interface('eth1'))

        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_rename_interface(self):
        start_dict = self.db['group'].find_one({'_id': self.group._id})

        if1 = self.group.list_ifs()
        self.assertEqual(if1.keys()[0], 'eth0')
        self.assertIsNone(self.group.rename_interface('unexisting_if', 'eth1'))

        self.assertTrue(self.group.add_interface('ethX'))
        self.assertIsNone(self.group.rename_interface('ethX', 'eth0'))
        self.assertTrue(self.group.rename_interface('ethX', 'eth1'))
        self.assertTrue(self.group.del_interface('eth1'))

        end_dict = self.db['group'].find_one({'_id': self.group._id})
        self.assertEqual(start_dict, end_dict)

    def test_get_ip(self):

        self.group.set_bmcnetwork(self.bmcnet.name)
        self.group.set_net_to_if('eth0', self.net1.name)

        group_json = self.db['group'].find_one({'_id': self.group._id})

        if_uuid = ""
        for k in group_json['interfaces']:
            if_uuid = k

        self.assertEqual(len(if_uuid), 32)
        
        human_eth0_ip = self.group.get_ip(
            interface_uuid=if_uuid,
            ip=500,
            bmc=False,
            format='human'
        )

        num_eth0_ip = self.group.get_ip(
            interface_uuid=if_uuid,
            ip="10.11.1.244",
            bmc=False,
            format='num'
        )

        self.assertEqual(human_eth0_ip, "10.11.1.244")
        self.assertEqual(num_eth0_ip, 500)

        human_bmc_ip = self.group.get_ip(
            ip=600,
            bmc=True,
            format='human'
        )

        num_bmc_ip = self.group.get_ip(
            ip="10.10.2.88",
            bmc=True,
            format='num'
        )

        self.assertEqual(human_bmc_ip, "10.10.2.88")
        self.assertEqual(num_bmc_ip, 600)

        out = self.group.get_ip()
        self.assertIsNone(out)

        out = self.group.get_ip(interface_uuid=if_uuid)
        self.assertIsNone(out)

        out = self.group.get_ip(bmc=True)
        self.assertIsNone(out)

    def test_boot_params(self):

        # mocking osimage boot stuff
        self.osimage.copy_boot()

        self.assertEqual(self.group.boot_params,
                {'net_prefix': '',
                'kernel_file': self.osimage.name + '-vmlinuz-1.0.0-1.el7.x86_64',
                'kern_opts': '',
                'boot_if': '',
                'initrd_file': self.osimage.name + '-initramfs-1.0.0-1.el7.x86_64',
            }
        )

        self.group.set('boot_if', 'eth0')

        self.assertEqual(self.group.boot_params,
                {'net_prefix': '',
                'kernel_file': self.osimage.name + '-vmlinuz-1.0.0-1.el7.x86_64',
                'kern_opts': '',
                'boot_if': '',
                'initrd_file': self.osimage.name + '-initramfs-1.0.0-1.el7.x86_64',
            }
        )

        self.group.set_net_to_if('eth0', self.net1.name)

        self.assertEqual(self.group.boot_params,
                {'net_prefix': 16,
                'kernel_file': self.osimage.name + '-vmlinuz-1.0.0-1.el7.x86_64',
                'kern_opts': '',
                'boot_if': 'eth0',
                'initrd_file': self.osimage.name + '-initramfs-1.0.0-1.el7.x86_64',
            }
        )



if __name__ == '__main__':
    unittest.main()
