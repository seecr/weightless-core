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

from os import getuid
assert getuid() != 0, "Do not run tests as 'root'"

from sys import path as sysPath
from glob import glob
for path in glob('lib/*'):
    sysPath.insert(0, path)

from os import system                             #DO_NOT_DISTRIBUTE
system('find .. -name "*.pyc" | xargs rm -f')     #DO_NOT_DISTRIBUTE
                                                  #DO_NOT_DISTRIBUTE
for path in glob('../deps.d/*'):                  #DO_NOT_DISTRIBUTE
    sysPath.insert(0, path)                       #DO_NOT_DISTRIBUTE
sysPath.insert(0,'..')                            #DO_NOT_DISTRIBUTE

from unittest import main
from types import GeneratorType

from weightless.core.compose import ComposeType
if ComposeType == GeneratorType:
    from core.composetest import ComposePyTest
else:
    from core.composetest import ComposeCTest
from core.localtest import LocalTest
from core.composeschedulingtest import ComposeSchedulingPyTest
from core.composefiltertest import ComposeFilterPyTest

from http.acceptortest import AcceptorTest
from http.httpreadertest import HttpReaderTest
from http.httpservertest import HttpServerTest
from http.httpspectest import HttpSpecTest
from http.httpsservertest import HttpsServerTest
from http.suspendtest import SuspendTest
from http.asyncreadertest import AsyncReaderTest

from core.observabletest import ObservableTest
from core.observabledirectedmessagingtest import ObservableDirectedMessagingTest

from io.reactortest import ReactorTest
from io.giotest import GioTest
from io.gutilstest import GutilsTest
from io.servertest import ServerTest

#from httpng.httpprotocolintegrationtest import HttpProtocolIntegrationTest
#from httpng.httpprotocoltest import HttpProtocolTest

if __name__ == '__main__':
    main()
