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
from __future__ import with_statement
from servertestcase import ServerTestCase
from socket import socket

class ServerTestCaseTest(ServerTestCase):

    def testWithRealSocket(self):
        with self.server(['response one', 'response two']) as (port, messages):
            client = socket()
            client.connect(('127.0.0.1', port))
            client.send('aap')
            response = client.recv(999)
            self.assertEquals('response one', response)
            client.send('noot')
            response = client.recv(999)
            self.assertEquals('response two', response)
        self.assertEquals('aap', messages[0])
        self.assertEquals('noot', messages[1])

