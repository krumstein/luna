import rpm
import os
import shutil
import socket
import time
import tempfile
import pymongo
import subprocess


specfile_template = """
Name:                   kernel
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

%files
"""
def mock_osimage_tree(osimage_path, kern_versions = ['1.0.0']):

    rpmtsCallback_fd = None

    def runCallback(reason, amount, total, key, client_data):
        global rpmtsCallback_fd
        if reason == rpm.RPMCALLBACK_INST_OPEN_FILE:
            rpmtsCallback_fd = os.open(key, os.O_RDONLY)
            return rpmtsCallback_fd
        elif reason == rpm.RPMCALLBACK_INST_START:
            os.close(rpmtsCallback_fd)

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
        spec_content = specfile_template.format(version = kern_ver, release = kern_release)
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
            print "ERROR: Unable to build rpm"
            raise RuntimeError
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

        return True

def create_luna_homedir(path):
    if not os.path.exists(path):
        os.makedirs(path)
    if 'VIRTUAL_ENV' not in os.environ:
        print "Runinning not in virtual environment"
        virtual_env_path = '/'
    else:
        virtual_env_path = os.environ['VIRTUAL_ENV']
    for d in ['boot', 'torrents']:
        if not os.path.exists(path + '/' + d):
            os.makedirs(path + '/' + d)
    source_template_path = virtual_env_path + '/usr/share/luna/templates'
    if not os.path.exists(path + '/templates'):
        shutil.copytree(source_template_path, path + '/templates')

class sandbox(object):

    def __init__(self, path = None):

        if not path:
            self.path = tempfile.mkdtemp()
        else:
            # can cause race condition, but ok
            if not os.path.exists(path):
                os.makedirs(path)
            self.path = path
        self._dbconn = None
        # TODO
        # check if mongod binary exists
        self._mongopath = self.path + "/mongo"
        if not os.path.exists(self._mongopath):
            os.makedirs(self._mongopath)
        self._mongoprocess = None
        try:
            self._start_mongo(
            self.dbtype = 'mongo'
        except OSError:
            import ming
            self._mingdatastore = ming.create_datastore('mim:///luna')
            self._dbconn = self._mingdatastore.db.luna
            self.dbtype = 'ming'
            
    def _start_mongo(self):
        self._mongoprocess = None
        # will try 5 times
        for t in range(5):
            s = socket.socket()
            res = s.bind(('127.0.0.1', 0))
            dbport = s.getsockname()[1]
            s.close()
            s = None
            self._mongoprocess = subprocess.Popen(['mongod', '--bind_ip', 'localhost',
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
            print dbport

            for i in range(3):
                time.sleep(1)
                try:
                    self._dbconn = pymongo.MongoClient('localhost:'+ str(dbport))['luna']
                except pymongo.errors.ConnectionFailure:
                    print "+++"
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
