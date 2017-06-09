import unittest
import mock

import luna
import getpass
from helper_utils import Sandbox


class OsimageCreateTests(unittest.TestCase):

    def setUp(self):

        print

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(
            mongo_db=self.db,
            create=True,
            path=self.path,
            user=getpass.getuser(),
        )

    def tearDown(self):
        self.sandbox.cleanup()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('rpm.addMacro')
    def test_create_osimage_with_defaults(self,
                                          mock_rpm_addmacro,
                                          mock_rpm_transactionset,
                                          ):
        packages = [
            {'VERSION': '3.10', 'RELEASE': '999-el0', 'ARCH': 'x86_64'},
        ]
        mock_rpm_transactionset.return_value.dbMatch.return_value = packages

        osimage = luna.OsImage(
            name='testosimage',
            path=self.path,
            mongo_db=self.db,
            create=True,
        )

        doc = self.db['osimage'].find_one({'_id': osimage._id})
        expected = {
            'path': self.path,
            'kernmodules': 'ipmi_devintf,ipmi_si,ipmi_msghandler',
            'dracutmodules': 'luna,-i18n,-plymouth',
            'kernver': '3.10-999-el0.x86_64'
        }

        for attr in expected:
            self.assertEqual(doc[attr], expected[attr])


class OsimageMethodsTests(unittest.TestCase):

    @mock.patch('rpm.TransactionSet')
    @mock.patch('rpm.addMacro')
    def setUp(self,
              mock_rpm_addmacro,
              mock_rpm_transactionset,
              ):

        print

        packages = [
            {'VERSION': '3.10', 'RELEASE': '999-el0', 'ARCH': 'x86_64'},
        ]
        mock_rpm_transactionset.return_value.dbMatch.return_value = packages

        self.sandbox = Sandbox()
        self.db = self.sandbox.db
        self.path = self.sandbox.path

        self.cluster = luna.Cluster(
            mongo_db=self.db,
            create=True,
            path=self.path,
            user=getpass.getuser(),
        )

        self.osimage = luna.OsImage(
            name='testosimage',
            path=self.path,
            mongo_db=self.db,
            create=True,
        )

    def tearDown(self):
        self.sandbox.cleanup()

    @mock.patch('os.chmod')
    @mock.patch('os.chown')
    @mock.patch('shutil.move')
    @mock.patch('os.close')
    @mock.patch('os.fchdir')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.chroot')
    @mock.patch('os.open')
    def test_pack_image_default(self,
                                mock_os_open,
                                mock_os_chroot,
                                mock_subprocess_popen,
                                mock_os_fchdir,
                                mock_os_close,
                                mock_shutil_move,
                                mock_os_chown,
                                mock_os_chmod,
                                ):

        mock_subprocess_popen.return_value.stderr.readline.return_value = ''

        self.assertTrue(self.osimage.create_tarball())

    @mock.patch('os.close')
    @mock.patch('os.fchdir')
    @mock.patch('os.remove')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.chroot')
    @mock.patch('os.open')
    def test_pack_image_broken(self,
                               mock_os_open,
                               mock_os_chroot,
                               mock_subprocess_popen,
                               mock_os_remove,
                               mock_os_fchdir,
                               mock_os_close,
                               ):

        mock_subprocess_popen.side_effect = Exception('dummy excepion')

        self.assertFalse(self.osimage.create_tarball())

    @mock.patch('rpm.TransactionSet')
    @mock.patch('rpm.addMacro')
    def test_get_package_ver(self,
                             mock_rpm_addmacro,
                             mock_rpm_transactionset,
                             ):
        packages = [
            {'VERSION': '3.10', 'RELEASE': '999-el0', 'ARCH': 'x86_64'},
            {'VERSION': '3.11', 'RELEASE': '999-el0', 'ARCH': 'x86_64'},
        ]
        mock_rpm_transactionset.return_value.dbMatch.return_value = packages
        #mock_rpm_transactionset.dbMatch = [p1]
        self.assertEqual(
            self.osimage.get_package_ver('', 'test'),
            ['3.10-999-el0.x86_64', '3.11-999-el0.x86_64']
        )


if __name__ == '__main__':
    unittest.main()
