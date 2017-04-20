import unittest

import os
import luna
import getpass
from helper_utils import Sandbox


class OsimageCreateTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path
        self.kern_versions = ['1.0.0', '2.0.0']
        self.osimage_path = self.sandbox.create_osimage(self.kern_versions)

        self.cluster = luna.Cluster(
            mongo_db=self.db,
            create=True,
            path=self.path,
            user=getpass.getuser(),
        )

    def tearDown(self):
        self.sandbox.cleanup()

    def test_create_osimage_with_defaults(self):
        osimage = luna.OsImage(
            name='testosimage',
            path=self.osimage_path,
            mongo_db=self.db,
            create=True,
        )

        doc = self.db['osimage'].find_one({'_id': osimage._id})
        expected = {
            'path': self.osimage_path,
            'kernmodules': 'ipmi_devintf,ipmi_si,ipmi_msghandler',
            'dracutmodules': 'luna,-i18n,-plymouth',
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])

if __name__ == '__main__':
    unittest.main()
