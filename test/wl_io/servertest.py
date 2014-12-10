## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013 Seecr (Seek You Too B.V.) http://seecr.nl
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

import socket
from select import select

from weightlesstestcase import WeightlessTestCase

from weightless.io import Server
from seecr.test.io import stderr_replaced

class ServerTest(WeightlessTestCase):

    def testListen(self):
        with Server(self.reactor, self.port) as server:
            with self.send('localhost', self.port, b'are you listening?') as sok:
                pass

    def testConnect(self):
        messages = []
        class Interceptor(object):
            def processConnection(self):
                messages.append((yield))
        with Server(self.reactor, self.port) as server:
            server.addObserver(Interceptor())
            with self.send('localhost', self.port, b'a message') as sok:
                self.reactor.step().step()
                self.assertEqual([b'a message'], messages)

    def testConnectionNotProcessedRaisesError(self):
        with Server(self.reactor, self.port) as server:
            with self.send('localhost', self.port, b'a message') as sok:
                with stderr_replaced() as stderr:
                    self.reactor.step()
                    self.assertTrue('None of the 0 observers respond to processConnection(...)' in stderr.getvalue(), stderr.getvalue())

    def testShutdownAndClose(self):
        class Interceptor(object):
            def processConnection(self):
                yield b'over en uit'
        with Server(self.reactor, self.port) as server:
            server.addObserver(Interceptor())
            with self.send('localhost', self.port, b'a message') as connection:
                while connection not in select([connection],[],[],0)[0]:
                    self.reactor.step()
                self.assertEqual(b'over en uit', connection.recv(99))
                try:
                    connection.send(b'aap')
                    self.fail('connection is closed, this must raise an io error')
                except socket.error as e:
                    pass

    def testShutdownAndCloseInCaseOfException(self):
        class Interceptor(object):
            def processConnection(self):
                raise Exception('oops')
                yield 'over en uit'
        with Server(self.reactor, self.port) as server:
            server.addObserver(Interceptor())
            with self.send('localhost', self.port, b'a message') as connection:
                with stderr_replaced() as s:
                    self.reactor.step()
                    self.assertTrue('Exception: oops' in s.getvalue(), s.getvalue())
                try:
                    connection.send(b'aap')
                    self.fail('connection is closed, this must raise an io error')
                except socket.error as e:
                    pass

    def XXXXXXXXXXXXXXXXtestMultipleConnectionsAndSomeShortConversation(self):
        class MyHandler(object):
            def processConnection(self):
                message = yield
                yield 'Goodbye ' + message
        server = Server(self.reactor, self.port)
        server.addObserver(MyHandler())
        conn3 = self.send('localhost', self.port, 'Klaas')
        conn1 = self.send('localhost', self.port, 'Thijs')
        conn2 = self.send('localhost', self.port, 'Johan')
        readable = []
        while conn1 not in readable or conn2 not in readable or conn3 not in readable:
            self.reactor.step()
            readable = select([conn1, conn2, conn3],[],[],0)[0]
        self.assertEqual('Goodbye Thijs', conn1.recv(99))
        self.assertEqual('Goodbye Johan', conn2.recv(99))
        self.assertEqual('Goodbye Klaas', conn3.recv(99))
        conn1.close()
        conn2.close()
        conn3.close()
        server.stop()

#TOTEST:
# - error in processConnection
# - leave connection open if ..... for ... seconds (apache keeps it open for approx 5)
