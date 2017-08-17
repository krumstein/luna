#!/bin/bash
set -e

SCRIPTDIR=$(
  cd $(dirname "$0")
  pwd
)

if [ ! -f ${SCRIPTDIR}/luna.spec.in ]; then
    echo "No luna.spec.in found"
    exit 1
fi

if  ! git describe --tag 2>/dev/null &>/dev/null
then
  VERSION=9999
  BUILD=$(git log --pretty=format:'' | wc -l)
else
  VERSION=$(git describe --tag  | sed -r 's/^v([\.0-9]*)-(.*)$/\1/')
  BUILD=$(git describe --tag  | sed -r 's/^v([\.0-9]*)-(.*)$/\2/' | tr - .)
fi

mkdir -p ${SCRIPTDIR}/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

sed -e "s/__VERSION__/$VERSION/" ${SCRIPTDIR}/luna.spec.in > ${SCRIPTDIR}/SPECS/luna.spec
sed -i "s/__BUILD__/$BUILD/" ${SCRIPTDIR}/SPECS/luna.spec

git archive --format=tar.gz --prefix=luna-${VERSION}-${BUILD}/  -o ${SCRIPTDIR}/SOURCES/v${VERSION}-${BUILD}.tar.gz HEAD

rm -rf ${SCRIPTDIR}/SRPMS/*.rpm
rpmbuild -bs --define '_topdir ./rpm' ${SCRIPTDIR}/SPECS/luna.spec
rm -rf ${SCRIPTDIR}/RPMS/*.rpm
rpmbuild --rebuild --define "_topdir ${SCRIPTDIR}" ${SCRIPTDIR}/SRPMS/*.rpm
