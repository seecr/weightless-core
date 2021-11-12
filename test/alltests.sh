#!/bin/bash
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2011-2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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
export PYTHONWARNINGS=default

option=$1
if [ "$option" == "--python" ]; then
        shift
        tests=PYTHON
elif [ "$option" == "--c" ]; then
        shift
        tests=C
else
    tests="C PYTHON"
fi

echo Performing tests: $tests

# for t in $tests; do
#     echo "================ $t with python3 _alltests.py $@ ================"
#     WEIGHTLESS_COMPOSE_TEST=$t pdb _alltests.py "$@"
    # WEIGHTLESS_COMPOSE_TEST=$t python3 _alltests.py "$@"
# done

WEIGHTLESS_COMPOSE_TEST=C pdb _alltests.py
