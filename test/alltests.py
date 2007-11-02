#!/usr/bin/env python
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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
#
from platform import python_version
from glob import glob
import os, sys

for file in glob('../deps.d/*'):
    sys.path.insert(0, file)

if os.environ.get('PYTHONPATH', '') == '':
    sys.path.insert(0, '..')

import unittest

# Python >= 2.4
from acceptortest import AcceptorTest
from reactortest import ReactorTest
from httpreadertest import HttpReaderTest
from httpservertest import HttpServerTest
from transparentsockettest import TransparentSocketTest

if python_version() >= "2.5":
    from composetest import ComposePythonTest, ComposePyrexTest
    from giotest import GioTest
else:
    print 'Skipping Python 2.5 tests.'

if __name__ == '__main__':
	unittest.main()
