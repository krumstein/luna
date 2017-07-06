To make a new source package just run the build.sh script. This script takes the current tags with git describe --tags, e.g.:
$ git describe --tags
v1.2-0.1-10-g45fa8ba

And splits to get verstion and release. In that case, version would be 1.2 and release would be 0.1.10.g45fa8ba. 
The "10" means, that there's 10 commits on top of current tags. The "g45fa8ba" is the git commit hash. 
After that is applies these information to luna.spec.in in order to produce the luna.spec file.
This scripts can be used with rpm building service. You need a "mock" to create clean chroots. The command to build the package:

bash rpm/build.sh
LATEST=$(/bin/ls -ltr ~/rpmbuild/SRPMS/ | tail -1 |  awk '{print $9}')
mock -r  rpm/luna-7-x86_64.cfg  rebuild ~/rpmbuild/SRPMS/${LATEST}

The compiled would be in /var/lib/mock/epel-7-x86_64/result/


You can also build using standart rpmbuild, but in that case you'll need to install required packages:

bash rpm/build.sh
sudo yum install  python-docutils rb_libtorrent-devel boost-devel
LATEST=$(/bin/ls -ltr ~/rpmbuild/SRPMS/ | tail -1 |  awk '{print $9}')
rpmbuild --rebuild ~/rpmbuild/SRPMS/${LATEST} 


