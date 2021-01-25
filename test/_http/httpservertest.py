# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2018-2021 Seecr (Seek You Too B.V.) https://seecr.nl
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


from weightlesstestcase import WeightlessTestCase, MATCHALL
from seecr.test.portnumbergenerator import PortNumberGenerator
from seecr.test.io import stdout_replaced, stderr_replaced

from io import BytesIO
from errno import EAGAIN
from gzip import GzipFile
from os.path import join, abspath, dirname
from random import random
from seecr.test import CallTrace
from select import select
from socket import socket, error as SocketError, SHUT_RDWR
from sys import getdefaultencoding
from time import sleep
from zlib import compress

import sys

from weightless.core import be, Yield, compose
from weightless.io import Reactor, reactor
from weightless.io.utils import asProcess
from weightless.http import HttpServer, _httpserver, REGEXP, HTTP, HttpRequest1_1, EmptySocketPool
from weightless.http._httpserver import HttpHandler, RECVSIZE

from weightless.http._httpserver import updateResponseHeaders, parseContentEncoding, parseAcceptEncoding
from weightless.io._reactor import WRITE_INTENT, READ_INTENT

def inmydir(p):
    return join(dirname(abspath(__file__)), p)


httprequest1_1 = be(
    (HttpRequest1_1(),
        (EmptySocketPool(),),
    )
).httprequest1_1


from contextlib import contextmanager
@contextmanager
def clientsocket(host, port, blocking=True):
    s = socket()
    s.connect((host, port))
    s.setblocking(int(blocking))
    try:
        yield s
    finally:
        s.close()

class HttpServerTest(WeightlessTestCase):

    def sendRequestAndReceiveResponse(self, request, response='The Response', recvSize=4096, compressResponse=False, extraStepsAfterCompress=1, sokSends=None):
        if sokSends is not None:
            origInit = HttpHandler.__init__

            def newInit(inner_self, reactor, sok, generatorFactory, timeout, recvSize=RECVSIZE, prio=None, maxConnections=None, errorHandler=None, compressResponse=False):
                logging_sok = SendLoggingMockSock(bucket=sokSends, origSock=sok)
                origInit(inner_self,
                         reactor=reactor,
                         sok=logging_sok, # <-- logging here!
                         generatorFactory=generatorFactory,
                         timeout=timeout,
                         recvSize=recvSize,
                         prio=prio,
                         maxConnections=maxConnections,
                         errorHandler=errorHandler,
                         compressResponse=compressResponse)

            HttpHandler.__init__ = newInit

            def cleanup():
                HttpHandler.__init__ = origInit
        else:
            def cleanup():
                pass

        try:
            self.responseCalled = False
            @compose
            def responseGenFunc(**kwargs):
                yield response
                yield ''
                self.responseCalled = True
            server = HttpServer(self.reactor, self.port, responseGenFunc, recvSize=recvSize, compressResponse=compressResponse)
            server.listen()
            with clientsocket('localhost', self.port, blocking=False) as sok:
                sok.send(request)

                clientResponse = b''

                def clientRecv():
                    clientResponse = b''
                    while True:
                        try:
                            r = sok.recv(4096)
                        except SocketError as e:
                            (errno, msg) = e.args
                            if errno == EAGAIN:
                                break
                            raise
                        if not r:
                            break
                        clientResponse += r
                    return clientResponse

                while self.responseCalled is False:
                    self.reactor.step()
                    clientResponse += clientRecv()
                if compressResponse and extraStepsAfterCompress:
                    for _ in range(extraStepsAfterCompress):
                        self.reactor.step()
                        clientResponse += clientRecv()

                server.shutdown()
                clientResponse += clientRecv()
        finally:
            cleanup()
        return clientResponse

    def testConnect(self):
        self.req = False
        def onRequest(**kwargs):
            self.req = True
            yield 'nosens'

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, onRequest)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(b'GET / HTTP/1.0' + 2*HTTP.CRLF)
                    reactor.step() # connect/accept
                    reactor.step() # read GET request
                    reactor.step() # call onRequest for response data
                self.assertEqual(True, self.req)

                # cleanup
                server.shutdown()

    def testConnectBindAddress(self):
        reactor = CallTrace()
        server = HttpServer(reactor, self.port, lambda **kwargs: None, bindAddress='127.0.0.1')
        server.listen()
        self.assertEqual(('127.0.0.1', self.port), server._acceptor._sok.getsockname())

        # cleanup
        server.shutdown()

    def testSendHeader(self):
        self.kwargs = None
        def response(**kwargs):
            self.kwargs = kwargs
            yield 'nosense'

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, response)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(HTTP.CRLF.join([
                        b'GET /path/here HTTP/1.0',
                        b'Connection: close',
                        b'Ape-Nut: Mies',
                        b'', b'']))
                    while not self.kwargs:
                        reactor.step()
                    self.assertEqual({
                        'Body': b'',
                        'RequestURI': b'/path/here',
                        'HTTPVersion': b'1.0',
                        'Method': b'GET',
                        'Headers': {
                            b'Connection': b'close',
                            b'Ape-Nut': b'Mies'
                        },
                        'Client': ('127.0.0.1', MATCHALL)}, self.kwargs)

                # cleanup
                server.shutdown()

    def testGetResponse(self):
        response = self.sendRequestAndReceiveResponse(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEqual(b'The Response', response)

    def testGetCompressedResponse_deflate(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c
        compressedResponse = rawHeaders.encode() + b'Content-Encoding: deflate\r\n\r\n' + compress(rawBody.encode())
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=True)
        self.assertEqual(compressedResponse, response)

    def testGetCompressedResponse_deflate_ContentLengthStripped(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c
        compressedResponse = rawHeaders.replace('Content-Length: 12345\r\n', '').encode() + 'Content-Encoding: deflate\r\n\r\n'.encode() + compress(rawBody.encode())
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=True)
        self.assertEqual(compressedResponse, response)

    def testGetCompressedResponse_gzip_ContentLengthStripped(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c

        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip;q=0.999, deflate;q=0.998, dontknowthisone;q=1\r\n\r\n',
            response=rawResponser(),
            compressResponse=True)
        compressed_response = response.split(b'\r\n\r\n', 1)[1]
        decompressed_response = GzipFile(None, fileobj=BytesIO(compressed_response)).read()

        self.assertEqual(decompressed_response, rawBody.encode())

    def testOnlyCompressBodyWhenCompressResponseIsOn(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield c

        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=False)
        self.assertEqual(rawResponse.encode(), response)

        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=True)
        self.assertNotEqual(rawResponse.encode(), response)

    def testDontCompressRestMoreThanOnce(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\n'
        rawBody = ''
        for _ in range(int((1024 ** 2 / 5))):  # * len(str(random())) (+/- 14)
            rawBody += str(random())
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            responseCopy = rawResponse
            while len(responseCopy) > 0:
                randomSize = int(random()*384*1024)
                yield responseCopy[:randomSize]
                responseCopy = responseCopy[randomSize:]

        # Value *must* be larger than size used for a TCP Segment.
        self.assertTrue(1000000 < len(compress(rawBody.encode())))
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n',
            response=rawResponser(),
            compressResponse=True,
            extraStepsAfterCompress=1)
        compressed_response = response.split(2*HTTP.CRLF, 1)[1]
        decompressed_response = GzipFile(None, fileobj=BytesIO(compressed_response)).read()

        self.assertEqual(rawBody.encode(), decompressed_response)

        # White box, more than one sock.send(...) -> uses self._rest -> must not be compressed again.
        sokSends = []
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n',
            response=rawResponser(),
            compressResponse=True,
            sokSends=sokSends,
            extraStepsAfterCompress=1)
        compressed_response = response.split(b'\r\n\r\n', 1)[1]
        decompressed_response = GzipFile(None, fileobj=BytesIO(compressed_response)).read()
        self.assertEqual(rawBody.encode(), decompressed_response)
        self.assertTrue(6 <= len(sokSends) <= 24, len(sokSends))

    def testCompressLargerBuggerToTriggerCompressionBuffersToFlush(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nAnother: Header\r\n\r\n'
        def rawResponser():
            yield rawHeaders
            for _ in range(4500):
                yield str(random()) * 3 + str(random()) * 2 + str(random())

        sokSends = []
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=True,
            sokSends=sokSends,
            extraStepsAfterCompress=1)
        self.assertTrue(3 < len(sokSends) < 100, len(sokSends))  # Not sent in one bulk-response.
        self.assertTrue(all(sokSends))  # No empty strings

    def testGetCompressedResponse_uncompressedWhenContentEncodingPresent(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nContent-Encoding: enlightened\r\n'
        rawBody = '''This is the response.
        *NOT* compressed.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            yield rawResponse
            return
            for c in rawResponse:
                yield c
        response = self.sendRequestAndReceiveResponse(
            b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n',
            response=rawResponser(),
            compressResponse=True,
            extraStepsAfterCompress=0)
        self.assertEqual(rawResponse.encode(), response)

    def testParseContentEncoding(self):
        self.assertEqual([b'gzip'], parseContentEncoding(b'gzip'))
        self.assertEqual([b'gzip'], parseContentEncoding(b'    gzip       '))
        self.assertEqual([b'gzip', b'deflate'], parseContentEncoding(b'gzip, deflate'))
        self.assertEqual([b'deflate', b'gzip'], parseContentEncoding(b'  deflate  ,    gzip '))

    def testParseAcceptEncoding(self):
        self.assertEqual([b'gzip'], parseAcceptEncoding(b'gzip'))
        self.assertEqual([b'gzip', b'deflate'], parseAcceptEncoding(b'gzip, deflate'))
        self.assertEqual([b'gzip', b'deflate'], parseAcceptEncoding(b' gzip  , deflate '))
        self.assertEqual([b'deflate'], parseAcceptEncoding(b'gzip;q=0, deflate;q=1.0'))
        self.assertEqual([b'deflate'], parseAcceptEncoding(b'gzip;q=0.00, deflate;q=1.001'))
        self.assertEqual([b'deflate;media=range'], parseAcceptEncoding(b'gzip;q=0.00, deflate;media=range;q=1.001;I=amIgnored'))
        self.assertEqual([b'text/xhtml+xml', b'x-gzip', b'text/html;level=2'], parseAcceptEncoding(b'text/html;level=2;q=0.005, text/xhtml+xml;q=0.7, x-gzip;q=0.6'))

    def testUpdateResponseHeaders(self):
        headers = b'HTTP/1.0 200 OK\r\nSome: Header\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match)

        self.assertEqual(b'HTTP/1.0 200 OK\r\nSome: Header\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

        headers = b'HTTP/1.0 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: 1\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, removeHeaders=[b'Content-Length'])

        self.assertEqual(b'HTTP/1.0 200 OK\r\nSome: Header\r\nAnother: 1\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

        headers = b'HTTP/1.0 200 OK\r\nA: H\r\ncOnTeNt-LENGTh:\r\nB: I\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, removeHeaders=[b'Content-Length'])

        self.assertEqual(b'HTTP/1.0 200 OK\r\nA: H\r\nB: I\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

    def testUpdateResponseHeaders_addHeaders(self):
        headers = b'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, addHeaders={b'Content-Encoding': b'deflate'})
        self.assertEqual((b'HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: deflate\r\n\r\n', b'body'), (newHeaders, newBody))

    def testUpdateResponseHeaders_removeHeaders(self):
        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=[b'B'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\n\r\n', b'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=[b'Not-Found-Header'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nB: have\r\n\r\n', b'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nAnother: header\r\nB: have\r\nBe: haved\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=[b'B'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nAnother: header\r\nBe: haved\r\n\r\n', b'body'), (newSLandHeaders, newBody))

    def testUpdateResponseHeaders_requireAbsent(self):
        headers = b'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, requireAbsent=[b'Content-Encoding'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nA: H\r\n\r\n', b'body'), (newHeaders, newBody))

        headers = b'HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: Yes, Please\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=[b'Content-Encoding']))

        headers = b'HTTP/1.0 200 OK\r\ncoNTent-ENCodIng:\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=[b'Content-Encoding']))

        headers = b'HTTP/1.0 200 OK\r\nA: Content-Encoding\r\nOh: No\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=[b'Content-Encoding', b'Oh']))

        headers = b'HTTP/1.0 200 OK\r\nA:\r\nB:\r\nC:\r\nD:\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        try:
            updateResponseHeaders(headers, match, requireAbsent=['B', 'C'])
        except ValueError as e:
            self.assertEqual('Response headers contained disallowed items: C, B', str(e))

    def testCloseConnection(self):
        response = self.sendRequestAndReceiveResponse(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEqual(b'The Response', response)
        self.assertEqual({}, self.reactor._fds)

    def testSmallFragments(self):
        response = self.sendRequestAndReceiveResponse(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n', recvSize=3)
        self.assertEqual(b'The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):
        def response(**kwargs):
            yield ''            # Socket poking here - then try to really send stuff
            yield 'some text that is longer than '
            yield 'the length of fragments sent'

        class SocketWrapper(object):
            def __init__(self, sok, size=3):
                self._sok = sok
                self._size = size

            def __getattr__(self, *args, **kwargs):
                return getattr(self._sok, *args, **kwargs)

            def send(self, data, *options):
                self._sok.send(data[:self._size], *options)
                return self._size

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, response, recvSize=3, socketWrapper=SocketWrapper)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                writerFile = lambda: [context.fileOrFd for context in list(reactor._fds.values()) if context.intent == WRITE_INTENT]
                while not writerFile():
                    reactor.step()
                for i in range(22):
                    reactor.step()
                fragment = sok.recv(4096)
                self.assertEqual(b'some text that is longer than the length of fragments sent', fragment)

            # cleanup
            server.shutdown()

    def testHttpServerEncodesUnicode(self):
        unicodeString = 'some t\xe9xt'
        oneStringLength = len(unicodeString.encode(getdefaultencoding()))
        self.assertTrue(len(unicodeString) != oneStringLength)
        def response(**kwargs):
            yield unicodeString * 6000

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, response, recvSize=3)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                writers = lambda: [c for c in list(reactor._fds.values()) if c.intent == WRITE_INTENT]
                while not writers():
                    reactor.step()
                reactor.step()
                reactor.step()
                fragment = sok.recv(100000) # will read about 49152 chars
                self.assertEqual(oneStringLength * 6000, len(fragment))
                self.assertTrue(b"some t\xc3\xa9xt" in fragment, fragment)

                # cleanup
                server.shutdown()

    def testInvalidGETRequestStartsOnlyOneTimer(self):
        _httpserver.RECVSIZE = 3
        with Reactor() as reactor:
            timers = []
            orgAddTimer = reactor.addTimer
            def addTimerInterceptor(*timer):
                timers.append(timer)
                return orgAddTimer(*timer)
            reactor.addTimer = addTimerInterceptor
            server = HttpServer(reactor, self.port, None, timeout=0.01)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'GET HTTP/1.0\r\n\r\n') # no path
                while select([sok],[], [], 0) != ([sok], [], []):
                    reactor.step()
                response = sok.recv(4096)
                self.assertEqual(b'HTTP/1.0 400 Bad Request\r\n\r\n', response)
                self.assertEqual(1, len(timers))

                # cleanup
                server.shutdown()

    def testInvalidPOSTRequestStartsOnlyOneTimer(self):
        # problem in found in OAS, timers not removed properly when whole body hasnt been read yet
        _httpserver.RECVSIZE = 1
        with Reactor() as reactor:
            timers = []
            orgAddTimer = reactor.addTimer
            def addTimerInterceptor(*timer):
                timers.append(timer)
                return orgAddTimer(*timer)
            reactor.addTimer = addTimerInterceptor
            server = HttpServer(reactor, self.port, lambda **kwargs: (x for x in []), timeout=0.01)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'POST / HTTP/1.0\r\nContent-Length: 10\r\n\r\n')
                reactor.step()
                sok.send(b".")
                sleep(0.1)
                reactor.step()
                sok.send(b".")
                reactor.step()
                sleep(0.1)
                while select([sok],[], [], 0) != ([sok], [], []):
                    reactor.step()
                self.assertEqual(2, len(timers))

                # cleanup
                server.shutdown()

    def testInvalidRequestWithHalfHeader(self):
        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, None, timeout=0.1)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'POST / HTTP/1.0\r\n')
                sok.send(b'Expect: something\r\n')
                sok.send(b'Content-Length: 5\r\n')
                sok.send(b'\r\n1234')
                sok.close()
                with self.stderr_replaced() as s:
                    for i in range(4):
                        reactor.step()
                    self.assertEqual(1, len([c for c in list(reactor._fds.values()) if c.intent == READ_INTENT]))

            # cleanup
            server.shutdown()

    def testValidRequestResetsTimer(self):
        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, lambda **kwargs: ('a' for a in range(3)), timeout=0.01, recvSize=3)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                sok.send(b'GET / HTTP/1.0\r\n\r\n')
                sleep(0.02)
                for i in range(11):
                    reactor.step()
                response = sok.recv(4096)
                self.assertEqual(b'aaa', response)

            # cleanup
            server.shutdown()

    def testPostMethodReadsBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(b'POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')

                    while self.requestData is None:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual(b'POST', self.requestData['Method'])
                    self.assertEqual(b'application/x-www-form-urlencoded', headers[b'Content-Type'])
                    self.assertEqual(8, int(headers[b'Content-Length']))
                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(b'bodydata', self.requestData['Body'])

                # cleanup
                server.shutdown()

    def testPutMethodReadsBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(b'PUT / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')

                    while not self.requestData:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual(b'PUT', self.requestData['Method'])
                    self.assertEqual(b'application/x-www-form-urlencoded', headers[b'Content-Type'])
                    self.assertEqual(8, int(headers[b'Content-Length']))

                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(b'bodydata', self.requestData['Body'])

                    # cleanup
                    server.shutdown()

    def testPostMethodDeCompressesDeflatedBody_deflate(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    bodyData = b'bodydatabodydata'
                    bodyDataCompressed = compress(bodyData)
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(
                        HTTP.CRLF.join([
                            b'POST / HTTP/1.0',
                            b'Content-Type: application/x-www-form-urlencoded',
                            b'Content-Length: %d' % contentLengthCompressed,
                            b'Content-Encoding: deflate',
                            HTTP.CRLF]) + bodyDataCompressed)

                    while not self.requestData:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual(b'POST', self.requestData['Method'])
                    self.assertEqual(b'application/x-www-form-urlencoded', headers[b'Content-Type'])
                    self.assertEqual(contentLengthCompressed, int(headers[b'Content-Length']))  # TS: is this correct?, maybe decompressed length?

                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(bodyData, self.requestData['Body'])

                # cleanup
                server.shutdown()

    def testPostMethodDeCompressesDeflatedBody_gzip(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    bodyData = b'bodydatabodydata'
                    _sio = BytesIO()
                    _gzFileObj = GzipFile(filename=None, mode='wb', compresslevel=6, fileobj=_sio)
                    _gzFileObj.write(bodyData); _gzFileObj.close()
                    bodyDataCompressed = _sio.getvalue()
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(
                        HTTP.CRLF.join([
                            b'POST / HTTP/1.0',
                            b'Content-Type: application/x-www-form-urlencoded',
                            b'Content-Length: %d' % contentLengthCompressed,
                            b'Content-Encoding: gzip',
                            HTTP.CRLF]) + bodyDataCompressed)

                    while not self.requestData:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual(b'POST', self.requestData['Method'])
                    self.assertEqual(b'application/x-www-form-urlencoded', headers[b'Content-Type'])
                    self.assertEqual(contentLengthCompressed, int(headers[b'Content-Length']))

                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(bodyData, self.requestData['Body'])

                # cleanup
                server.shutdown()

    def testPostMethodDeCompressesDeflatedBody_x_deflate(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            yield 'HTTP/1.0 200 OK\r\n\r\n'

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler, timeout=0.01)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                bodyData = b'bodydatabodydata'
                bodyDataCompressed = compress(bodyData)
                contentLengthCompressed = len(bodyDataCompressed)
                sok.send(
                    HTTP.CRLF.join([
                        b'POST / HTTP/1.0',
                        b'Content-Type: application/x-www-form-urlencoded',
                        b'Content-Length: %d' % contentLengthCompressed,
                        b'Content-Encoding: x-deflate',
                        HTTP.CRLF]) + bodyDataCompressed)

                while select([sok],[], [], 0) != ([sok], [], []):
                    reactor.step()
                self.assertTrue(sok.recv(4096).startswith(b'HTTP/1.0 200 OK'))

                # TS: minimalistic assert that it works too for x-deflate
                self.assertEqual(bodyData, self.requestData['Body'])

            # cleanup
            sok.close()
            server.shutdown()

    def testPostMethodDeCompressesDeflatedBody_unrecognizedEncoding(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler, timeout=0.01)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                bodyDataCompressed = compress(b'bodydatabodydata')
                contentLengthCompressed = len(bodyDataCompressed)
                sok.send(
                    HTTP.CRLF.join([
                        b'POST / HTTP/1.0',
                        b'Content-Type: application/x-www-form-urlencoded',
                        b'Content-Length: %d' % contentLengthCompressed,
                        b'Content-Encoding: unknown',
                        HTTP.CRLF]) + bodyDataCompressed)

                while select([sok],[], [], 0) != ([sok], [], []):
                    reactor.step()
                self.assertTrue(sok.recv(4096).startswith(b'HTTP/1.0 400 Bad Request'))

                self.assertEqual(None, self.requestData)

            # cleanup
            server.shutdown()

    def testPostMethodTimesOutOnBadBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler, timeout=0.01)
            server.listen()
            with clientsocket("localhost", self.port) as sok:
                done = []
                def onDone():
                    fromServer = sok.recv(1024)
                    self.assertTrue(b'HTTP/1.0 400 Bad Request' in fromServer)
                    done.append(True)
                reactor.addTimer(0.02, onDone)

                sok.send(
                    HTTP.CRLF.join([
                        b'POST / HTTP/1.0',
                        b'Content-Type: application/x-www-form-urlencoded',
                        b'Content-Length: 8',
                        HTTP.CRLF]))

                while not done:
                    reactor.step()

            # cleanup
            server.shutdown()

    def testReadChunkedPost(self):
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01, recvSize=3)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(
                        HTTP.CRLF.join([
                            b'POST / HTTP/1.0',
                            b'Content-Type: application/x-www-form-urlencoded',
                            b'Transfer-Encoding: chunked',
                            HTTP.CRLF]) + b'5\r\nabcde\r\n5\r\nfghij\r\n0\r\n')
                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while self.requestData.get('Body', None) != b'abcdefghij':
                    reactor.step()

                # cleanup
                server.shutdown()

    def testReadChunkedAndCompressedPost(self):
        postData = b'AhjBeehCeehAhjBeehCeehAhjBeehCeehAhjBeehCeeh'
        postDataCompressed = compress(postData)
        self.assertEqual(20, len(postDataCompressed))
        self.assertEqual(15, len(postDataCompressed[:15]))
        self.assertEqual(5, len(postDataCompressed[15:]))

        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler, timeout=0.01, recvSize=3)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(
                        HTTP.CRLF.join([
                            b'POST / HTTP/1.0',
                            b'Content-Type: application/x-www-form-urlencoded',
                            b'Transfer-Encoding: chunked',
                            b'Content-Encoding: deflate',
                            HTTP.CRLF]) + b'f\r\n%s\r\n5\r\n%s\r\n0\r\n' % (postDataCompressed[:15], postDataCompressed[15:]))
                    reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Body', None) != postData:
                        reactor.step()

                # cleanup
                server.shutdown()

    def testPostMultipartForm(self):
        with open(inmydir('data/multipart-data-01'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) == None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(4, len(form))
                    self.assertEqual(['SOME ID'], form[b'id'])

                # cleanup
                server.shutdown()

    def XXX_testPostMultipartFormCompressed(self):
        """Not yet"""
        httpRequest = open(inmydir('data/multipart-data-01-compressed')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler)
            server.listen()
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send(httpRequest)

            reactor.addTimer(2, lambda: self.fail("Test Stuck"))
            while self.requestData.get('Form', None) == None:
                reactor.step()
            form = self.requestData['Form']
            self.assertEqual(4, len(form))
            self.assertEqual(['SOME ID'], form['id'])

            # cleanup
            sok.close()
            server.shutdown()

    def testWindowsPostMultipartForm(self):
        with open(inmydir('data/multipart-data-02'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) == None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(4, len(form))
                    self.assertEqual(['SOME ID'], form[b'id'])
                    self.assertEqual(1, len(form[b'somename']))
                    filename, mimetype, data = form[b'somename'][0]
                    self.assertEqual(b'Bank Gothic Medium BT.ttf', filename)
                    self.assertEqual(b'application/octet-stream', mimetype)

                # cleanup
                server.shutdown()

    def testTextFileSeenAsFile(self):
        with open(inmydir('data/multipart-data-03'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) == None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(4, len(form))
                    self.assertEqual(['SOME ID'], form[b'id'])
                    self.assertEqual(1, len(form[b'somename']))
                    filename, mimetype, data = form[b'somename'][0]
                    self.assertEqual(b'hello.bas', filename)
                    self.assertEqual(b'text/plain', mimetype)

                # cleanup
                server.shutdown()

    def testReadMultipartFormEndBoundary(self):
        with open(inmydir('data/multipart-data-04'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) == None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(1, len(form))
                    self.assertEqual(3521*'X', form[b'id'][0])

                # cleanup
                server.shutdown()

    def testReadMultipartFormEndBoundaryFilenameWithSemicolon(self):
        with open(inmydir('data/multipart-data-05'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) is None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(1, len(form))
                    self.assertEqual((b'some filename.extension', b'text/plain', 3521*'X'), form[b'name with ; semicolon'][0])

                # cleanup
                server.shutdown()


    def testOnlyHandleAMaximumNrOfRequests(self):
        codes = []
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            codes.append(kwargs['ResponseCode'])
            yield "FAIL"

        server = HttpServer(self.reactor, self.port, handler, errorHandler=error_handler, maxConnections=5)
        server.listen()

        self.reactor.getOpenConnections = lambda: 10

        with clientsocket("localhost", self.port) as sok:
            self.reactor.step()
            sok.send(b"GET / HTTP/1.0\r\n\r\n")
            self.reactor.step().step().step()
            server.shutdown()

            self.assertEqual(b'FAIL', sok.recv(1024))
            self.assertEqual([503], codes)

    def testOnlyHandleAMaximumNrOfRequestsBelowBoundary(self):
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            yield "FAIL"

        server = HttpServer(self.reactor, self.port, handler, errorHandler=error_handler, maxConnections=10)
        server.listen()

        self.reactor.getOpenConnections = lambda: 5
        with clientsocket("localhost", self.port) as sock:
            self.reactor.step()
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            self.reactor.step().step().step()
            server.shutdown()

            self.assertEqual(b'OK', sock.recv(1024))

    def testDefaultErrorHandler(self):
        def handler(**kwargs):
            yield "OK"

        server = HttpServer(self.reactor, self.port, handler, maxConnections=5)
        server.listen()

        self.reactor.getOpenConnections = lambda: 10
        with clientsocket("localhost", self.port) as sock:
            self.reactor.step()
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            self.reactor.step().step().step()

            self.assertEqual(b'HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>', sock.recv(1024))
            server.shutdown()

    def testYieldInHttpServer(self):
        bucket = []
        def handler(RequestURI, **kwargs):
            yield 'A'
            while 'continue' not in bucket:
                yield Yield
            yield 'B'

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()
                with clientsocket("localhost", self.port) as sok:
                    sok.send(b'GET /path/here HTTP/1.0\r\n\r\n')
                    for i in range(500):
                        reactor.step()
                    self.assertEqual(b'A', sok.recv(100))
                    bucket.append('continue')
                    reactor.step()
                    self.assertEqual(b'B', sok.recv(100))

                # cleanup
                server.shutdown()

    def testYieldPossibleUseCase(self):
        bucket = []
        result = []
        ready = []
        useYield = []
        workDone = []
        def handler(RequestURI, **kwargs):
            name = 'work' if b'aLotOfWork' in RequestURI else 'lazy'
            bucket.append('%s_START' % name)
            yield 'START'
            if b'/aLotOfWork' in RequestURI:
                bucket.append('%s_part_1' % name)
                if True in useYield:
                    while not workDone:
                        yield Yield
                bucket.append('%s_part_2' % name)
            bucket.append('%s_END' % name)
            ready.append('yes')
            yield 'END'

        with stdout_replaced():
            with Reactor() as reactor:
                server = HttpServer(reactor, self.port, handler)
                server.listen()

                def loopWithYield(use):
                    del ready[:]
                    del bucket[:]
                    del result[:]
                    del workDone[:]
                    useYield[:] = [use]
                    with clientsocket("localhost", self.port) as sok0:
                        sok0.send(b'GET /aLotOfWork HTTP/1.0\r\n\r\n')
                        with clientsocket("localhost", self.port) as sok1:
                            sok1.send(b'GET /path/here HTTP/1.0\r\n\r\n')
                            sleep(0.02)
                            while ready != ['yes']:
                                reactor.step()
                                if bucket:
                                    result.append(set(bucket))
                                    del bucket[:]
                            workDone.append(True)
                            while ready != ['yes', 'yes']:
                                reactor.step()
                                if bucket:
                                    result.append(set(bucket))
                                    del bucket[:]
                    return result

                self.assertEqual([
                        set(['work_START']),
                        set(['lazy_START', 'work_part_1', 'work_part_2', 'work_END']),
                        set(['lazy_END'])
                   ], loopWithYield(False))
                self.assertEqual([
                        set(['work_START']),
                        set(['lazy_START', 'work_part_1']),
                        set(['lazy_END']),
                        set(['work_part_2', 'work_END']),
                   ], loopWithYield(True))

                # cleanup
                server.shutdown()

    def testExceptionBeforeResponseGives500(self):
        port = self.newPortNumber()

        called = []
        def handler(**kwargs):
            called.append(True)
            raise KeyError(22)
            yield

        def test():
            h = HttpServer(reactor=reactor(), port=port, generatorFactory=handler)
            h.listen()

            with stderr_replaced() as err:
                statusAndHeaders, body = yield httprequest1_1(host='127.0.0.1', port=port, request='/ignored', timeout=5)
                err_val = err.getvalue()

            self.assertEqual(
                {'HTTPVersion': b'1.0',
                 'Headers': {},
                 'ReasonPhrase': b'Internal Server Error',
                 'StatusCode': b'500'},
                statusAndHeaders)
            self.assertEqual(b'', body)
            self.assertEqual([True], called)
            self.assertTrue('Error in handler - no response sent, 500 given:\nTraceback (most recent call last):\n' in err_val, err_val)
            self.assertTrue(err_val.endswith('raise KeyError(22)\nKeyError: 22\n'), err_val)

            h.shutdown()

        asProcess(test())

    def testExceptionAfterResponseStarted(self):
        port = self.newPortNumber()

        called = []
        def handler(**kwargs):
            called.append(True)
            yield "HTTP/1.0 418 I'm a teapot\r\n\r\nBody?"
            raise KeyError(23)
            yield

        def test():
            h = HttpServer(reactor=reactor(), port=port, generatorFactory=handler)
            h.listen()

            with stderr_replaced() as err:
                statusAndHeaders, body = yield httprequest1_1(host='127.0.0.1', port=port, request='/ignored', timeout=5)
                err_val = err.getvalue()

            self.assertEqual(
                {'HTTPVersion': b'1.0',
                 'Headers': {},
                 'ReasonPhrase': b"I'm a teapot",
                 'StatusCode': b'418'},
                statusAndHeaders)
            self.assertEqual(b'Body?', body)
            self.assertEqual([True], called)
            self.assertTrue('Error in handler - after response started:\nTraceback (most recent call last):\n' in err_val, err_val)
            self.assertTrue(err_val.endswith('raise KeyError(23)\nKeyError: 23\n'), err_val)

            h.shutdown()

        asProcess(test())

    def testEmptyResponseGives500(self):
        port = self.newPortNumber()

        called = []
        def handler_empty(**kwargs):
            yield ''
            called.append(True)
            yield ''
            called.append(True)

        def handler_noYields(**kwargs):
            called.append(True)
            return
            yield

        def test_empty():
            del called[:]

            h = HttpServer(reactor=reactor(), port=port, generatorFactory=handler_empty)
            h.listen()

            with stderr_replaced() as err:
                statusAndHeaders, body = yield httprequest1_1(host='127.0.0.1', port=port, request='/ignored', timeout=5)
                err_val = err.getvalue()
            self.assertEqual(
                {'HTTPVersion': b'1.0',
                 'Headers': {},
                 'ReasonPhrase': b'Internal Server Error',
                 'StatusCode': b'500'},
                statusAndHeaders)
            self.assertEqual(b'', body)
            self.assertEqual([True, True], called)
            self.assertTrue('Error in handler - no response sent, 500 given.\n' in err_val, err_val)

            h.shutdown()

        def test_noYields():
            del called[:]

            h = HttpServer(reactor=reactor(), port=port, generatorFactory=handler_noYields)
            h.listen()

            with stderr_replaced() as err:
                statusAndHeaders, body = yield httprequest1_1(host='127.0.0.1', port=port, request='/ignored', timeout=5)
                err_val = err.getvalue()
            self.assertEqual(
                {'HTTPVersion': b'1.0',
                 'Headers': {},
                 'ReasonPhrase': b'Internal Server Error',
                 'StatusCode': b'500'},
                statusAndHeaders)
            self.assertEqual(b'', body)
            self.assertEqual([True], called)
            self.assertTrue('Error in handler - no response sent, 500 given.\n' in err_val, err_val)

            h.shutdown()

        asProcess(test_empty())
        asProcess(test_noYields())

    def testHandleBrokenPipe(self):
        def abort():
            raise AssertionError('Test timed out.')
        token = self.reactor.addTimer(seconds=1, callback=abort)

        exceptions = []
        yielded_data = "OK" * 1000
        def handler(**kwargs):
            try:
                while True:
                    yield yielded_data
            except Exception as e:
                exceptions.append(e)
        server = HttpServer(self.reactor, self.port, handler, maxConnections=5)
        server.listen()
        with clientsocket("localhost", self.port) as sock:
            self.reactor.step()
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            sock.shutdown(SHUT_RDWR)
            with stderr_replaced() as f:
                while not exceptions:
                    self.reactor.step()
            self.assertTrue('Error while sending data "b\'%s' % yielded_data[:10] in f.getvalue())
            self.assertTrue("Traceback" in f.getvalue())
            self.assertTrue("[Errno 32] Broken pipe" in f.getvalue())

            self.assertEqual("[Errno 32] Broken pipe", str(exceptions[0]))
            server.shutdown()

        self.reactor.removeTimer(token=token)

    def testHandlerExitsWithException(self):
        exceptions = []
        exc_message = "this is not an I/O exception, but an application exception"
        yielded_data = "a bit of data"
        def handler(**kwargs):
            yield yielded_data
            raise Exception(exc_message)
            yield
        server = HttpServer(self.reactor, self.port, handler, maxConnections=5)
        server.listen()
        with clientsocket("localhost", self.port) as sock:
            self.reactor.step()
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            self.reactor.step()
            with stderr_replaced() as f:
                self.reactor.step().step()
                self.assertFalse(yielded_data in f.getvalue())
                self.assertTrue("Exception: %s" % exc_message in f.getvalue())

        server.shutdown()

class SendLoggingMockSock(object):
    def __init__(self, bucket, origSock):
        self._bucket = bucket
        self._orig = origSock

    def send(self, data, *args, **kwargs):
        self._bucket.append(data)
        return self._orig.send(data, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._orig, name)
