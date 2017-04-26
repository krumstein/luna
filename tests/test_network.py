import unittest

import luna
import getpass
from helper_utils import Sandbox


class NetworkCreateTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(mongo_db=self.db, create=True,
                                    path=self.path, user=getpass.getuser())

    def tearDown(self):
        self.sandbox.cleanup()

    def test_create_network_with_defaults(self):
        net = luna.Network(name='testnet', mongo_db=self.db, create=True,
                           NETWORK='172.16.1.0', PREFIX=24)
        self.assertIsInstance(net, luna.Network)

    def test_create_network_ipv6(self):
        net = luna.Network(name='testnet', mongo_db=self.db, create=True,
                           NETWORK='fd12:3456:789a:1::1', PREFIX='64',
                           version=6)
        self.assertIsInstance(net, luna.Network)

    def test_create_network_check(self):
        net = luna.Network(name='testnet', mongo_db=self.db, create=True,
                           NETWORK='172.16.1.0', PREFIX=24)
        net = luna.Network(name='testnet', mongo_db=self.db)

        self.assertIsInstance(net, luna.Network)
        self.assertEqual(net.maxbits, 32)
        self.assertEqual(net.version, 4)
        expected_dict = {
            'name': 'testnet',
            'freelist': [{u'start': 1, u'end': 253L}],
            'ns_ip': 254,
            'PREFIX': 24,
            '_usedby_': {},
            'version': 4,
            'NETWORK': 2886729984L}
        doc = self.db['network'].find_one({'name': net.name})
        for key in expected_dict.keys():
            self.assertEqual(doc[key], expected_dict[key])

    def test_create_network_check_ipv6(self):
        net = luna.Network(name='testnet', mongo_db=self.db, create=True,
                           NETWORK='fd12:3456:789a:1::1', PREFIX=64,
                           version=6)
        net = luna.Network(name='testnet', mongo_db=self.db)

        self.assertIsInstance(net, luna.Network)
        self.assertEqual(net.maxbits, 128)
        self.assertEqual(net.version, 6)
        expected_dict = {
            'name': 'testnet',
            'freelist': [{'start': '1', 'end': '18446744073709551613'}],
            'ns_ip': '18446744073709551614',
            'PREFIX': 64,
            '_usedby_': {},
            'version': 6,
            'NETWORK': '336389205813283084628800618700287770624'}
        doc = self.db['network'].find_one({'name': net.name})
        for key in expected_dict.keys():
            self.assertEqual(doc[key], expected_dict[key])


class NetworkReadTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(mongo_db=self.db, create=True,
                                    path=self.path, user=getpass.getuser())

    def tearDown(self):
        self.sandbox.cleanup()

    def test_read_non_existing_network(self):
        self.assertRaises(RuntimeError, luna.Network, mongo_db=self.db)

    def test_read_network(self):
        luna.Network(name='testnet', mongo_db=self.db, create=True,
                     NETWORK='172.16.1.0', PREFIX='24')
        net = luna.Network(name='testnet', mongo_db=self.db)
        self.assertIsInstance(net, luna.Network)


class NetworkAttributesTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(mongo_db=self.db, create=True,
                                    path=self.path, user=getpass.getuser())

        self.net = luna.Network(name='test', mongo_db=self.db, create=True,
                                NETWORK='172.16.1.0', PREFIX='24',
                                ns_hostname='controller',
                                ns_ip='172.16.1.254')

    def tearDown(self):
        self.sandbox.cleanup()

    def test_get_network(self):
        self.assertEqual(self.net.get('NETWORK'), '172.16.1.0')

    def test_get_netmask(self):
        self.assertEqual(self.net.get('NETMASK'), '255.255.255.0')

    def test_get_PREFIX(self):
        self.assertEqual(self.net.get('PREFIX'), '24')

    def test_get_ns_ip(self):
        self.assertEqual(self.net.get('ns_ip'), '172.16.1.254')

    def test_change_ns_ip(self):
        json = self.net._json
        self.assertEqual(json['ns_ip'], 254)
        self.assertEqual(json['freelist'],
            [{'start': 1, 'end': 253}]
        )
        self.assertTrue(self.net.set('ns_ip', '172.16.1.253'))
        self.assertEqual(json['ns_ip'], 253)
        self.assertEqual(json['freelist'],
            [{'start': 1, 'end': 252}, {'start': 254, 'end': 254}]
        )

    def test_get_other_key(self):
        self.assertEqual(self.net.get('name'), 'test')

    def test_reserve_ip(self):
        self.net.reserve_ip('172.16.1.3')
        net = self.net._json
        self.assertEqual(net['freelist'], [{'start': 1, 'end': 2},
                                           {'start': 4, 'end': 253}])

    def test_reserve_ip_range(self):
        self.net.reserve_ip('172.16.1.4', '172.16.1.6')
        net = self.net._json
        self.assertEqual(net['freelist'], [{'start': 1, 'end': 3},
                                           {'start': 7, 'end': 253}])

    def test_release_ip(self):
        self.net.release_ip('172.16.1.254')
        net = self.net._json
        self.assertEqual(net['freelist'], [{'start': 1, 'end': 254}])

    def test_release_ip_range(self):
        self.net.release_ip('172.16.1.250', '172.16.1.254')
        net = self.net._json
        self.assertEqual(net['freelist'], [{'start': 1, 'end': 254}])


class NetworkAttributesTestsIPv6(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(mongo_db=self.db, create=True,
                                    path=self.path, user=getpass.getuser())

        self.net = luna.Network(name='test', mongo_db=self.db, create=True,
                                NETWORK='fdee:172:30:128::', PREFIX=64,
                                ns_hostname='controller',
                                ns_ip='fdee:172:30:128::254:254',
                                version=6)

    def tearDown(self):
        self.sandbox.cleanup()

    def test_get_network(self):
        self.assertEqual(self.net.get('NETWORK'), 'fdee:172:30:128::')

    def test_get_netmask(self):
        self.assertEqual(self.net.get('NETMASK'), 'ffff:ffff:ffff:ffff::')

    def test_get_PREFIX(self):
        self.assertEqual(self.net.get('PREFIX'), 64)

    def test_get_ns_ip(self):
        self.assertEqual(self.net.get('ns_ip'), 'fdee:172:30:128::254:254')

    def test_change_ns_ip(self):
        json = self.net._json
        self.assertEqual(json['ns_ip'], 39060052)
        self.assertEqual(json['freelist'],
            [
                {'start': 1, 'end': 39060051},
                {'start': 39060053, 'end': 18446744073709551614}
            ]
        )

        self.assertTrue(self.net.set('ns_ip', 'fdee:172:30:128::254:253'))
        self.assertEqual(json['ns_ip'], 39060051)
        self.assertEqual(json['freelist'],
            [
                {'start': 1, 'end': 39060050},
                {'start': 39060052, 'end': 18446744073709551614}
            ]
        )

    def test_get_other_key(self):
        self.assertEqual(self.net.get('name'), 'test')

    def test_reserve_ip(self):
        self.net.reserve_ip('fdee:172:30:128::253:254')
        net = self.net._json
        expected_freelist = [
            {'start': 1, 'end': 38994515},
            {'start': 38994517, 'end': 39060051},
            {'start': 39060053, 'end': 18446744073709551614}
        ]
        self.assertEqual(net['freelist'], expected_freelist)

    def test_reserve_ip_range(self):
        self.net.reserve_ip('fdee:172:30:128::1:4', 'fdee:172:30:128::1:6')
        net = self.net._json
        self.assertEqual(net['freelist'],
                         [{'end': 65539, 'start': 1},
                          {'start': 65543, 'end': 39060051},
                          {'start': 39060053, 'end': 18446744073709551614}]
                         )

    def test_release_ip(self):
        self.net.release_ip('fdee:172:30:128::254:254')
        net = self.net._json
        self.assertEqual(net['freelist'],
                         [{'start': 1, 'end': 18446744073709551614}])

    def test_release_ip_range(self):
        self.net.reserve_ip('fdee:172:30:128::1:4', 'fdee:172:30:128::1:6')
        self.net.release_ip('fdee:172:30:128::1:4', 'fdee:172:30:128::1:6')
        net = self.net._json
        self.assertEqual(net['freelist'],
                         [{'start': 1, 'end': 39060051},
                          {'start': 39060053, 'end': 18446744073709551614}]
                         )

if __name__ == '__main__':
    unittest.main()
