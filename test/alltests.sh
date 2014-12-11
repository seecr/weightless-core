#!/bin/bash
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2011-2014 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2011 Seek You Too (CQ2) http://www.cq2.nl
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

export LANG=en_US.UTF-8
export PYTHONPATH=.:"$PYTHONPATH"

option=$1
if [ "$option" == "--python" ]; then
        tests=PYTHON
elif [ "$option" == "--c" ]; then
        tests=C
else
    tests="C PYTHON"
fi
echo Performing tests: $tests

pyversions="python3"
for t in $tests; do
    for pycmd in $pyversions; do
        echo "================ $t with $pycmd _alltests.py $@ ================"
        #WEIGHTLESS_COMPOSE_TEST=$t gdb --args $pycmd _alltests.py "$@"
        WEIGHTLESS_COMPOSE_TEST=$t $pycmd -W ignore _alltests.py "$@"
    done
done
