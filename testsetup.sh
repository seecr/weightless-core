#!/bin/bash
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
# 
# This file is part of "Weightless"
# 
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
## end license ##

set -o errexit
rm -rf tmp build
mydir=$(cd $(dirname $0); pwd)
source ${mydir}/test/lib/seecr-test-1.2.50/share/_distro
source ${mydir}/test/lib/seecr-test-1.2.50/share/functions

pyversions="2.6"
if distro_is_debian_wheezy; then
    pyversions="2.6 2.7"
fi

VERSION="x.y.z"

for pyversion in $pyversions; do
    definePythonVars $pyversion
    echo "###### $pyversion, $PYTHON"
    ${PYTHON} setup.py install --root tmp
done
cp -r test tmp/test
removeDoNotDistribute tmp
find tmp -name '*.py' -exec sed -r -e "
    s/\\\$Version:[^\\\$]*\\\$/\\\$Version: ${VERSION}\\\$/;
    " -i '{}' \;

runtests "$@"

rm -rf tmp build
