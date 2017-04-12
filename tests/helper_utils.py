import rpm
import os
import shutil
import socket
import time
import tempfile
import pymongo
import subprocess
import ming
import uuid


class Sandbox(object):
    """
    Class for creating sanboxed envidonment for Luna
    Class.db     - MongoDB or Ming database.
                   Depends if mongod executable exist.
    Class.dbtype - Current DB.
    Class.path   - Path to temporary folder.
    """

    def __init__(self, path = None, dbtype = 'auto'):
        """
        path   - Path to store sandbox files. 
        dbtype - Type of the dabatabse. [auto|mongo|ming]
        """
        if 'LUNA_TEST_DBTYPE' in os.environ:
            dbtype = os.environ['LUNA_TEST_DBTYPE']
        if not path:
            self.path = tempfile.mkdtemp(prefix='luna')
        else:
            # can cause race condition, but ok
            if not os.path.exists(path):
                os.makedirs(path)
            self.path = path
        self._dbconn = None
        self._mongopath = self.path + "/mongo"
        if not os.path.exists(self._mongopath):
            os.makedirs(self._mongopath)
        self._mongoprocess = None
        if dbtype == 'auto':
            try:
                self._start_mongo()
                self.dbtype = 'mongo'
            except OSError:
                self._mingdatastore = ming.create_datastore('mim:///' + str(uuid.uuid4()))
                self._dbconn = self._mingdatastore.db.luna
                self.dbtype = 'ming'
        elif dbtype == 'mongo':
            self._start_mongo()
            self.dbtype = 'mongo'
        else:
            self._mingdatastore = ming.create_datastore('mim:///' + str(uuid.uuid4()))
            self._dbconn = self._mingdatastore.db.luna
            self.dbtype = 'ming'
        self._create_luna_homedir()

    _specfile_template = """Name:                   kernel
Version:                {version}
Release:                {release}
Vendor:                 dummy
Group:                  dummy
Summary:                Provides %{{name}}
License:                %{{vendor}}
# in Provides: you add whatever you want to fool the system
Buildroot:              /var/tmp/%{{name}}-%{{version}}-root
Provides:               kernel

%description
%{{summary}}

%files"""

    def create_osimage(self, kern_versions = ['1.0.0']):

        rpmtsCallback_fd = None

        def runCallback(reason, amount, total, key, client_data):
            global rpmtsCallback_fd
            if reason == rpm.RPMCALLBACK_INST_OPEN_FILE:
                rpmtsCallback_fd = os.open(key, os.O_RDONLY)
                return rpmtsCallback_fd
            elif reason == rpm.RPMCALLBACK_INST_START:
                os.close(rpmtsCallback_fd)
        
        # create dir for osimage
        if not os.path.exists(self.path + '/os'):
            os.makedirs(self.path + '/os')
        osimage_path = tempfile.mkdtemp(
            prefix = 'os',
            dir = self.path + '/os/'
        )

        # create rpmdb tree
        rpmdb_path = osimage_path + '/var/lib/rpm'
        if not os.path.exists(rpmdb_path):
            os.makedirs(rpmdb_path)

        # initialize rpmdb
        rpm.addMacro('_dbpath', rpmdb_path)
        ts = rpm.TransactionSet()
        ts.initDB()

        # create rpmbuild endironment
        rpmbuild_path = osimage_path + '/rpmbuild'
        if not os.path.exists(rpmbuild_path):
            for subdir in ['BUILD',  'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']:
                d = rpmbuild_path + '/' + subdir
                if not os.path.exists(d):
                    os.makedirs(d)

        # build and install fake kernel packages
        for kern_ver in kern_versions:

            #
            # create spec file
            #

            kern_release = '1.el7'
            spec_content = self._specfile_template.format(version = kern_ver, release = kern_release)
            spec_file_name = rpmbuild_path + '/SPECS/kernel-' + kern_ver + '.spec'
            with open(spec_file_name, 'w') as fd:
                fd.write(spec_content)

            #
            # build rpm
            #

            rpmbuild_cmd = ['rpmbuild', '--define', '"_topdir ' + rpmbuild_path +'"',
                    '-ba', spec_file_name]

            # Suppressing all outputs. Those are annoing, when running it million times.
            devnull = open(os.devnull, 'w')
            res = subprocess.call(" ".join(rpmbuild_cmd), shell=True, stdout=devnull, stderr=devnull)
            if res:
                assert False, "ERROR: Unable to build rpm"
            #
            # 'install' rpms
            #

            ts = rpm.TransactionSet()
            # do dot verify DSA signatures
            ts.setVSFlags(-1)
            # rpm --justdb
            ts.setFlags(rpm.RPMTRANS_FLAG_JUSTDB)

            rpm_file_name = (rpmbuild_path
                    + '/RPMS/x86_64/kernel-'
                    + kern_ver + '-' + kern_release
                    + '.x86_64.rpm'
                )
            rpm_header = None
            # read rpm header
            with open(rpm_file_name, 'r') as fd:
                rpm_header = ts.hdrFromFdno(fd)
            # add rpm to transaction
            ts.addInstall(rpm_header, rpm_file_name, 'i')

            # finally perform install
            ts.run(runCallback, 1)

            # create fake /boot/initramfs- and /boot/vmlinuz- files
            if not os.path.exists(osimage_path + '/boot'):
                os.makedirs(osimage_path + '/boot')
            vmlinuz_path = (osimage_path
                + "/boot/vmlinuz-"
                + kern_ver + '-' + kern_release + '.x86_64')
            initramfs_path = (osimage_path
                + "/boot/initramfs-"
                + kern_ver + '-' + kern_release + '.x86_64.img')
            with open(vmlinuz_path, 'a') as f:
                f.write('lunafakekernel')
            with open(initramfs_path, 'a') as f:
                f.write('lunafakeinitrd')

        return osimage_path

    def _create_luna_homedir(self):
        """
        Creates ./boot, ./torrents, ./templates
        subdirs in path
        """

        if 'VIRTUAL_ENV' not in os.environ:
            print "Runinning not in virtual environment"
            virtual_env_path = '/'
        else:
            virtual_env_path = os.environ['VIRTUAL_ENV']
        for d in ['boot', 'torrents']:
            if not os.path.exists(self.path + '/' + d):
                os.makedirs(self.path + '/' + d)
        source_template_path = virtual_env_path + '/usr/share/luna/templates'
        if not os.path.exists(self.path + '/templates'):
            shutil.copytree(source_template_path, self.path + '/templates')

    def _start_mongo(self):
        # will try 5 times
        for t in range(5):
            s = socket.socket()
            res = s.bind(('127.0.0.1', 0))
            dbport = s.getsockname()[1]
            s.close()
            s = None
            self._mongoprocess = subprocess.Popen([
                'mongod',
                '--bind_ip',
                'localhost',
                '--port', str(dbport),
                '--dbpath', self._mongopath,
                '--nojournal', '--nohttpinterface',
                '--noauth', '--smallfiles',
                '--syncdelay', '0',
                '--maxConns', '10',
                '--nssize', '1', ],
                stdout=open(os.devnull, 'wb'),
                stderr=subprocess.STDOUT

            )

            # it might take some time to bring DB up

            for i in range(3):
                time.sleep(1)
                try:
                    self._dbconn = pymongo.MongoClient('localhost:'+ str(dbport))['luna']
                except pymongo.errors.ConnectionFailure:
                    continue
                else:
                    break
            if self._dbconn:
                break
        if not self._dbconn:
            self.cleanup()
            assert False, 'Cannot connect to the mongodb test instance'

    @property
    def db(self):
        return self._dbconn

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if self._mongoprocess:
            self._mongoprocess.terminate()
            self._mongoprocess.wait()
            self._mongoprocess = None
        else:
            self._mingdatastore.conn.drop_all()
        shutil.rmtree(self.path, ignore_errors=True)
