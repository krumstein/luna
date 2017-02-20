# ///////////////////////////////////////////////
# HOW TO GENERATE LUNA RPM
# ///////////////////////////////////////////////
#
# $ git clone git@github.com:clustervision/luna.git
# $ tar xzf luna.tar.gz luna
# $ rpmbuild -ta luna.tar.gz
#
# ///////////////////////////////////////////////

# ///////////////////////////////////////////////
# LUNA DEFINITION
# ///////////////////////////////////////////////
Name: luna
Version: 2.0
Release: 1%{?dist}

Summary: Luna is a baremetal provisioning tool uses image-based approach
Packager: ClusterVision
License: GNU GPL

Source: https://github.com/clustervision/luna/release/%{name}-%{version}.tar.gz
URL: https://github.com/clustervision/luna
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}

# ///////////////////////////////////////////////
# INTERNAL LUNA DEFINITION
# ///////////////////////////////////////////////
%define luna_home "/trinity/local"

# ///////////////////////////////////////////////
# RPMBUILD DEFINITION
# ///////////////////////////////////////////////
# Disable debuginfo package
%define debug_package %{nil}

# ///////////////////////////////////////////////
# BUILD REQUIREMENTS
# ///////////////////////////////////////////////
BuildRequires: bash  
BuildRequires: sed
BuildRequires: python

# ///////////////////////////////////////////////
# INSTALL REQUIREMENTS
# ///////////////////////////////////////////////
Requires: epel-release
Requires: nginx
Requires: python-tornado
Requires: ipxe-bootimgs
Requires: tftp-server
Requires: tftp
Requires: xinetd
Requires: dhcp
Requires: rb_libtorrent-python
Requires: net-snmp-python
Requires: python-hostlist

Requires(post):  /usr/bin/sed
Requires(post):  /usr/bin/systemctl
Requires(post):  /usr/sbin/useradd,/usr/sbin/userdel
Requires(post):  /usr/sbin/groupadd,/usr/sbin/groupdel
Requires(post):  /usr/bin/chmod,/usr/bin/chown
Requires(post):  /usr/bin/getent,/usr/bin/id

Requires(preun): /usr/bin/systemctl

# ///////////////////////////////////////////////
# DESCRIPTION 
# ///////////////////////////////////////////////
%description
Luna is a baremetal provisioning tool uses image-based-approach. It delivers image of operating systems, but not the 'recipe' how to configure OS, as competotors do. It dramatically speeds up imstallation time, and reduce administrative efforts.
Killer feature of Luna - it is using BitTorrent protocol, so every booting node is becoming provisioner to help others to boot.
It does not iteract with already booted node: torrent client acts only in initrd environment.
Luna does not require any additional service to run on node. By default it changes very limited number of files on booted nodes. Absolute minimun is: /etc/hostname and etc/sysconfig/network-scripts/ifcfg-* files.

# ///////////////////////////////////////////////
# CHILD PACKAGE
# ///////////////////////////////////////////////
%package client
Summary: Kernel module Luna for deployed nodes.
Requires: epel-release
Requires: rb_libtorrent
Requires: dracut-config-generic

%description client
Kernel module Luna for depolyed nodes.

# ///////////////////////////////////////////////
# PREPARATION SECTION
# ///////////////////////////////////////////////
%prep
%setup -n %{name}

# ///////////////////////////////////////////////
# BUILD SECTION
# ///////////////////////////////////////////////
%build

# ///////////////////////////////////////////////
# INSTALL SECTION
# ///////////////////////////////////////////////
%install
# Install files for main package 
install -m 755 src                                     %{buildroot}/luna/src
install -m 755 doc                                     %{buildroot}/luna/doc
install -m 755 test                                    %{buildroot}/luna/test
install -m 755 config                                  %{buildroot}/luna/config
install -m 644 LICENSE                                 %{buildroot}/luna/LICENSE
install -m 644 README.md                               %{buildroot}/luna/README.md
install -m 644 src/system/lweb.service                 %{buildroot}/etc/systemd/system/lweb.service
install -m 644 src/system/ltorrent.service             %{buildroot}/etc/systemd/system/ltorrent.service
install -m 644 src/system/luna_autocomplete.sh         %{buildroot}/etc/profile.d/luna_autocomplete.sh

# Install symlinks
mkdir -p %{buildroot}/usr/sbin
pushd %{buildroot}/usr/sbin
ln -fs /luna/src/exec/luna
ln -fs /luna/src/exec/lpower
ln -fs /luna/src/exec/lweb
ln -fs /luna/src/exec/ltorrent
ln -fs /luna/src/exec/lchroot
popd
mkdir -p %{buildroot}/usr/lib64/python2.7
pushd %{buildroot}/usr/lib64/python2.7
ln -fs /luna/src/module luna
popd

# Create luna home directory
mkdir -p %{buildroot}/%{luna_home}/luna
mkdir -p %{buildroot}/%{luna_home}/luna/{boot,torrents}
install -m 644 src/templates                           %{buildroot}/%{luna_home}/luna/templates

# Create luna system directories
mkdir -p %{buildroot}/var/log/luna
mkdir -p %{buildroot}/var/run/luna

# Install dracut files for local trinity
install -m 644 src/dracut/95luna/bashrc                %{buildroot}/trinity/local/luna/dracut/95luna/bashrc
install -m 755 src/dracut/95luna/ltorrent-client       %{buildroot}/trinity/local/luna/dracut/95luna/ltorrent-client
install -m 755 src/dracut/95luna/luna-parse-cmdline.sh %{buildroot}/trinity/local/luna/dracut/95luna/luna-parse-cmdline.sh
install -m 755 src/dracut/95luna/luna-start.sh         %{buildroot}/trinity/local/luna/dracut/95luna/luna-start.sh
install -m 755 src/dracut/95luna/module-setup.sh       %{buildroot}/trinity/local/luna/dracut/95luna/module-setup.sh
install -m 644 src/dracut/95luna/profile               %{buildroot}/trinity/local/luna/dracut/95luna/profile
install -m 644 src/dracut/95luna/sshd_config           %{buildroot}/trinity/local/luna/dracut/95luna/sshd_config

# Setup TFTP
mkdir -p %{buildroot}/tftpboot
install -m 644 /usr/share/ipxe/undionly.kpxe           %{buildroot}/tftpboot/luna_undionly.kpxe

# Setup DNS
mkdir -p %{buildroot}/etc
touch %{buildroot}/etc/named.luna.zones

# Setup NGINX
mkdir -p %{buildroot}/etc/nginx/conf.d
install -m 644 config/nginx/nginx.conf                 %{buildroot}/etc/nginx/nginx.conf
install -m 644 config/nginx/luna.conf                  %{buildroot}/etc/nginx/conf.d/nginx-luna.conf
sed -i "s|/opt|%{luna_home}|g" %{buildroot}/etc/nginx/conf.d/nginx-luna.conf

# Install files for client package
install -m 644 src/dracut/95luna/bashrc                %{buildroot}/usr/lib/dracut/modules.d/95luna/bashrc
install -m 755 src/dracut/95luna/ltorrent-client       %{buildroot}/usr/lib/dracut/modules.d/95luna/ltorrent-client
install -m 755 src/dracut/95luna/luna-parse-cmdline.sh %{buildroot}/usr/lib/dracut/modules.d/95luna/luna-parse-cmdline.sh
install -m 755 src/dracut/95luna/luna-start.sh         %{buildroot}/usr/lib/dracut/modules.d/95luna/luna-start.sh
install -m 755 src/dracut/95luna/module-setup.sh       %{buildroot}/usr/lib/dracut/modules.d/95luna/module-setup.sh
install -m 644 src/dracut/95luna/profile               %{buildroot}/usr/lib/dracut/modules.d/95luna/profile
install -m 644 src/dracut/95luna/sshd_config           %{buildroot}/usr/lib/dracut/modules.d/95luna/sshd_config

# ///////////////////////////////////////////////
# CLEAN SECTION
# ///////////////////////////////////////////////
%clean
rm -rf $RPM_BUILD_ROOT

# ///////////////////////////////////////////////
# PRE INSTALLATION PHASE
# ///////////////////////////////////////////////
%pre
case "$1" in
    # This is an initial install.
    1)
        # Stop some services
        /usr/bin/systemctl stop dhcpd xinetd nginx 2>/dev/null || /usr/bin/true
        /usr/bin/systemctl stop lweb ltorrent 2>/dev/null || /usr/bin/true
    ;;

    # This is an upgrade.
    2)
        # Stop some services
        /usr/bin/systemctl stop dhcpd xinetd nginx 2>/dev/null || /usr/bin/true
        /usr/bin/systemctl stop lweb ltorrent 2>/dev/null || /usr/bin/true
    ;;
esac
exit 0

# ///////////////////////////////////////////////
# POST INSTALLATION PHASE
# ///////////////////////////////////////////////
%post
case "$1" in
    # This is an initial install (1) or an upgrade (2).
    [1-2])
        # Define TRIX_SHFILE
        TRIX_SHFILE="/etc/trinity.sh"

        # Check if a trinity environment exists
        if [[ -f ${TRIX_SHFILE} ]];then
            source ${TRIX_SHFILE}
        fi

        # Delete luna user if exists
        if /usr/bin/id -u luna >/dev/null 2>&1; then
            /usr/sbin/userdel luna
        fi

        # Delete luna group if exists
        if /usr/bin/grep -q -E "^luna:" /etc/group ; then
            /usr/sbin/groupdel luna
        fi

        # Create luna group
        /usr/sbin/groupadd -r ${LUNA_GROUP_ID:+"-g $LUNA_GROUP_ID"} luna
        if grep -q "^LUNA_GROUP_ID=" ${TRIX_SHFILE}; then
            sed -i "s|^LUNA_GROUP_ID=.*$|LUNA_GROUP_ID=$LUNA_GROUP_ID|" ${TRIX_SHFILE}
        else
            echo "LUNA_GROUP_ID=$(/usr/bin/getent group | /usr/bin/awk -F\: '$1==\"luna\"{print $3}')" >> ${TRIX_SHFILE}
        fi

        # Create luna user
        /usr/sbin/useradd -r ${LUNA_USER_ID:+"-u $LUNA_USER_ID"} -g luna -d %{luna_home}/luna luna
        if grep -q "^LUNA_USER_ID=" ${TRIX_SHFILE}; then
            sed -i "s|^LUNA_USER_ID=.*$|LUNA_USER_ID=$LUNA_USER_ID|" ${TRIX_SHFILE}
        else
            echo "LUNA_USER_ID=$(/usr/bin/id -u luna)" >> ${TRIX_SHFILE}
        fi

        # Setup TFTP
        /usr/bin/sed -e 's/^\(\W\+disable\W\+\=\W\)yes/\1no/g' -i /etc/xinetd.d/tftp
        /usr/bin/sed -e 's|^\(\W\+server_args\W\+\=\W-s\W\)/var/lib/tftpboot|\1/tftpboot|g' -i /etc/xinetd.d/tftp

        # Setup DNS
        echo "include \"/etc/named.luna.zones\";" > /etc/named.conf

        # Set permission on luna directories
        /usr/bin/chown -R luna: %{luna_home}/luna
        /usr/bin/chmod ag+rx %{luna_home}/luna
        /usr/bin/chown -R luna: /var/log/luna
        /usr/bin/chown -R luna: /var/run/luna

        # Reload systemd config and start services.
        /usr/bin/systemctl daemon-reload
        /usr/bin/systemctl start lweb ltorrent
        /usr/bin/systemctl start dhcpd xinetd nginx
        /usr/bin/systemctl enable dhcpd xinetd nginx lweb ltorrent
    ;;
esac
exit 0

%post client
case "$1" in
    # This is an initial install (1) or an upgrade (2).
    [1-2])
        if [ -f /etc/fstab ]; then
            touch /etc/fstab
            chown root:root /etc/fstab
            chmod 644 /etc/fstab
        fi
    ;;
esac
exit 0

# ///////////////////////////////////////////////
# PRE REMOVE PHASE
# ///////////////////////////////////////////////
%preun
case "$1" in
    # This is an un-installation (0) or an upgrade (1).
    [0-1])
        # Stop luna services
        /usr/bin/systemctl stop lweb ltorrent 2>/dev/null || /usr/bin/true
    ;;
esac
exit 0

# ///////////////////////////////////////////////
# POST REMOVE PHASE
# ///////////////////////////////////////////////
%postun
case "$1" in
    # This is an un-installation (0) or an upgrade (1).
    [0-1])
        # Reload systemd config.
        /usr/bin/systemctl daemon-reload
    ;;
esac
exit 0

# ///////////////////////////////////////////////
# LIST FILES SECTION
# ///////////////////////////////////////////////
%files
%defattr(-, root, root)
/luna/src
/luna/doc
/luna/test
/luna/config
/luna/LICENSE
/luna/README.md
/usr/sbin/luna
/usr/sbin/lpower
/usr/sbin/lweb
/usr/sbin/ltorrent
/usr/sbin/lchroot
/usr/lib64/python2.7/luna
/etc/systemd/system/lweb.service
/etc/systemd/system/ltorrent.service
/etc/profile.d/luna_autocomplete.sh
%{luna_home}/luna/{boot,templates,torrents}
/trinity/local/luna/dracut
/tftpboot/luna_undionly.kpxe
/etc/named.luna.zones
/etc/nginx/nginx.conf
/etc/nginx/conf.d/nginx-luna.conf

%files client
%defattr(-,root,root)
/usr/lib/dracut/modules.d/95luna

# ///////////////////////////////////////////////
# CHANGELOG
# ///////////////////////////////////////////////
%changelog
 * Thu Feb 16 2017 Cedric Castagnede <cedric.castagnede@clustervision.com> 2.0
 - First version of this spec file.
