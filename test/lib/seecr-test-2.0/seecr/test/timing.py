## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2005-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2012, 2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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

# Module test.pystone may interfere with default test package
# With this code we temporarily move the beginning of the PYTHON_PATH aside to
# import the good test module.
from sys import path
import sys
from os import stat
from os.path import expanduser, isfile
from time import time


def determineT():
    def pystones(*args, **kwargs):
        from warnings import warn
        warn("Python module 'test.pystone' not available. Will assume T=1.0")
        return 1.0, "ignored"

    pystonesValueFile = expanduser('~/.seecr-test-pystones')
    if isfile(pystonesValueFile):
        age = time() - stat(pystonesValueFile).st_mtime
        if age < 12 * 60 * 60:
            with open(pystonesValueFile) as fp:
                return float(fp.read())

    temppath = []
    while len(path) > 0:
        try:
            if 'test' in sys.modules:
                del sys.modules['test']
            from test.pystone import pystones

            break
        except ImportError:
            temppath.append(path[0])
            del path[0]
    for temp in reversed(temppath):
        path.insert(0, temp)
    del temppath
    T, p = pystones(loops=50000)
    try:
        with open(pystonesValueFile, 'w') as f:
            f.write(str(T))
    except IOError:
        pass
    return T

T = determineT()
print('T=%.1fs' % T)
del determineT

