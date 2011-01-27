#!/usr/bin/env python2.5
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
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
from glob import glob
import os, sys

for file in glob('../deps.d/*'):
    sys.path.insert(0, file)

sys.path.insert(0, '..')

from unittest import main

from acceptortest import AcceptorTest
from composetest import ComposeTest
from sidekicktest import SidekickTest
from httpreadertest import HttpReaderTest
from httpservertest import HttpServerTest
from httpspectest import HttpSpecTest
from httpsservertest import HttpsServerTest
from reactortest import ReactorTest
from servertestcasetest import ServerTestCaseTest
from snaketest import SnakeTest
from suspendtest import SuspendTest
from transparentsockettest import TransparentSocketTest
from asyncreadertest import AsyncReaderTest

if __name__ == '__main__':
    main()
