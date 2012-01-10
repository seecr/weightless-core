## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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
from urllib2 import urlopen
from StringIO import StringIO
import socket
import sys
from select import select

from weightlesstestcase import WeightlessTestCase

from weightless.io import Server

class ServerTest(WeightlessTestCase):

    def testListen(self):
        server = Server(self.reactor, self.port)
        self.send('localhost', self.port, 'are you listening?')
        server.stop()

    def testConnect(self):
        messages = []
        class Interceptor(object):
            def processConnection(self):
                messages.append((yield))
        server = Server(self.reactor, self.port)
        server.addObserver(Interceptor())
        sok = self.send('localhost', self.port, 'a message')
        self.reactor.step().step()
        self.assertEquals(['a message'], messages)
        sok.close()
        server.stop()

    def testConnectionNotProcessedRaisesError(self):
        server = Server(self.reactor, self.port)
        sok = self.send('localhost', self.port, 'a message')
        sys.stderr = StringIO()
        try:
            self.reactor.step()
            self.assertTrue('None of the 0 observers respond to processConnection(...)' in sys.stderr.getvalue())
        finally:
            sys.stderr = sys.__stderr__
        sok.close()
        server.stop()

    def testShutdownAndClose(self):
        class Interceptor(object):
            def processConnection(self):
                yield 'over en uit'
        server = Server(self.reactor, self.port)
        server.addObserver(Interceptor())
        connection = self.send('localhost', self.port, 'a message')
        while connection not in select([connection],[],[],0)[0]:
            self.reactor.step()
        self.assertEquals('over en uit', connection.recv(99))
        try:
            connection.send('aap')
            self.fail('connection is closed, this must raise an io error')
        except socket.error, e:
            pass
        connection.close()
        server.stop()

    def testShutdownAndCloseInCaseOfException(self):
        class Interceptor(object):
            def processConnection(self):
                raise Exception('oops')
                yield 'over en uit'
        server = Server(self.reactor, self.port)
        server.addObserver(Interceptor())
        connection = self.send('localhost', self.port, 'a message')
        sys.stderr = StringIO()
        try:
            self.reactor.step()
        finally:
            sys.stderr = sys.__stderr__
        try:
            connection.send('aap')
            self.fail('connection is closed, this must raise an io error')
        except socket.error, e:
            pass
        connection.close()
        server.stop()

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
        self.assertEquals('Goodbye Thijs', conn1.recv(99))
        self.assertEquals('Goodbye Johan', conn2.recv(99))
        self.assertEquals('Goodbye Klaas', conn3.recv(99))
        conn1.close()
        conn2.close()
        conn3.close()
        server.stop()

#TOTEST:
# - error in processConnection
# - leave connection open if ..... for ... seconds (apache keeps it open for approx 5)
