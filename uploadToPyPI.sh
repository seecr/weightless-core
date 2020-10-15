#!/bin/bash
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2011-2012, 2020 Seecr (Seek You Too B.V.) https://seecr.nl
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

mydir=$(cd $(dirname $0); pwd)

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>
    Will upload Weightless to pypi"
    exit 1
fi

find ${mydir}/ -name '*.py' -exec sed -r -e \
    "/DO_NOT_DISTRIBUTE/d;
    s/\\\$Version:[^\\\$]*\\\$/\\\$Version: ${VERSION}\\\$/" -i '{}' \;

(
    cd $mydir
    python3 setup.py register sdist upload
)
