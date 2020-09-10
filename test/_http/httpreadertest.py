## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013, 2015-2016 Seecr (Seek You Too B.V.) http://seecr.nl
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

from seecr.test import CallTrace
from seecr.test.io import stdout_replaced
from weightlesstestcase import MATCHALL, WeightlessTestCase

from unittest import TestCase
from time import sleep
from socket import socket, timeout
from threading import Thread, Event

from weightless.io import Reactor
from weightless.http import HttpReader
from weightless.core import VERSION as WlVersion
from weightless.http._httpreader import HttpReaderFacade, Connector, HandlerFacade, _httpParseUrl
import sys
from io import StringIO

from .testutils import server

class HttpReaderTest(WeightlessTestCase):

    def testRequestAndHeaders(self):
        dataReceived = []
        class SomethingWithSend(object):
            def send(self, data):
                dataReceived.append(data)

        requests = []
        recvSize = 7
        with stdout_replaced():
            with self.referenceHttpServer(self.port, requests, getResponse=b"Hello World!"):
                with Reactor() as reactor:
                    connection = Connector(reactor, 'localhost', self.port)
                    try:
                        reader = HttpReader(
                            reactor, connection, SomethingWithSend(),
                            'GET', 'localhost', '/aap/noot/mies',
                            recvSize=recvSize)
                        reactor.addTimer(0.1, lambda: self.fail("Test Stuck"))
                        while b'Hello World!' != b"".join((x for x in dataReceived[1:] if x)):
                            reactor.step()
                        for each in dataReceived[1:-1]:
                            self.assertEqual(recvSize, len(each))
                        self.assertTrue(len(dataReceived[-1]) <= recvSize, dataReceived)
                        self.assertEqual(1, len(requests))
                        self.assertEqual('/aap/noot/mies', requests[0]['path'])
                        self.assertEqual({'Host': 'localhost', 'User-Agent': 'Weightless/vx.y.z'}, dict(requests[0]['headers']))
                        self.assertEqual({
                            'HTTPVersion': b'1.0',
                            'StatusCode': b'200',
                            'ReasonPhrase': b'OK',
                            'Headers': {
                                b'Date': MATCHALL,
                                b'Server': b'BaseHTTP/0.6 Python/3.7.3',
                            },
                            'Client': ('127.0.0.1', MATCHALL)}, dataReceived[0])
                    finally:
                        connection.close()

    def testHttpUrlParse(self):
        host, port, path = _httpParseUrl('http://www.cq2.org')
        self.assertEqual('www.cq2.org', host)
        self.assertEqual(80, port)
        self.assertEqual('/', path)

        host, port, path = _httpParseUrl('http://www.cq2.org:5000/page#anchor')
        self.assertEqual('www.cq2.org', host)
        self.assertEqual(5000, port)
        self.assertEqual('/page#anchor', path)

        host, port, path = _httpParseUrl('http://www.cq2.org:5000/page?x=1')
        self.assertEqual('www.cq2.org', host)
        self.assertEqual(5000, port)
        self.assertEqual('/page?x=1', path)

    def testEmptyPath(self):
        requests = []
        with stdout_replaced():
            with Reactor() as reactor:
                with self.referenceHttpServer(self.port, requests, getResponse=b"Hello World!"):
                    dataReceived = []
                    reader = HttpReaderFacade(reactor, "http://localhost:%s" % self.port, dataReceived.append)
                    reactor.step()
                    reactor.step()
                    self.assertEqual("/", requests[0]['path'])

    def testTimeoutOnInvalidRequest(self):
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v%s\r\n\r\n" % WlVersion
        requests = []
        with Reactor() as reactor:
            dataReceived = []
            with self.referenceHttpServer(self.port, requests, rawResponse=b"HTTP/1.1 *invalid reponse* 200 OK\r\n\r\n"):
                errorArgs = []
                def error(exception):
                    errorArgs.append(exception)
                reader = HttpReaderFacade(reactor, "http://localhost:%s" % self.port, dataReceived.append, error, timeout=0.01)
                while not errorArgs:
                    reactor.step()
                self.assertEqual('timeout while receiving data', str(errorArgs[0]))

    def testTimeoutOnSilentServer(self):
        requests = []
        with Reactor() as reactor:
            with self.referenceHttpServer(self.port, requests, stallTime=1):
                errorArgs = []
                class Handler:
                    def send(self, data):
                        pass
                    def throw(self, exception):
                        errorArgs.append(exception)
                reader = HttpReader(reactor, Connector(reactor, 'localhost', self.port), Handler(), "GET", "localhost", "/", timeout=0.1)
                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while not errorArgs:
                    reactor.step()
                self.assertEqual('timeout while receiving data', str(errorArgs[0]))

    def testTimeoutOnServerGoingSilentAfterHeaders(self):
        with Reactor() as reactor:
            requests = []
            with self.referenceHttpServer(self.port, requests, stallAfterHeaders=1):
                errorArgs = []
                receivedData = []
                class Handler:
                    def send(self, data):
                        receivedData.append(data)
                        pass
                    def throw(self, exception):
                        errorArgs.append(exception)
                reader = HttpReader(reactor, Connector(reactor, 'localhost', self.port), Handler(), "GET", "localhost", "/", timeout=0.1)
                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while not errorArgs:
                    reactor.step()
                self.assertEqual('timeout while receiving data', str(errorArgs[0]))
                self.assertEqual({
                    'HTTPVersion': b'1.0',
                    'StatusCode': b'200',
                    'ReasonPhrase': b'OK',
                    'Headers': {
                        b'Server': b'BaseHTTP/0.6 Python/3.7.3',
                        b'Date': MATCHALL},
                    'Client': ('127.0.0.1', MATCHALL)}, receivedData[0])

    def testClearTimer(self):
        requests = []
        with Reactor() as reactor:
            expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v%s\r\n\r\n" % WlVersion
            with self.referenceHttpServer(self.port, requests, getResponse=b"response"):
                #serverThread = server(self.port, "HTTP/1.1 200 OK\r\n\r\nresponse", expectedrequest)
                self.exception = None
                sentData = []
                def send(data):
                    sentData.append(data)
                def throw(exception):
                    self.exception = exception
                reader = HttpReaderFacade(reactor, "http://localhost:%s" % self.port, send, throw, timeout=0.01, recvSize=3)
                while not self.exception:
                    reactor.step()
                sleep(0.02) # 2 * timeout, just to be sure

                self.assertTrue(isinstance(self.exception, StopIteration), self.exception)
                self.assertEqual(b"response", b"".join(sentData[-3:]))

    def testPost(self):
        requests = []
        with Reactor() as reactor:
            request = "POST / HTTP/1.1\r\nHost: localhost\r\nSOAPAction: blah\r\nTransfer-Encoding: chunked\r\nUser-Agent: Weightless/v%s\r\n\r\n1\r\nA\r\n1\r\nB\r\n1\r\nC\r\n0\r\n\r\n" % WlVersion
            serverThread = server(self.port, "HTTP/1.1 200 OK\r\n\r\nresponse", request.encode(), loop=9)
            sentData = []
            done = []
            def send(data):
                sentData.append(data)

            def throw(exception):
                if isinstance(exception, StopIteration):
                    done.append(exception)

            def bodyHandler():
                yield "A"
                yield "B"
                yield "C"
                yield None

            reader = HttpReaderFacade(reactor,
                "http://localhost:%s" % self.port,
                send,
                errorHandler=throw,
                timeout=.5,
                headers={'SOAPAction': 'blah'},
                bodyHandler=bodyHandler)

            reactor.addTimer(3.0, lambda: self.fail("Test Stuck"))
            while not done:
                reactor.step()
            self.assertEqual([b'response'], sentData[1:])
            self.assertEqual(b'200', sentData[0]['StatusCode'])

    def testWriteChunks(self):
        reader = HttpReader(CallTrace("reactor"), CallTrace("socket"), HandlerFacade(None, None, None), '', '', '')
        self.assertEqual(b'1\r\nA\r\n', reader._createChunk('A'))
        self.assertEqual(b'A\r\n' + 10*b'B' + b'\r\n', reader._createChunk(10*'B'))

    def testDealWithChunkedResponse(self):
        with Reactor() as reactor:
            sentData = []
            done = []
            expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v%s\r\n\r\n" % WlVersion
            requests = []
            with self.referenceHttpServer(self.port, requests, rawResponse=("\r\n".join("""HTTP/1.1 302 Found
Date: Fri, 26 Oct 2007 07:23:26 GMT
Server: Apache/2.2.3 (Debian) mod_python/3.2.10 Python/2.4.4 mod_ssl/2.2.3 OpenSSL/0.9.8c
Location: /page/softwarestudio.page/show
Transfer-Encoding: chunked
Content-Type: text/html; charset=utf-8

4F
<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>

0


""".split("\n"))).encode()):
                class Handler:
                    def send(self, data):
                        sentData.append(data)
                    def throw(self, exception):
                        if isinstance(exception, StopIteration):
                            done.append(True)
                    def close(self):
                        self.throw(StopIteration())

                reader = HttpReader(reactor, Connector(reactor, 'localhost', int(self.port)), Handler(), 'GET', 'localhost', '/', recvSize=5)

                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while not done:
                    reactor.step()
                self.assertEqual(b"""<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>""", b"".join(sentData[1:]))

    def testChunkedAllTheWay(self):
        reactor = CallTrace('Reactor')
        sokket = CallTrace('Sokket')
        data = []
        class Handler:
            def send(self, chunk):
                data.append(chunk)
            def throw(self, exception):
                pass
        httpreader = HttpReader(reactor, sokket, Handler(), 'GET', 'host,nl', '/')
        httpreader._chunked = True
        # chunk == network message
        httpreader._sendFragment(b'4\r\n1234\r\n')
        self.assertEqual([b'1234'], data)
        httpreader._sendFragment(b'10\r\n0123456789abcdef\r\n')
        self.assertEqual([b'1234', b'0123456789abcdef'], data)
        del data[0]
        del data[0]
        # chunk = 2 network messages
        httpreader._sendFragment(b'10\r\nfedcba')
        #self.assertEquals(['fedcba'], data)
        httpreader._sendFragment(b'9876543210\r\n')
        self.assertEqual([b'fedcba9876543210'], data)

    def testLastRecvContainsCompleteChunk(self):
        reactor = CallTrace('Reactor')
        sokket = CallTrace('Sokket')
        data = []
        done = []
        class Handler:
            def send(self, chunk):
                data.append(chunk)
            def throw(self, exception):
                done.append(True)
            def close(self):
                self.throw(StopIteration())
        httpreader = HttpReader(reactor, sokket, Handler(), 'GET', 'host,nl', '/')
        httpreader._chunked = True
        chunkOne = b'9\r\n123456789\r\n'
        chunkTwo = b'8\r\n87654321\r\n'
        httpreader._sendFragment(chunkOne)
        self.assertEqual([b'123456789'], data)
        httpreader._sendFragment(chunkTwo)
        self.assertEqual([b'123456789', b'87654321'], data)
        while data: del data[0] # now both in one network message
        httpreader._sendFragment(chunkOne + chunkTwo +b'0\r\n\r\n')
        # Send fragment will only read one fragment.
        # Now feed it until all chunks are finished
        httpreader._sendFragment(b'')
        httpreader._sendFragment(b'')
        self.assertEqual([b'123456789', b'87654321'], data)
        self.assertEqual([True], done)
