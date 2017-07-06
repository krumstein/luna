#!/bin/bash
set -e
VERSION=$(git describe --tag  | sed -r 's/^v([\.0-9]*)-(.*)$/\1/')
BUILD=$(git describe --tag  | sed -r 's/^v([\.0-9]*)-(.*)$/\2/' | tr - .)
sed -e "s/__VERSION__/$VERSION/" rpm/luna.spec.in > rpm/luna.spec
sed -i "s/__BUILD__/$BUILD/" rpm/luna.spec    

git archive --format=tar.gz --prefix=luna-${VERSION}-${BUILD}/  -o ~/rpmbuild/SOURCES/v${VERSION}-${BUILD}.tar.gz HEAD

rpmbuild -bs rpm/luna.spec
rm rpm/luna.spec
