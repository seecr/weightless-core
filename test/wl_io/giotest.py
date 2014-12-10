
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012 Seecr (Seek You Too B.V.) http://seecr.nl
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

from socket import socketpair, socket
from socket import SOL_SOCKET, SO_REUSEADDR, SO_LINGER, SOL_TCP, TCP_CORK, TCP_NODELAY
from struct import pack
from time import sleep
from random import randint

from weightlesstestcase import WeightlessTestCase

from weightless.io import Reactor, Gio, giopen
from weightless.io._gio import Context, SocketContext, Timer, TimeoutException

class GioTest(WeightlessTestCase):

    def testOpenReturnsContextManager(self):
        result = giopen('_http/data/testdata5kb')
        self.assertTrue(hasattr(result, '__enter__'))
        self.assertTrue(hasattr(result, '__exit__'))

    def testYieldWithoutContext(self):
        done = []
        def handler():
            yield
            yield 'a'
            done.append(True)
        try:
            g = Gio(self.mockreactor, handler())
            self.fail('must not come here')
        except AssertionError as e:
            self.assertEqual('Gio: No context available.', str(e))

    def testNeverExittedContextIsForcedToExitByGeneratorExitWhileWriting(self):
        context =  giopen(self.tempfile, 'rw')
        def neverExit():
            with context:
                while True: # never exit context, unless with exception
                    yield b'ape'
        proc = neverExit()
        g = Gio(self.reactor, proc)
        self.reactor.step()
        try:
            proc.throw(GeneratorExit()) # force exit outside Gio()
            self.fail('Must not come here')
        except StopIteration:
            pass
        self.assertEqual([], g._contextstack)

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

    def testGioAsContext(self):
        with open(self.tempfile, 'w') as fp:
            fp.write('read this!')
        def myProcessor():
            with giopen(self.tempfile, 'rw') as datastream:
                self.assertTrue(isinstance(datastream, Context))
                self.dataIn = yield
                yield b'write this!'
        Gio(self.reactor, myProcessor())
        self.reactor.step()
        self.assertEqual(b'read this!', self.dataIn[:19])
        self.reactor.step()
        self.assertEqual('read this!write this!', open(self.tempfile).read()[:21])
        self.assertEqual({}, self.reactor._readers)
        self.assertEqual({}, self.reactor._writers)

    def testAlternate(self):
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

    def testNesting(self):
        done = []
        with open(self.tempdir+'/1', 'w') as fp:
            fp.write('1234')
        with open(self.tempdir+'/2', 'w') as fp:
            fp.write('abcd')
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
                    yield b'Hello ' + message[-4:]
            def jack(channel):
                with channel:
                    x = yield b'My name is Jack'
                    self.assertEqual(None, x)
                    self.response = yield
            Gio(reactor, jack(SocketContext(lhs)))
            Gio(reactor, peter(SocketContext(rhs)))
            reactor.step().step().step().step()
            self.assertEqual(b'Hello Jack', self.response)

    def testLargeBuffers(self):
        reactor = Reactor()
        lhs, rhs = socketpair()
        messages = []
        messageSize = 1024*128
        def peter(channel):
            with channel:
                while True:
                    messages.append((yield))
        def jack(channel):
            with channel:
                yield b'X' * messageSize
        Gio(reactor, jack(SocketContext(lhs)))
        Gio(reactor, peter(SocketContext(rhs)))
        while sum(len(message) for message in messages) < messageSize:
            reactor.step()
        self.assertTrue(len(messages) > 1) # test is only sensible when multiple parts are sent
        self.assertEqual(messageSize, len(b''.join(messages)))

    def testHowToCreateAHttpServer(self):
        port = randint(1024, 64000)
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
                yield b'HTTP/1.1 200 Ok\r\n\r\nGoodbye'
            def stop(self):
                self._reactor.removeReader(self._ear)
        #CLIENT
        responses = []
        def connection(host, port):
            connection = socket()
            connection.connect((host, port))
            return SocketContext(connection)
        def httpClient():
            with connection('localhost', port):
                yield b'GET / HTTP/1.0\r\n\r\n'
                response = yield
                responses.append(response)
        with Reactor() as reactor:
            server = HttpServer(reactor, port)
            try:
                Gio(reactor, httpClient())
                while not responses:
                    reactor.step()
            finally:
                server.stop()
            self.assertEqual([b'HTTP/1.1 200 Ok\r\n\r\nGoodbye'], responses)

    def testTimerDoesNotFire(self):
        done = []
        def handler():
            with giopen(self.tempfile, 'rw'):
                with Timer(0.1):
                    yield b'a'
                yield b'b'
            done.append(True)
        g = Gio(self.mockreactor, handler())
        self.mockreactor.step().step()
        self.assertEqual([True], done)
        self.assertEqual([], self.mockreactor._timers)
        self.assertEqual([], g._contextstack)

    def testTimerTimesOutOutsideBlock(self):
        done = []
        def handler():
            try:
                with giopen(self.tempfile, 'rw'):
                    with Timer(0.1):
                        for i in range(999999):
                            yield b'a'
            except TimeoutException:
                done.append(False)
            yield
        g = Gio(self.mockreactor, handler())
        while not done:
            self.mockreactor.step()
        self.assertEqual([False], done)
        self.assertEqual([], self.mockreactor._timers)
        self.assertEqual([], g._contextstack)

    def testTimerTimesOutWithinBlock(self):
        done = []
        def handler():
            with giopen(self.tempfile, 'rw'):
                with Timer(0.1):
                    try:
                        for i in range(999999):
                            yield b'a'
                    except TimeoutException:
                        done.append(False)
            yield
        g = Gio(self.reactor, handler())
        while done != [False]:
            self.reactor.step()
        self.assertEqual([False], done)
        self.assertEqual([], self.mockreactor._timers)
        self.assertEqual([], g._contextstack)
