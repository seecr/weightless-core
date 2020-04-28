
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015 Seecr (Seek You Too B.V.) http://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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

from weightlesstestcase import WeightlessTestCase
from seecr.test.io import stdout_replaced
from seecr.test.portnumbergenerator import PortNumberGenerator

from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, SOL_TCP, TCP_CORK, TCP_NODELAY
from socket import socketpair, socket
from struct import pack
from time import sleep

from weightless.io import Reactor, reactor, Gio, giopen
from weightless.io.utils import asProcess
from weightless.io._gio import Context, SocketContext, Timer, TimeoutException

class GioTest(WeightlessTestCase):

    def testOpenReturnsContextManager(self):
        result = giopen('httptest/data/testdata5kb')
        self.assertTrue(hasattr(result, '__enter__'))
        self.assertTrue(hasattr(result, '__exit__'))

    def testYieldWithoutContext(self):
        def test():
            done = []
            def handler():
                yield
                yield 'a'
                done.append(True)
            try:
                g = Gio(reactor(), handler())
                self.fail('must not come here')
            except AssertionError as e:
                self.assertEqual('Gio: No context available.', str(e))

            return
            yield

        asProcess(test())

    def testNeverExittedContextIsForcedToExitByGeneratorExitWhileWriting(self):
        lhs, rhs = socketpair()
        try:
            context = SocketContext(lhs)  # quick hack, can block.
            def neverExit():
                with context:
                    while True: # never exit context, unless with exception
                        yield 'ape'
            proc = neverExit()
            g = Gio(self.reactor, proc)
            self.reactor.step()
            try:
                proc.throw(GeneratorExit()) # force exit outside Gio()
                self.fail('Must not come here')
            except StopIteration:
                pass
            self.assertEqual([], g._contextstack)
        finally:
            lhs.close(); rhs.close()

    def XXXXXXXXXXXXXtestNeverExittedContextIsForcedToExitByGeneratorExitWhileReading(self):
        context =  giopen(self.tempfile, 'rw')
        def neverExit():
            with context:
                while True: # never exit context, unless with exception
                    yield
        proc = neverExit()
        g = Gio(self.reactor, proc)
        self.reactor.step()
        try:
            proc.throw(GeneratorExit()) # force exit outside Gio()
            self.fail('Must not come here')
        except GeneratorExit:
            pass
        self.assertEqual([], g._contextstack)

    def XXXtestGioAsContext(self):
        # TS: Disabled: file-contexts don't work with epoll' Reactor since a file-fd is *always* readable and writable.
        open(self.tempfile, 'w').write('read this!')
        def myProcessor():
            with giopen(self.tempfile, 'rw') as datastream:
                self.assertTrue(isinstance(datastream, Context))
                self.dataIn = yield
                yield 'write this!'
        Gio(self.reactor, myProcessor())
        self.reactor.step()
        self.assertEqual('read this!', self.dataIn[:19])
        self.reactor.step()
        self.assertEqual('read this!write this!', open(self.tempfile).read()[:21])
        self.assertEqual({}, self.reactor._readers)
        self.assertEqual({}, self.reactor._writers)

    def XXXtestAlternate(self):
        # TS: Disabled: file-contexts don't work with epoll' Reactor since a file-fd is *always* readable and writable.
        done = []
        open(self.tempdir+'/1', 'w').write('1234')
        open(self.tempdir+'/2', 'w').write('abcd')
        def swapContents():
            numbersStream = giopen(self.tempdir+'/1', 'rw')
            lettersStream = giopen(self.tempdir+'/2', 'rw')
            with numbersStream:
                numbers = yield
            with lettersStream:
                letters = yield
                yield numbers
            with numbersStream:
                yield letters
            done.append(True)
        Gio(self.reactor, swapContents())
        with self.loopingReactor():
            while not done:
                pass
        self.assertEqual('1234abcd', open(self.tempdir+'/1').read())
        self.assertEqual('abcd1234', open(self.tempdir+'/2').read())

    def XXXtestNesting(self):
        # TS: Disabled: file-contexts don't work with epoll' Reactor since a file-fd is *always* readable and writable.
        done = []
        open(self.tempdir+'/1', 'w').write('1234')
        open(self.tempdir+'/2', 'w').write('abcd')
        def swapContents():
            numbersStream = giopen(self.tempdir+'/1', 'rw')
            lettersStream = giopen(self.tempdir+'/2', 'rw')
            with numbersStream:
                numbers = yield
                with lettersStream:
                    letters = yield
                    yield numbers
                yield letters
            done.append(True)
        Gio(self.reactor, swapContents())
        while not done:
            self.reactor.step()
        self.assertEqual('1234abcd', open(self.tempdir+'/1').read())
        self.assertEqual('abcd1234', open(self.tempdir+'/2').read())

    def testSocketHandshake(self):
        with Reactor() as reactor:
            lhs, rhs = socketpair()
            def peter(channel):
                with channel:
                    message = yield
                    yield 'Hello ' + message.decode()[-4:]
            def jack(channel):
                with channel:
                    x = yield 'My name is Jack'
                    self.assertEqual(None, x)
                    self.response = yield
            Gio(reactor, jack(SocketContext(lhs)))
            Gio(reactor, peter(SocketContext(rhs)))
            reactor.step().step().step().step()
            self.assertEqual(b'Hello Jack', self.response)

    def testLargeBuffers(self):
        with stdout_replaced():
            with Reactor() as reactor:
                lhs, rhs = socketpair()
                messages = []
                messageSize = 1024*128
                def peter(channel):
                    with channel:
                        while True:
                            messages.append((yield))
                def jack(channel):
                    with channel:
                        yield 'X' * messageSize
                jack_socketContext = jack(SocketContext(lhs))
                peter_socketContext = peter(SocketContext(rhs))
                try:
                    Gio(reactor, jack_socketContext)
                    Gio(reactor, peter_socketContext)
                    while sum(len(message) for message in messages) < messageSize:
                        reactor.step()
                    self.assertTrue(len(messages) > 1) # test is only sensible when multiple parts are sent
                    self.assertEqual(messageSize, len(b''.join(messages)))
                finally:
                    jack_socketContext.close()
                    peter_socketContext.close()

    def testHowToCreateAHttpServer(self):
        port = next(PortNumberGenerator)
        # SERVER
        class HttpServer:
            def __init__(self, reactor, port):
                ear = socket()
                ear.bind(('0.0.0.0', port))
                ear.listen(127)
                ear.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                reactor.addReader(ear, self)
                self._ear = ear
                self._reactor = reactor
            def __call__(self):
                connection, address = self._ear.accept()
                Gio(self._reactor, self.handleConnection(SocketContext(connection)))
            def handleConnection(self, connection):
                with connection:
                    yield self.handleRequest()
            def handleRequest(self):
                msg = yield
                yield 'HTTP/1.1 200 Ok\r\n\r\nGoodbye'
            def stop(self):
                self._reactor.removeReader(self._ear)
                self._ear.close()
        server = HttpServer(self.reactor, port)
        #CLIENT
        responses = []
        def connection(host, port):
            connection = socket()
            connection.connect((host, port))
            return SocketContext(connection)
        def httpClient():
            with connection('localhost', port):
                yield 'GET %s HTTP/1.0\r\n\r\n' % '/'
                response = yield
                responses.append(response)
        Gio(self.reactor, httpClient())
        while not responses:
            self.reactor.step()
        self.assertEqual([b'HTTP/1.1 200 Ok\r\n\r\nGoodbye'], responses)
        server.stop()

    def testTimerDoesNotFire(self):
        def test():
            done = []
            def handler():
                lhs, rhs = socketpair()
                try:
                    with SocketContext(lhs):  # quick hack, can block.
                        with Timer(0.01):
                            yield 'a'
                        yield 'b'
                finally:
                    lhs.close(); rhs.close()
                done.append(True)
            g = Gio(reactor(), handler())
            for _ in range(42):
                yield
            self.assertEqual([True], done)
            self.assertEqual([], reactor()._timers)
            self.assertEqual([], g._contextstack)

        asProcess(test())

    def testTimerTimesOutOutsideBlock(self):
        def test():
            done = []
            def handler():
                lhs, rhs = socketpair()
                try:
                    with SocketContext(lhs):  # quick hack, can block.
                        with Timer(0.01):
                            for i in range(999999):
                                yield 'a'
                except TimeoutException:
                    done.append(False)
                finally:
                    lhs.close; rhs.close()
                yield
            g = Gio(reactor(), handler())
            while not done:
                yield
            self.assertEqual([False], done)
            self.assertEqual([], reactor()._timers)
            self.assertEqual([], g._contextstack)

        asProcess(test())

    def testTimerTimesOutWithinBlock(self):
        def test():
            done = []
            def handler():
                lhs, rhs = socketpair()
                try:
                    with SocketContext(lhs):  # quick hack, can block.
                        with Timer(0.01):
                            try:
                                for i in range(999999):
                                    yield 'a'
                            except TimeoutException:
                                done.append(False)
                finally:
                    lhs.close(); rhs.close()
                yield
            g = Gio(reactor(), handler())
            while done != [False]:
                yield
            self.assertEqual([False], done)
            self.assertEqual([], reactor()._timers)
            self.assertEqual([], g._contextstack)

        asProcess(test())
