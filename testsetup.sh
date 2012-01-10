## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
set -e

rm -rf tmp build
for pycmd in $(pyversions --installed); do

$pycmd setup.py install --root tmp

VERSION="x.y.z"

find tmp -name '*.py' -exec sed -r -e \
    "/DO_NOT_DISTRIBUTE/ d;
    s/\\\$Version:[^\\\$]*\\\$/\\\$Version: ${VERSION}\\\$/" -i '{}' \;

if [ "$pycmd" == "python2.5" ]; then
    export PYTHONPATH=`pwd`/tmp/usr/lib/python2.5/site-packages
else
    export PYTHONPATH=`pwd`/tmp/usr/local/lib/python2.6/dist-packages
fi
cp -r test tmp/test

(
cd tmp/test
./alltests.sh --${pycmd}
)

rm -rf tmp build
done
