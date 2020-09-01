# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2012, 2015, 2018-2020 Seecr (Seek You Too B.V.) http://seecr.nl
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

from io import StringIO
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
from weightless.http import HttpServer, _httpserver, REGEXP, HttpRequest1_1, EmptySocketPool
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
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send(request)
            sok.setblocking(0)

            clientResponse = ''

            def clientRecv():
                clientResponse = ''
                while True:
                    try:
                        r = sok.recv(4096)
                    except SocketError as xxx_todo_changeme:
                        (errno, msg) = xxx_todo_changeme.args
                        if errno == EAGAIN:
                            break
                        raise
                    if not r:
                        break
                    clientResponse += r
                return clientResponse

            while not self.responseCalled:
                self.reactor.step()
                clientResponse += clientRecv()
            if compressResponse and extraStepsAfterCompress:
                for _ in range(extraStepsAfterCompress):
                    self.reactor.step()
                    clientResponse += clientRecv()

            server.shutdown()
            clientResponse += clientRecv()
            sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('GET / HTTP/1.0\r\n\r\n')
                reactor.step() # connect/accept
                reactor.step() # read GET request
                reactor.step() # call onRequest for response data
                self.assertEqual(True, self.req)

                # cleanup
                server.shutdown()
                sok.close()

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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                while not self.kwargs:
                    reactor.step()
                self.assertEqual({'Body': '', 'RequestURI': '/path/here', 'HTTPVersion': '1.0', 'Method': 'GET', 'Headers': {'Connection': 'close', 'Ape-Nut': 'Mies'}, 'Client': ('127.0.0.1', MATCHALL)}, self.kwargs)

                # cleanup
                sok.close()
                server.shutdown()

    def testGetResponse(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEqual('The Response', response)

    def testGetCompressedResponse_deflate(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c
        compressedResponse = rawHeaders + 'Content-Encoding: deflate\r\n\r\n' + compress(rawBody)
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
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
        compressedResponse = rawHeaders.replace('Content-Length: 12345\r\n', '') + 'Content-Encoding: deflate\r\n\r\n' + compress(rawBody)
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
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

        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip;q=0.999, deflate;q=0.998, dontknowthisone;q=1\r\n\r\n', response=rawResponser(), compressResponse=True)
        compressed_response = response.split('\r\n\r\n', 1)[1]
        decompressed_response = GzipFile(None, fileobj=StringIO(compressed_response)).read()

        self.assertEqual(decompressed_response, rawBody)

    def testOnlyCompressBodyWhenCompressResponseIsOn(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield c

        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=False)
        self.assertEqual(rawResponse, response)

        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
        self.assertNotEqual(rawResponse, response)

    def testDontCompressRestMoreThanOnce(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\n'
        rawBody = ''
        for _ in range((1024 ** 2 / 5)):  # * len(str(random())) (+/- 14)
            rawBody += str(random())
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            responseCopy = rawResponse
            while len(responseCopy) > 0:
                randomSize = int(random()*384*1024)
                yield responseCopy[:randomSize]
                responseCopy = responseCopy[randomSize:]

        # Value *must* be larger than size used for a TCP Segment.
        self.assertTrue(1000000 < len(compress(rawBody)))
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n', response=rawResponser(), compressResponse=True, extraStepsAfterCompress=1)
        compressed_response = response.split('\r\n\r\n', 1)[1]
        decompressed_response = GzipFile(None, fileobj=StringIO(compressed_response)).read()

        self.assertEqual(decompressed_response, rawBody)

        # White box, more than one sock.send(...) -> uses self._rest -> must not be compressed again.
        sokSends = []
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip\r\n\r\n', response=rawResponser(), compressResponse=True, sokSends=sokSends, extraStepsAfterCompress=1)
        compressed_response = response.split('\r\n\r\n', 1)[1]
        decompressed_response = GzipFile(None, fileobj=StringIO(compressed_response)).read()
        self.assertEqual(decompressed_response, rawBody)
        self.assertTrue(6 <= len(sokSends) <= 20, len(sokSends))

    def testCompressLargerBuggerToTriggerCompressionBuffersToFlush(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nAnother: Header\r\n\r\n'
        def rawResponser():
            yield rawHeaders
            for _ in range(4500):
                yield str(random()) * 3 + str(random()) * 2 + str(random())

        sokSends = []
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True, sokSends=sokSends, extraStepsAfterCompress=1)
        self.assertTrue(3 < len(sokSends) < 100, len(sokSends))  # Not sent in one bulk-response.
        self.assertTrue(all(sokSends))  # No empty strings

    def testGetCompressedResponse_uncompressedWhenContentEncodingPresent(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nContent-Encoding: enlightened\r\n'
        rawBody = '''This is the response.
        *NOT* compressed.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield c
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True, extraStepsAfterCompress=0)
        self.assertEqual(rawResponse, response)

    def testParseContentEncoding(self):
        self.assertEqual(['gzip'], parseContentEncoding('gzip'))
        self.assertEqual(['gzip'], parseContentEncoding('    gzip       '))
        self.assertEqual(['gzip', 'deflate'], parseContentEncoding('gzip, deflate'))
        self.assertEqual(['deflate', 'gzip'], parseContentEncoding('  deflate  ,    gzip '))

    def testParseAcceptEncoding(self):
        self.assertEqual(['gzip'], parseAcceptEncoding('gzip'))
        self.assertEqual(['gzip', 'deflate'], parseAcceptEncoding('gzip, deflate'))
        self.assertEqual(['gzip', 'deflate'], parseAcceptEncoding(' gzip  , deflate '))
        self.assertEqual(['deflate'], parseAcceptEncoding('gzip;q=0, deflate;q=1.0'))
        self.assertEqual(['deflate'], parseAcceptEncoding('gzip;q=0.00, deflate;q=1.001'))
        self.assertEqual(['deflate;media=range'], parseAcceptEncoding('gzip;q=0.00, deflate;media=range;q=1.001;I=amIgnored'))
        self.assertEqual(['text/xhtml+xml', 'x-gzip', 'text/html;level=2'], parseAcceptEncoding('text/html;level=2;q=0.005, text/xhtml+xml;q=0.7, x-gzip;q=0.6'))

    def testUpdateResponseHeaders(self):
        headers = 'HTTP/1.0 200 OK\r\nSome: Header\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match)

        self.assertEqual('HTTP/1.0 200 OK\r\nSome: Header\r\n\r\n', newHeaders)
        self.assertEqual('The Body', newBody)

        headers = 'HTTP/1.0 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: 1\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, removeHeaders=['Content-Length'])

        self.assertEqual('HTTP/1.0 200 OK\r\nSome: Header\r\nAnother: 1\r\n\r\n', newHeaders)
        self.assertEqual('The Body', newBody)

        headers = 'HTTP/1.0 200 OK\r\nA: H\r\ncOnTeNt-LENGTh:\r\nB: I\r\n\r\nThe Body'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, removeHeaders=['Content-Length'])

        self.assertEqual('HTTP/1.0 200 OK\r\nA: H\r\nB: I\r\n\r\n', newHeaders)
        self.assertEqual('The Body', newBody)

    def testUpdateResponseHeaders_addHeaders(self):
        headers = 'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, addHeaders={'Content-Encoding': 'deflate'})
        self.assertEqual(('HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: deflate\r\n\r\n', 'body'), (newHeaders, newBody))

    def testUpdateResponseHeaders_removeHeaders(self):
        statusLineAndHeaders = 'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=['B'])
        self.assertEqual(('HTTP/1.0 200 OK\r\n\r\n', 'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = 'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=['Not-Found-Header'])
        self.assertEqual(('HTTP/1.0 200 OK\r\nB: have\r\n\r\n', 'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = 'HTTP/1.0 200 OK\r\nAnother: header\r\nB: have\r\nBe: haved\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(statusLineAndHeaders)
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, match, removeHeaders=['B'])
        self.assertEqual(('HTTP/1.0 200 OK\r\nAnother: header\r\nBe: haved\r\n\r\n', 'body'), (newSLandHeaders, newBody))

    def testUpdateResponseHeaders_requireAbsent(self):
        headers = 'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        newHeaders, newBody = updateResponseHeaders(headers, match, requireAbsent=['Content-Encoding'])
        self.assertEqual(('HTTP/1.0 200 OK\r\nA: H\r\n\r\n', 'body'), (newHeaders, newBody))

        headers = 'HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: Yes, Please\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=['Content-Encoding']))

        headers = 'HTTP/1.0 200 OK\r\ncoNTent-ENCodIng:\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=['Content-Encoding']))

        headers = 'HTTP/1.0 200 OK\r\nA: Content-Encoding\r\nOh: No\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, match, requireAbsent=['Content-Encoding', 'Oh']))

        headers = 'HTTP/1.0 200 OK\r\nA:\r\nB:\r\nC:\r\nD:\r\n\r\nbody'
        match = REGEXP.RESPONSE.match(headers)
        try:
            updateResponseHeaders(headers, match, requireAbsent=['B', 'C'])
        except ValueError as e:
            self.assertEqual('Response headers contained disallowed items: C, B', str(e))

    def testCloseConnection(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEqual('The Response', response)
        self.assertEqual({}, self.reactor._fds)

    def testSmallFragments(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n', recvSize=3)
        self.assertEqual('The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):
        def response(**kwargs):
            yield ''            # Socket poking here - then try to really send stuff
            yield 'some text that is longer than '
            yield 'the lenght of fragments sent'

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, response, recvSize=3)
            server.listen()
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
            writerFile = lambda: [context.fileOrFd for context in list(reactor._fds.values()) if context.intent == WRITE_INTENT]
            while not writerFile():
                reactor.step()
            serverSok = writerFile()[0]
            originalSend = serverSok.send
            def sendOnlyManagesToActuallySendThreeBytesPerSendCall(data, *options):
                originalSend(data[:3], *options)
                return 3
            serverSok.send = sendOnlyManagesToActuallySendThreeBytesPerSendCall
            for i in range(22):
                reactor.step()
            fragment = sok.recv(4096)
            self.assertEqual('some text that is longer than the lenght of fragments sent', fragment)

            # cleanup
            sok.close()
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
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
            writers = lambda: [c for c in list(reactor._fds.values()) if c.intent == WRITE_INTENT]
            while not writers():
                reactor.step()
            reactor.step()
            reactor.step()
            fragment = sok.recv(100000) # will read about 49152 chars
            self.assertEqual(oneStringLength * 6000, len(fragment))
            self.assertTrue("some t\xc3\xa9xt" in fragment, fragment)

            # cleanup
            sok.close()
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
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('GET HTTP/1.0\r\n\r\n') # no path
            while select([sok],[], [], 0) != ([sok], [], []):
                reactor.step()
            response = sok.recv(4096)
            self.assertEqual('HTTP/1.0 400 Bad Request\r\n\r\n', response)
            self.assertEqual(1, len(timers))

            # cleanup
            sok.close()
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
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('POST / HTTP/1.0\r\nContent-Length: 10\r\n\r\n')
            reactor.step()
            sok.send(".")
            sleep(0.1)
            reactor.step()
            sok.send(".")
            reactor.step()
            sleep(0.1)
            while select([sok],[], [], 0) != ([sok], [], []):
                reactor.step()
            self.assertEqual(2, len(timers))

            # cleanup
            sok.close()
            server.shutdown()

    def testInvalidRequestWithHalfHeader(self):
        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, None, timeout=0.1)
            server.listen()
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('POST / HTTP/1.0\r\n')
            sok.send('Expect: something\r\n')
            sok.send('Content-Length: 5\r\n')
            sok.send('\r\n1234')
            sok.close()
            with self.stderr_replaced() as s:
                for i in range(4):
                    reactor.step()
                self.assertEqual(1, len([c for c in list(reactor._fds.values()) if c.intent == READ_INTENT]))

            # cleanup
            sok.close()
            server.shutdown()

    def testValidRequestResetsTimer(self):
        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, lambda **kwargs: ('a' for a in range(3)), timeout=0.01, recvSize=3)
            server.listen()
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('GET / HTTP/1.0\r\n\r\n')
            sleep(0.02)
            for i in range(11):
                reactor.step()
            response = sok.recv(4096)
            self.assertEqual('aaa', response)

            # cleanup
            sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')

                while not self.requestData:
                    reactor.step()
                self.assertEqual(dict, type(self.requestData))
                self.assertTrue('Headers' in self.requestData)
                headers = self.requestData['Headers']
                self.assertEqual('POST', self.requestData['Method'])
                self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                self.assertEqual(8, int(headers['Content-Length']))

                self.assertTrue('Body' in self.requestData)
                self.assertEqual('bodydata', self.requestData['Body'])

                # cleanup
                sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('PUT / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')

                while not self.requestData:
                    reactor.step()
                self.assertEqual(dict, type(self.requestData))
                self.assertTrue('Headers' in self.requestData)
                headers = self.requestData['Headers']
                self.assertEqual('PUT', self.requestData['Method'])
                self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                self.assertEqual(8, int(headers['Content-Length']))

                self.assertTrue('Body' in self.requestData)
                self.assertEqual('bodydata', self.requestData['Body'])

                # cleanup
                sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                bodyData = 'bodydatabodydata'
                bodyDataCompressed = compress(bodyData)
                contentLengthCompressed = len(bodyDataCompressed)
                sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: deflate\r\n\r\n' % contentLengthCompressed) + bodyDataCompressed)

                while not self.requestData:
                    reactor.step()
                self.assertEqual(dict, type(self.requestData))
                self.assertTrue('Headers' in self.requestData)
                headers = self.requestData['Headers']
                self.assertEqual('POST', self.requestData['Method'])
                self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                self.assertEqual(contentLengthCompressed, int(headers['Content-Length']))  # TS: is this correct?, maybe decompressed length?

                self.assertTrue('Body' in self.requestData)
                self.assertEqual('bodydatabodydata', self.requestData['Body'])

                # cleanup
                sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                bodyData = 'bodydatabodydata'
                _sio = StringIO()
                _gzFileObj = GzipFile(filename=None, mode='wb', compresslevel=6, fileobj=_sio)
                _gzFileObj.write(bodyData); _gzFileObj.close()
                bodyDataCompressed = _sio.getvalue()
                contentLengthCompressed = len(bodyDataCompressed)
                sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: gzip\r\n\r\n' % contentLengthCompressed) + bodyDataCompressed)

                while not self.requestData:
                    reactor.step()
                self.assertEqual(dict, type(self.requestData))
                self.assertTrue('Headers' in self.requestData)
                headers = self.requestData['Headers']
                self.assertEqual('POST', self.requestData['Method'])
                self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                self.assertEqual(contentLengthCompressed, int(headers['Content-Length']))

                self.assertTrue('Body' in self.requestData)
                self.assertEqual('bodydatabodydata', self.requestData['Body'])

                # cleanup
                sok.close()
                server.shutdown()

    def testPostMethodDeCompressesDeflatedBody_x_deflate(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            yield 'HTTP/1.0 200 OK\r\n\r\n'

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler, timeout=0.01)
            server.listen()
            sok = socket()
            sok.connect(('localhost', self.port))
            bodyData = 'bodydatabodydata'
            bodyDataCompressed = compress(bodyData)
            contentLengthCompressed = len(bodyDataCompressed)
            sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: x-deflate\r\n\r\n' % contentLengthCompressed) + bodyDataCompressed)

            while select([sok],[], [], 0) != ([sok], [], []):
                reactor.step()
            self.assertTrue(sok.recv(4096).startswith('HTTP/1.0 200 OK'))

            # TS: minimalistic assert that it works too for x-deflate
            self.assertEqual('bodydatabodydata', self.requestData['Body'])

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
            sok = socket()
            sok.connect(('localhost', self.port))
            bodyData = 'bodydatabodydata'
            bodyDataCompressed = compress(bodyData)
            contentLengthCompressed = len(bodyDataCompressed)
            sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: unknown\r\n\r\n' % contentLengthCompressed) + bodyDataCompressed)

            while select([sok],[], [], 0) != ([sok], [], []):
                reactor.step()
            self.assertTrue(sok.recv(4096).startswith('HTTP/1.0 400 Bad Request'))

            self.assertEqual(None, self.requestData)

            # cleanup
            sok.close()
            server.shutdown()

    def testPostMethodTimesOutOnBadBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        done = []
        def onDone():
            fromServer = sok.recv(1024)
            self.assertTrue('HTTP/1.0 400 Bad Request' in fromServer)
            done.append(True)

        with Reactor() as reactor:
            server = HttpServer(reactor, self.port, handler, timeout=0.01)
            server.listen()
            reactor.addTimer(0.02, onDone)
            sok = socket()
            sok.connect(('localhost', self.port))
            sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\n')

            while not done:
                reactor.step()

            # cleanup
            sok.close()
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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nabcde\r\n5\r\nfghij\r\n0\r\n')

                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while self.requestData.get('Body', None) != 'abcdefghij':
                    reactor.step()

                # cleanup
                sok.close()
                server.shutdown()

    def testReadChunkedAndCompressedPost(self):
        postData = 'AhjBeehCeehAhjBeehCeehAhjBeehCeehAhjBeehCeeh'
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
                sok = socket()
                sok.connect(('localhost', self.port))
                postString = 'POST / HTTP/1.1\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\nContent-Encoding: deflate\r\n\r\nf\r\n%s\r\n5\r\n%s\r\n0\r\n' % (postDataCompressed[:15], postDataCompressed[15:])
                sok.send(postString)

                reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                while self.requestData.get('Body', None) != postData:
                    reactor.step()

                # cleanup
                sok.close()
                server.shutdown()

    def testPostMultipartForm(self):
        httpRequest = open(inmydir('data/multipart-data-01')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
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
        httpRequest = open(inmydir('data/multipart-data-02')).read()
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
            self.assertEqual(1, len(form['somename']))
            filename, mimetype, data = form['somename'][0]
            self.assertEqual('Bank Gothic Medium BT.ttf', filename)
            self.assertEqual('application/octet-stream', mimetype)

            # cleanup
            sok.close()
            server.shutdown()

    def testTextFileSeenAsFile(self):
        httpRequest = open(inmydir('data/multipart-data-03')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
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
                self.assertEqual(1, len(form['somename']))
                filename, mimetype, data = form['somename'][0]
                self.assertEqual('hello.bas', filename)
                self.assertEqual('text/plain', mimetype)

                # cleanup
                sok.close()
                server.shutdown()

    def testReadMultipartFormEndBoundary(self):
        httpRequest = open(inmydir('data/multipart-data-04')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
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
                self.assertEqual(1, len(form))
                self.assertEqual(3521*'X', form['id'][0])

                # cleanup
                sok.close()
                server.shutdown()

    def testReadMultipartFormEndBoundaryFilenameWithSemicolon(self):
        httpRequest = open(inmydir('data/multipart-data-05')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with stdout_replaced():
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
                self.assertEqual(1, len(form))
                self.assertEqual(('some filename.extension', 'text/plain', 3521*'X'), form['name with ; semicolon'][0])

                # cleanup
                sok.close()
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

        sock = socket()
        sock.connect(('localhost', self.port))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step().step().step()
        server.shutdown()

        self.assertEqual('FAIL', sock.recv(1024))
        self.assertEqual([503], codes)

        # cleanup
        sock.close()

    def testOnlyHandleAMaximumNrOfRequestsBelowBoundary(self):
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            yield "FAIL"

        server = HttpServer(self.reactor, self.port, handler, errorHandler=error_handler, maxConnections=10)
        server.listen()

        self.reactor.getOpenConnections = lambda: 5

        sock = socket()
        sock.connect(('localhost', self.port))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step().step().step()
        server.shutdown()

        self.assertEqual('OK', sock.recv(1024))

        # cleanup
        sock.close()

    def testDefaultErrorHandler(self):
        def handler(**kwargs):
            yield "OK"

        server = HttpServer(self.reactor, self.port, handler, maxConnections=5)
        server.listen()

        self.reactor.getOpenConnections = lambda: 10

        sock = socket()
        sock.connect(('localhost', self.port))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step().step().step()

        self.assertEqual('HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>', sock.recv(1024))
        server.shutdown()
        sock.close()

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
                sok = socket()
                sok.connect(('localhost', self.port))
                sok.send('GET /path/here HTTP/1.0\r\n\r\n')
                for i in range(500):
                    reactor.step()
                self.assertEqual('A', sok.recv(100))
                bucket.append('continue')
                reactor.step()
                self.assertEqual('B', sok.recv(100))

                # cleanup
                sok.close()
                server.shutdown()

    def testYieldPossibleUseCase(self):
        bucket = []
        result = []
        ready = []
        useYield = []
        workDone = []
        def handler(RequestURI, **kwargs):
            name = 'work' if 'aLotOfWork' in RequestURI else 'lazy'
            bucket.append('%s_START' % name)
            yield 'START'
            if '/aLotOfWork' in RequestURI:
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
                    sok0 = socket()
                    sok0.connect(('localhost', self.port))
                    sok0.send('GET /aLotOfWork HTTP/1.0\r\n\r\n')
                    sok1 = socket()
                    sok1.connect(('localhost', self.port))
                    sok1.send('GET /path/here HTTP/1.0\r\n\r\n')
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

                    sok0.close()
                    sok1.close()
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
        port = next(PortNumberGenerator)

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
                {'HTTPVersion': '1.0',
                 'Headers': {},
                 'ReasonPhrase': 'Internal Server Error',
                 'StatusCode': '500'},
                statusAndHeaders)
            self.assertEqual('', body)
            self.assertEqual([True], called)
            self.assertTrue('Error in handler - no response sent, 500 given:\nTraceback (most recent call last):\n' in err_val, err_val)
            self.assertTrue(err_val.endswith('raise KeyError(22)\nKeyError: 22\n'), err_val)

            h.shutdown()

        asProcess(test())

    def testExceptionAfterResponseStarted(self):
        port = next(PortNumberGenerator)

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
                {'HTTPVersion': '1.0',
                 'Headers': {},
                 'ReasonPhrase': "I'm a teapot",
                 'StatusCode': '418'},
                statusAndHeaders)
            self.assertEqual('Body?', body)
            self.assertEqual([True], called)
            self.assertTrue('Error in handler - after response started:\nTraceback (most recent call last):\n' in err_val, err_val)
            self.assertTrue(err_val.endswith('raise KeyError(23)\nKeyError: 23\n'), err_val)

            h.shutdown()

        asProcess(test())

    def testEmptyResponseGives500(self):
        port = next(PortNumberGenerator)

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
                {'HTTPVersion': '1.0',
                 'Headers': {},
                 'ReasonPhrase': 'Internal Server Error',
                 'StatusCode': '500'},
                statusAndHeaders)
            self.assertEqual('', body)
            self.assertEqual([True, True], called)
            self.assertEqual('Error in handler - no response sent, 500 given.\n', err_val)

            h.shutdown()

        def test_noYields():
            del called[:]

            h = HttpServer(reactor=reactor(), port=port, generatorFactory=handler_noYields)
            h.listen()

            with stderr_replaced() as err:
                statusAndHeaders, body = yield httprequest1_1(host='127.0.0.1', port=port, request='/ignored', timeout=5)
                err_val = err.getvalue()
            self.assertEqual(
                {'HTTPVersion': '1.0',
                 'Headers': {},
                 'ReasonPhrase': 'Internal Server Error',
                 'StatusCode': '500'},
                statusAndHeaders)
            self.assertEqual('', body)
            self.assertEqual([True], called)
            self.assertEqual('Error in handler - no response sent, 500 given.\n', err_val)

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
        sock = socket()
        sock.connect(('localhost', self.port))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        sock.shutdown(SHUT_RDWR)
        with stderr_replaced() as f:
            while not exceptions:
                self.reactor.step()

            self.assertTrue("Error while sending data \"%s" % yielded_data[:10] in f.getvalue())
            self.assertTrue("Traceback" in f.getvalue())
            self.assertTrue("[Errno 32] Broken pipe" in f.getvalue())

        self.assertEqual("[Errno 32] Broken pipe", str(exceptions[0]))
        server.shutdown()
        sock.close()

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
        sock = socket()
        sock.connect(('localhost', self.port))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step()
        with stderr_replaced() as f:
            self.reactor.step().step()
            self.assertFalse(yielded_data in f.getvalue())
            self.assertTrue("Exception: %s" % exc_message in f.getvalue())

        server.shutdown()
        sock.close()


class SendLoggingMockSock(object):
    def __init__(self, bucket, origSock):
        self._bucket = bucket
        self._orig = origSock

    def send(self, data, *args, **kwargs):
        self._bucket.append(data)
        return self._orig.send(data, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._orig, name)