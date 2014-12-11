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

from urllib.request import urlopen, Request, urlopen
from io import StringIO
from socket import socket, SHUT_RD, SHUT_WR, SHUT_RDWR, SO_REUSEADDR, SOL_SOCKET
from select import select
import sys
from subprocess import Popen, PIPE
from re import compile
from time import sleep

from weightlesstestcase import WeightlessTestCase
from weightless.core import compose, Observable, Transparant, be, autostart
from weightless.io import Gio, Reactor, Server
from weightless.httpng import HttpProtocol, http


def getNetStat(clientport, serverport):
    connectionRe = compile(':%d.+:%d' % (clientport, serverport))
    p1 = Popen(['netstat', '-n', '-p'], stdout=PIPE, stderr=PIPE).communicate()[0]
    return sorted(line for line in p1.split('\n') if connectionRe.search(line))

class HttpProtocolIntegrationTest(WeightlessTestCase):

    def setUp(self):
        WeightlessTestCase.setUp(self)
        self.httpprotocol = HttpProtocol()
        self.server = Server(self.reactor, self.port)
        dna = (Transparant(),
            (self.server,
                (self.httpprotocol,
                    # add your test thing here
                )
            )
        )
        self.body = be(dna)

    def tearDown(self):
        self.server.stop()
        WeightlessTestCase.tearDown(self)

    def assertNetStat(self, local, remote, state):
        statelines = getNetStat(local, remote)
        if not state:
            self.assertEquals(0, len(statelines), statelines)
        else:
            self.assertTrue(state in statelines[0], statelines[0])

    def testSimpleServerSetUpAndAFewPOSTRequests(self):
        class MyServer(object):
            def processRequest(self, Method=None, ContentLength=None, *args, **kwargs):
                if Method != 'POST':
                    return
                result = yield http.readRe('(?P<BODY>.*)', ContentLength)
                body = result['BODY']
                yield http.ok()
                yield http.headers('a', 'b')
                yield 'Hello ' + body
        self.httpprotocol.addObserver(MyServer())
        with self.loopingReactor():
            result1 = urlopen(Request('http://localhost:%s/' % self.port, data='Johan')).read()
            result2 = urlopen(Request('http://localhost:%s/' % self.port, data='Erik')).read()
        self.assertEquals('Hello Johan', result1)
        self.assertEquals('Hello Erik', result2)

    def testContentLenght(self):
        body = []
        class MyServer(object):
            def processRequest(this, Method, RequestURI, HTTPVersion, Headers, **kwargs):
                length = int(list(Headers['content-length'].keys())[0])
                @autostart
                def destination(result):
                    while True:
                        result += (yield)
                result = []
                yield http.copyBytes(length, destination(result))
                self.assertEquals('This is a body', ''.join(result))
                yield http.ok()
                yield http.headers('a', 'b')
                yield 'Hello ' + ''.join(result)
        self.httpprotocol.addObserver(MyServer())
        with self.loopingReactor():
            result1 = urlopen(Request('http://localhost:%s/' % self.port, data='This is a body')).read()
        self.assertEquals('Hello This is a body', result1)

    def testOneRequest(self):
        done = []
        class MyServer(object):
            def processRequest(this, Method, RequestURI, HTTPVersion, Headers, **kwargs):
                self.assertEquals('GET', Method)
                self.assertEquals('/seven', RequestURI)
                self.assertEquals('1.0', HTTPVersion)
                self.assertEquals({}, Headers)
                yield 'Hello there'
                done.append(True)
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /seven HTTP/1.0\r\n\r\n')
        while not done:
            self.reactor.step()
        self.assertEquals([True], done)
        self.assertEquals('Hello there', sok.recv(99))

    def testHttp11TwoRequests(self):
        done = []
        class MyServer(object):
            def processRequest(self, Method=None, RequestURI=None, HTTPVersion=None, Headers=None, fragment=None, netloc=None, query=None, path=None, scheme=None):
                yield http.ok()
                yield http.noheaders()
                yield 'Echo ' + RequestURI
                done.append(True)
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', self.port)) # ONE connection!
        sok.send('GET /six HTTP/1.1\r\n\r\n')
        while not done:
            self.reactor.step()
        response = sok.recv(999)
        self.assertEquals('HTTP/1.1 200 Ok\r\n\r\nEcho /six', response)
        sok.send('GET /seven HTTP/1.1\r\n\r\n')
        done = []
        while not done:
            self.reactor.step()
        self.assertEquals([True], done)
        response = sok.recv(999)
        self.assertEquals('HTTP/1.1 200 Ok\r\n\r\nEcho /seven', response)
        sok.close() # need to do this, because we use HTTP/1.1
        self.reactor.step()

    def testGETWithResponse(self):
        class MyServer(object):
            def processRequest(self, **kwargs):
                yield 'answer 1'
                yield 'answer 2'
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', self.port)) # ONE connection!
        sok.send('GET /one HTTP/1.1\r\n\r\n')
        self.reactor.step().step().step()
        self.assertEquals('answer 1', sok.recv(999))
        self.reactor.step()
        self.assertEquals('answer 2', sok.recv(999))
        sok.shutdown(1)
        self.reactor.step()
        self.assertEquals('', sok.recv(999))
        sok.close()

    def testPOSTandThenGET(self):
        class MyPOSTServer(object):
            def processRequest(this, Method=None, RequestURI=None, ContentLength=0, **kwargs):
                if Method == 'POST':
                    return this.handle(ContentLength)
            def handle(this, ContentLength):
                body = yield http.readRe('(?P<BODY>.*)', ContentLength)
                self.assertEquals('XXYYZZ', body['BODY'])
                yield http.ok()
                yield http.noheaders()
                yield 'this was the post handler'
        class MyGETServer(object):
            def processRequest(this, Method=None, RequestURI=None, **kwargs):
                if Method == 'GET':
                    return this.handle()
            def handle(self):
                yield http.ok()
                yield http.noheaders()
                yield 'this was the GET handler'
        self.httpprotocol.addObserver(MyPOSTServer())
        self.httpprotocol.addObserver(MyGETServer())
        body = 'XXYYZZ'
        sok = socket()
        sok.connect(('localhost', self.port)) # ONE connection!
        sok.send('POST /one HTTP/1.1\r\nContent-Length: %s\r\n\r\n' % len(body) + body)
        self.reactor.step().step().step()
        self.assertEquals('HTTP/1.1 200 Ok\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('this was the post handler', sok.recv(999))
        sok.send('GET /two HTTP/1.1\r\n\r\n')
        self.reactor.step().step()
        self.assertEquals('HTTP/1.1 200 Ok\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('this was the GET handler', sok.recv(999))
        sok.close()
        self.reactor.step()

    def testTwoRequestOnSameConnectionAndConnectionCloseHeader(self):
        done = []
        class MyServer(object):
            def processRequest(this, Method=None, RequestURI=None, ContentLength=0, *args, **kwargs):
                yield http.ok()
                if Method == 'POST':
                    @autostart
                    def devNull():
                        while True: yield
                    yield http.copyBytes(ContentLength, devNull())
                wrong = yield 'Path = ' + str(RequestURI)
                self.assertEquals(None, wrong) # Second request must not end up here
                done.append(True)
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', self.port))
        body = 'XXYYZZ'
        sok.send('POST /one HTTP/1.1\r\nContent-Length: %s\r\n\r\n' % len(body) + body)
        sok.send('GET /two HTTP/1.1\r\nConnection: close\r\n\r\n')
        while not done == [True]:
            self.reactor.step()
        self.assertEquals([True], done)
        self.assertEquals('HTTP/1.1 200 Ok\r\nPath = /one', sok.recv(99))
        while not done == [True, True]:
            self.reactor.step()
        self.assertEquals('HTTP/1.1 200 Ok\r\nPath = /two', sok.recv(99))
        sok.close()

    def testConnectionCloseForHTTP10afterPIPELINING(self):
        class MyServer(object):
            def processRequest(this, Method, RequestURI, HTTPVersion, Headers, *args, **kwargs):
                yield http.ok()
                yield http.headers('Content-Length', 3)
                yield 'Bye'
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /one HTTP/1.1\r\n\r\n') #pipeline 2 requests
        sok.send('GET /two HTTP/1.0\r\n\r\n')
        self.reactor.step().step().step()
        self.assertEquals('HTTP/1.1 200 Ok\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('Content-Length: 3\r\n\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('Bye', sok.recv(999))
        self.reactor.step()
        self.assertEquals('HTTP/1.1 200 Ok\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('Content-Length: 3\r\n\r\n', sok.recv(999))
        self.reactor.step()
        self.assertEquals('Bye', sok.recv(999))
        self.assertEquals('', sok.recv(999))  # empty string means 'closed' in socket land

    def testTimerFiresWhenConnectedClientIsSilent(self):
        sok = socket()
        sok.connect(('localhost', self.port))
        localport = sok.getsockname()[1]
        with self.loopingReactor():
            response = sok.recv(9999)
        self.assertEquals('HTTP/1.1 408 Request Timeout\r\n\r\n', response)
        sok.close()
        stat = getNetStat(self.port, localport)
        self.assertTrue('TIME_WAIT' in stat[0], stat[0])
        stat = getNetStat(localport, self.port)
        self.assertEquals(0, len(stat), stat)

    def testTimerWhenInvalidRequest(self):
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET / HTTP/1.1\r') # unterminated Request Line
        sok.send('some garbage'*1024) # some kB garbage to trigger buffer protection
        sok.send('\rxyz') # unterminated end of Headers
        self.reactor.step().step().step().step()
        self.assertEquals('HTTP/1.1 413 Request Entity Too Large\r\n\r\n', sok.recv(999))
        #self.reactor.step()
        #self.assertEquals('\r\n', sok.recv(999))
        sok.close()

    def testReuseAddress(self):
        remoteport = self.port + 1
        server = socket()
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', remoteport))
        server.listen(1)
        local = socket()
        local.connect(('127.0.0.1', remoteport))
        server.close()
        server = socket()
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            server.bind(('127.0.0.1', remoteport))
        except:
            self.fail('bind must succeed')

    def testCloseStatesRemoteFirst(self):
        remoteport = self.port+1
        server = socket()
        server.bind(('127.0.0.1', remoteport))
        server.listen(1)
        local = socket()
        local.connect(('127.0.0.1', remoteport))
        localport = local.getsockname()[1]

        remote = server.accept()[0]
        self.assertNetStat(remoteport, localport, 'ESTABLISHED')
        self.assertNetStat(localport, remoteport, 'ESTABLISHED')

        remote.close()
        self.assertNetStat(remoteport, localport, 'FIN_WAIT')
        self.assertNetStat(localport, remoteport, 'CLOSE_WAIT')

        local.close()
        self.assertNetStat(remoteport, localport, 'TIME_WAIT')
        self.assertNetStat(localport, remoteport, None)

        server.close()
        server = socket()
        try:
            server.bind(('127.0.0.1', remoteport))
            self.fail('re-bind must raise Address Already in Use Exception')
        except AssertionError:
            raise
        except Exception as e:
            pass


    def testCloseStatesLocalFirst(self):
        remoteport = self.port+1
        server = socket()
        server.bind(('localhost', remoteport))
        server.listen(1)
        local = socket()
        local.connect(('localhost', remoteport))
        localport = local.getsockname()[1]

        remote = server.accept()[0]
        self.assertNetStat(remoteport, localport, 'ESTABLISHED')
        self.assertNetStat(localport, remoteport, 'ESTABLISHED')

        local.close()
        self.assertNetStat(localport, remoteport, 'FIN_WAIT')
        self.assertNetStat(remoteport, localport, 'CLOSE_WAIT')

        remote.close()
        self.assertNetStat(localport, remoteport, 'TIME_WAIT')
        self.assertNetStat(remoteport, localport, None)

        server = socket()
        try:
            server.bind(('127.0.0.1', remoteport))
        except:
            self.fail('bind must succeed')

    def testClientShutdownWithHTTP(self):
        remoteport = self.port
        class MyServer(object):
            def processRequest(this, **kwargs):
                yield http.ok()
                yield http.noheaders()
                yield 'Bye'
        self.httpprotocol.addObserver(MyServer())
        sok = socket()
        sok.connect(('localhost', remoteport))
        localport = sok.getsockname()[1]
        sok.send('GET /one HTTP/1.1\r\n\r\n')
        self.reactor.step().step().step().step().step()
        self.assertEquals('HTTP/1.1 200 Ok\r\n\r\nBye', sok.recv(999))
        sok.shutdown(SHUT_RDWR)     # initiate shutdown/close
        self.assertNetStat(localport, remoteport, 'FIN_WAIT')
        self.assertNetStat(remoteport, localport, 'CLOSE_WAIT')
        self.reactor.step()
        self.assertEquals('', sok.recv(999))  # empty string means 'closed' in socket land
        self.assertNetStat(localport, remoteport, 'TIME_WAIT')
        self.assertNetStat(remoteport, localport, None)

    def XXXXXXXXXXXXXXXXXXXtestOpenHttpWithTransactionOnConnectionScopeExample(self):
        class Transaction(Observable):
            def __init__(self, txmanagers):
                super(Transaction, self).__init__()
                self._txmanagers = txmanagers
            def unknown(self, message, *args, **kwargs):
                txs = []
                for txmanager in sefl._txmanagers:
                    tx = txmanager.begin()
                    txs.append(tx)
                try:
                    for response in self.all.unknown(message, *args, **kwargs):
                        yield response
                except:
                    for tx in txs:
                        tx.abort()
                else:
                    for tx in txs:
                        tx.commit()
        class MyDB(object):
            def begin(self):
                self._preparedData = []
                return self
            def store(self, data):
                self._preparedData.append(data)
            def commit(self):
                self.commitedData = ''.join(self._preparedData)
                self._preparedData = []
        class MyHandler(Observable):
            def upload(self, ContentLength, *args, **kwargs):
                body = yield readBytes(ContentLength)
                self.any.store(body)
        mydb = MyDB()
        reactor = Reactor()
        server = Server(reactor, 8080)
        pipe = be((Observable(),
                    (server,
                        (Transaction([mydb]), # Transaction commits when connection closes
                            (HttpProtocol(),
                                (MyHandler(),
                                    (mydb,)
                                )
                            )
                        )
                    )
                ))
        self.fail('continue here')
