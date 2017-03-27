from ming import create_datastore
import unittest

import os
import luna
import getpass
from helper_utils import create_luna_homedir, mock_osimage_tree


class OsimageCreateTests(unittest.TestCase):

    def setUp(self):
        self.bind = create_datastore('mim:///luna')
        self.db = self.bind.db.luna
        self.path = '/tmp/luna'

        if not os.path.exists(self.path):
            os.makedirs(self.path)

        self.osimage_path = self.path + '/osimage'

        create_luna_homedir(self.path)

        self.kern_versions = ['1.0.0', '2.0.0']

        mock_osimage_tree(self.osimage_path, self.kern_versions)

        self.cluster = luna.Cluster(
            mongo_db=self.db,
            create=True,
            path=self.path,
            user=getpass.getuser(),
        )

    def tearDown(self):
        self.bind.conn.drop_all()

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
