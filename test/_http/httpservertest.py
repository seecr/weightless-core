# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from weightlesstestcase import WeightlessTestCase, MATCHALL
from socket import socket
from select import select
from weightless.io import Reactor
from time import sleep
from seecr.test import CallTrace
from os.path import join, abspath, dirname
from io import StringIO, BytesIO
from sys import getdefaultencoding
from zlib import compress
from gzip import GzipFile

from weightless.http import HttpServer, _httpserver, REGEXP
from weightless.http._httpserver import GzipCompress
from weightless.core import Yield, compose

from weightless.http._httpserver import updateResponseHeaders, parseContentEncoding, parseAcceptEncoding, CRLF, CRLF_LEN

def inmydir(p):
    return join(dirname(abspath(__file__)), p)

class HttpServerTest(WeightlessTestCase):

    def sendRequestAndReceiveResponse(self, reactor, request, response='The Response', recvSize=4096, compressResponse=False, extraStepAfterCompress=True):
        self.responseCalled = False
        @compose
        def responseGenFunc(**kwargs):
            yield response
            yield ''
            self.responseCalled = True
        with HttpServer(reactor, self.port, responseGenFunc, recvSize=recvSize, compressResponse=compressResponse) as server:
            server.listen()
            with socket() as sok:
                sok.connect(('localhost', self.port))
                sok.send(request)

                mockStdout = None
                # with self.stdout_replaced() as mockStdout:
                while not self.responseCalled:
                    reactor.step()
                if compressResponse and extraStepAfterCompress: #not everythingSent???:
                    reactor.step()
                r = sok.recv(4096)
                return r

    def testConnect(self):
        self.req = False
        def onRequest(**kwargs):
            self.req = True
            yield 'nosens'
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, onRequest) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET / HTTP/1.0\r\n\r\n')
                    reactor.step() # connect/accept
                    reactor.step() # read GET request
                    reactor.step() # call onRequest for response data
                    self.assertEqual(True, self.req)

    def testConnectBindAddress(self):
        with Reactor() as reactor:
            with HttpServer(reactor, self.port, lambda **kwargs: None, bindAddress='127.0.0.1') as server:
                server.listen()
                self.assertEqual(('127.0.0.1', self.port), server._acceptor._sok.getsockname())

    def testSendHeader(self):
        self.kwargs = None
        def response(**kwargs):
            self.kwargs = kwargs
            yield 'nosense'
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, response) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                    while not self.kwargs:
                        reactor.step()
                    self.assertEqual({'Body': b'', 'RequestURI': '/path/here', 'HTTPVersion': '1.0', 'Method': 'GET', 'Headers': {'Connection': 'close', 'Ape-Nut': 'Mies'}, 'Client': ('127.0.0.1', sok.getsockname()[1])}, self.kwargs)

    def testGetResponse(self):
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
            self.assertEqual(b'The Response', response)

    def testGetCompressedResponse_deflate(self):
        rawHeaders = b'HTTP/1.1 200 OK\r\n'
        rawBody = b'''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + b'\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c
        compressedResponse = rawHeaders + b'Content-Encoding: deflate\r\n\r\n' + compress(rawBody)
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
            self.assertEqual(compressedResponse, response)

    def testGetCompressedResponse_deflate_ContentLengthStripped(self):
        rawHeaders = 'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = '''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + '\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c.encode()
        compressedResponse = rawHeaders.replace('Content-Length: 12345\r\n', '').encode() + b'Content-Encoding: deflate\r\n\r\n' + compress(rawBody.encode())
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
            self.assertEqual(compressedResponse, response)

    def testGetCompressedResponse_gzip_ContentLengthStripped(self):
        rawHeaders = b'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = b'''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + b'\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield Yield
                yield c
        
        _compress = GzipCompress()
        compressedBody = _compress.compress(rawBody)
        compressedBody += _compress.flush()

        compressedResponse = rawHeaders.replace(b'Content-Length: 12345\r\n', b'') + b'Content-Encoding: gzip\r\n\r\n' + compressedBody
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: gzip;q=0.999, deflate;q=0.998, dontknowthisone;q=1\r\n\r\n', response=rawResponser(), compressResponse=True)
            self.assertEqual(compressedResponse, response)

    def testOnlyCompressBodyWhenCompressResponseIsOn(self):
        rawHeaders = b'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: Header\r\n'
        rawBody = b'''This is the response.
        Nicely uncompressed, and readable.'''
        rawResponse = rawHeaders + b'\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield c

        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=False)
            self.assertEqual(rawResponse, response)

            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True)
            self.assertNotEqual(rawResponse, response)

    def testGetCompressedResponse_uncompressedWhenContentEncodingPresent(self):
        rawHeaders = b'HTTP/1.1 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nContent-Encoding: enlightened\r\n'
        rawBody = b'''This is the response.
        *NOT* compressed.'''
        rawResponse = rawHeaders + b'\r\n' + rawBody
        def rawResponser():
            for c in rawResponse:
                yield c
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nAccept-Encoding: deflate\r\n\r\n', response=rawResponser(), compressResponse=True, extraStepAfterCompress=False)
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
        headers = b'HTTP/1.0 200 OK\r\nSome: Header\r\n\r\nThe Body'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        newHeaders, newBody = updateResponseHeaders(headers, endHeaderMarker)

        self.assertEqual(b'HTTP/1.0 200 OK\r\nSome: Header\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

        headers = b'HTTP/1.0 200 OK\r\nSome: Header\r\nContent-Length: 12345\r\nAnother: 1\r\n\r\nThe Body'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        newHeaders, newBody = updateResponseHeaders(headers, endHeaderMarker, removeHeaders=['Content-Length'])

        self.assertEqual(b'HTTP/1.0 200 OK\r\nSome: Header\r\nAnother: 1\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

        headers = b'HTTP/1.0 200 OK\r\nA: H\r\ncOnTeNt-LENGTh:\r\nB: I\r\n\r\nThe Body'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        newHeaders, newBody = updateResponseHeaders(headers, endHeaderMarker, removeHeaders=['Content-Length'])

        self.assertEqual(b'HTTP/1.0 200 OK\r\nA: H\r\nB: I\r\n\r\n', newHeaders)
        self.assertEqual(b'The Body', newBody)

    def testUpdateResponseHeaders_addHeaders(self):
        headers = b'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        newHeaders, newBody = updateResponseHeaders(headers, endHeaderMarker, addHeaders={'Content-Encoding': 'deflate'})
        self.assertEqual((b'HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: deflate\r\n\r\n', b'body'), (newHeaders, newBody))

    def testUpdateResponseHeaders_removeHeaders(self):
        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        endHeaderMarker = statusLineAndHeaders.find(2*CRLF) + 2*CRLF_LEN
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, endHeaderMarker, removeHeaders=['B'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\n\r\n', b'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nB: have\r\n\r\nbody'
        endHeaderMarker = statusLineAndHeaders.find(2*CRLF) + 2*CRLF_LEN
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, endHeaderMarker, removeHeaders=['Not-Found-Header'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nB: have\r\n\r\n', b'body'), (newSLandHeaders, newBody))

        statusLineAndHeaders = b'HTTP/1.0 200 OK\r\nAnother: header\r\nB: have\r\nBe: haved\r\n\r\nbody'
        endHeaderMarker = statusLineAndHeaders.find(2*CRLF) + 2*CRLF_LEN
        newSLandHeaders, newBody = updateResponseHeaders(statusLineAndHeaders, endHeaderMarker, removeHeaders=['B'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nAnother: header\r\nBe: haved\r\n\r\n', b'body'), (newSLandHeaders, newBody))

    def testUpdateResponseHeaders_requireAbsent(self):
        headers = b'HTTP/1.0 200 OK\r\nA: H\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        newHeaders, newBody = updateResponseHeaders(headers, endHeaderMarker, requireAbsent=['Content-Encoding'])
        self.assertEqual((b'HTTP/1.0 200 OK\r\nA: H\r\n\r\n', b'body'), (newHeaders, newBody))

        headers = b'HTTP/1.0 200 OK\r\nA: H\r\nContent-Encoding: Yes, Please\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, endHeaderMarker, requireAbsent=['Content-Encoding']))

        headers = b'HTTP/1.0 200 OK\r\ncoNTent-ENCodIng:\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, endHeaderMarker, requireAbsent=['Content-Encoding']))

        headers = b'HTTP/1.0 200 OK\r\nA: Content-Encoding\r\nOh: No\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        self.assertRaises(ValueError, lambda: updateResponseHeaders(headers, endHeaderMarker, requireAbsent=['Content-Encoding', 'Oh']))

        headers = b'HTTP/1.0 200 OK\r\nA:\r\nB:\r\nC:\r\nD:\r\n\r\nbody'
        endHeaderMarker = headers.find(2*CRLF) + 2*CRLF_LEN
        try:
            updateResponseHeaders(headers, endHeaderMarker, requireAbsent=['B', 'C'])
        except ValueError as e:
            message, headers = str(e).split(":")
            self.assertEqual("Response headers contained disallowed items", message)
            self.assertEqual({'B', 'C'}, set(map(str.strip, headers.split(','))))

    def testCloseConnection(self):
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
            self.assertEqual(b'The Response', response)
            self.assertEqual({}, reactor._readers)
            self.assertEqual({}, reactor._writers)

    def testSmallFragments(self):
        with Reactor() as reactor:
            response = self.sendRequestAndReceiveResponse(reactor, b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n', recvSize=3)
            self.assertEqual(b'The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):

        class WrappedSocket(object):
            def __init__(self, target):
                self.__dict__['_target'] = target

            def send(self, data, *options):
                self._target.send(data[:3], *options)
                return 3

            def __getattr__(self, attr):
                return getattr(self._target, attr)

            def __setattr__(self, attr, value):
                setattr(self._target, attr, value)

        def response(**kwargs):
            yield 'some text that is longer than '
            yield 'the length of fragments sent'
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, response, recvSize=3, socketWrap=WrappedSocket) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                    while not reactor._writers:
                        reactor.step()

                    for i in range(20):
                        reactor.step()
                    fragment = sok.recv(4096)
                    self.assertEqual(b'some text that is longer than the length of fragments sent', fragment)

    def testHttpServerEncodesUnicode(self):
        unicodeString = 'some t\xe9xt'
        oneStringLength = len(unicodeString.encode(getdefaultencoding()))
        self.assertTrue(len(unicodeString) != oneStringLength)
        def response(**kwargs):
            yield unicodeString * 6000
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, response, recvSize=3) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
                    while not reactor._writers:
                        reactor.step()
                    reactor.step()
                    fragment = sok.recv(100000) # will read about 49152 chars
                    reactor.step()
                    fragment += sok.recv(100000)
                self.assertEqual(oneStringLength * 6000, len(fragment))
                self.assertTrue("some t\xc3\xa9xt".encode('latin-1') in fragment, fragment)

    def testInvalidGETRequestStartsOnlyOneTimer(self):
        _httpserver.RECVSIZE = 3
        with Reactor(log=StringIO()) as reactor:
            timers = []
            orgAddTimer = reactor.addTimer
            def addTimerInterceptor(*timer):
                timers.append(timer)
                return orgAddTimer(*timer)
            reactor.addTimer = addTimerInterceptor
            with HttpServer(reactor, self.port, None, timeout=0.01) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET HTTP/1.0\r\n\r\n') # no path
                    while select([sok],[], [], 0) != ([sok], [], []):
                        reactor.step()
                    response = sok.recv(4096)
                    self.assertEqual(b'HTTP/1.0 400 Bad Request\r\n\r\n', response)
                    self.assertEqual(1, len(timers))

    def testInvalidPOSTRequestStartsOnlyOneTimer(self):
        # problem in found in OAS, timers not removed properly when whole body hasnt been read yet
        _httpserver.RECVSIZE = 1
        with Reactor(log=StringIO()) as reactor:
            timers = []
            orgAddTimer = reactor.addTimer
            def addTimerInterceptor(*timer):
                timers.append(timer)
                return orgAddTimer(*timer)
            reactor.addTimer = addTimerInterceptor
            with HttpServer(reactor, self.port, lambda **kwargs: (x for x in []), timeout=0.01) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
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

    def testInvalidRequestWithHalfHeader(self):
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, None, timeout=0.1) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'POST / HTTP/1.0\r\n')
                    sok.send(b'Expect: something\r\n')
                    sok.send(b'Content-Length: 5\r\n')
                    sok.send(b'\r\n1234')
                    sok.close()
                    with self.stderr_replaced() as s:
                        for i in range(4):
                            reactor.step()
                        self.assertEqual(1, len(reactor._readers))

    def testValidRequestResetsTimer(self):
        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, lambda **kwargs: ('a' for a in range(3)), timeout=0.01, recvSize=3) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET / HTTP/1.0\r\n\r\n')
                    sleep(0.02)
                    for i in range(11):
                        reactor.step()
                    response = sok.recv(4096)
                    self.assertEqual(b'aaa', response)

    def testPostMethodReadsBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')
                    while not self.requestData:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual('POST', self.requestData['Method'])
                    self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                    self.assertEqual(8, int(headers['Content-Length']))

                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(b'bodydata', self.requestData['Body'])

    def testPostMethodDeCompressesDeflatedBody_deflate(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    bodyData = b'bodydatabodydata'
                    bodyDataCompressed = compress(bodyData)
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: deflate\r\n\r\n' % contentLengthCompressed).encode() + bodyDataCompressed)

                    while not self.requestData:
                        reactor.step()
                    self.assertEqual(dict, type(self.requestData))
                    self.assertTrue('Headers' in self.requestData)
                    headers = self.requestData['Headers']
                    self.assertEqual('POST', self.requestData['Method'])
                    self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
                    self.assertEqual(contentLengthCompressed, int(headers['Content-Length']))  # TS: is this correct?, maybe decompressed length?

                    self.assertTrue('Body' in self.requestData)
                    self.assertEqual(b'bodydatabodydata', self.requestData['Body'])

    def testPostMethodDeCompressesDeflatedBody_gzip(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                bodyData = b'bodydatabodydata'
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    _bio = BytesIO()
                    with GzipFile(filename=None, mode='wb', compresslevel=6, fileobj=_bio) as _gzFileObj:
                        _gzFileObj.write(bodyData)
                    compressedBodyData = _bio.getvalue()
                    bodyDataCompressed = compress(bodyData)
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: gzip\r\n\r\n' % contentLengthCompressed).encode() + bodyDataCompressed)

                    while not self.requestData:
                        reactor.step()

        self.assertEqual(dict, type(self.requestData))
        self.assertTrue('Headers' in self.requestData)
        headers = self.requestData['Headers']
        self.assertEqual('POST', self.requestData['Method'])
        self.assertEqual('application/x-www-form-urlencoded', headers['Content-Type'])
        self.assertEqual(contentLengthCompressed, int(headers['Content-Length']))

        self.assertTrue('Body' in self.requestData)
        self.assertEqual(bodyData, self.requestData['Body'])

    def testPostMethodDeCompressesDeflatedBody_x_deflate(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                bodyData = b'bodydatabodydata'
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    bodyDataCompressed = compress(bodyData)
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: x-deflate\r\n\r\n' % contentLengthCompressed).encode() + bodyDataCompressed)

                    while select([sok],[], [], 0) != ([sok], [], []):
                        reactor.step()
                    self.assertFalse(sok.recv(4096).decode().startswith('HTTP/1.0 400 Bad Request'))

        # TS: minimalistic assert that it works too for x-deflate
        self.assertEqual(bodyData, self.requestData['Body'])

    def testPostMethodDeCompressesDeflatedBody_unrecognizedEncoding(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs
            return
            yield

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                bodyData = b'bodydatabodydata'
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    bodyDataCompressed = compress(bodyData)
                    contentLengthCompressed = len(bodyDataCompressed)
                    sok.send(('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\nContent-Encoding: unknown\r\n\r\n' % contentLengthCompressed).encode() + bodyDataCompressed)

                    while select([sok],[], [], 0) != ([sok], [], []):
                        reactor.step()
                    self.assertTrue(sok.recv(4096).decode().startswith('HTTP/1.0 400 Bad Request'))

            self.assertEqual(None, self.requestData)

    def testPostMethodTimesOutOnBadBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        done = []
        def onDone():
            fromServer = sok.recv(1024).decode()
            self.assertTrue('HTTP/1.0 400 Bad Request' in fromServer)
            done.append(True)

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01) as server:
                server.listen()
                reactor.addTimer(0.02, onDone)
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\n')

                    while not done:
                        reactor.step()

    def testReadChunkedPost(self):
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01, recvSize=3) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nabcde\r\n5\r\nfghij\r\n0\r\n')

                    reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Body', None) != b'abcdefghij':
                        reactor.step()

    def testReadChunkedAndCompressedPost(self):
        postData = b'AhjBeehCeehAhjBeehCeehAhjBeehCeehAhjBeehCeeh'
        postDataCompressed = compress(postData)
        self.assertEqual(20, len(postDataCompressed))
        self.assertEqual(15, len(postDataCompressed[:15]))
        self.assertEqual(5, len(postDataCompressed[15:]))

        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler, timeout=0.01, recvSize=3) as server:
                server.listen()
                with socket() as sok: 
                    sok.connect(('localhost', self.port))
                    postString = b'POST / HTTP/1.1\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\nContent-Encoding: deflate\r\n\r\n' + b'f\r\n' + postDataCompressed[:15] + b'\r\n5\r\n'+ postDataCompressed[15:] + b'\r\n0\r\n'
                    sok.send(postString)

                    reactor.addTimer(.2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Body', None) != postData:
                        reactor.step()

    def testPostMultipartForm(self):
        with open(inmydir("data/multipart-data-01"), "rb") as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(httpRequest)

                reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                while self.requestData.get('Form', None) == None:
                    reactor.step()
                form = self.requestData['Form']
                self.assertEqual(4, len(form))
                self.assertEqual(['SOME ID'], form['id'])

    def XXX_testPostMultipartFormCompressed(self):
        """Not yet"""
        with open(inmydir('data/multipart-data-01-compressed'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(httpRequest)

                    reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                    while self.requestData.get('Form', None) == None:
                        reactor.step()
                    form = self.requestData['Form']
                    self.assertEqual(4, len(form))
                    self.assertEqual(['SOME ID'], form['id'])

    def testWindowsPostMultipartForm(self):
        with open(inmydir('data/multipart-data-02'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
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

    def testTextFileSeenAsFile(self):
        with open(inmydir('data/multipart-data-03'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
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

    def testReadMultipartFormEndBoundary(self):
        with open(inmydir('data/multipart-data-04'), 'rb') as fp:
            httpRequest = fp.read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(httpRequest)

                reactor.addTimer(2, lambda: self.fail("Test Stuck"))
                while self.requestData.get('Form', None) == None:
                    reactor.step()
        form = self.requestData['Form']
        self.assertEqual(1, len(form))
        self.assertEqual(3521*'X', form['id'][0])

    def testOnlyHandleAMaximumNrOfRequests(self):
        codes = []
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            codes.append(kwargs['ResponseCode'])
            yield "FAIL"
        with Reactor() as reactor:
            reactor.getOpenConnections = lambda: 10
            with HttpServer(reactor, self.port, handler, errorHandler=error_handler, maxConnections=5) as server:
                server.listen()

                with socket() as sock:
                    sock.connect(('localhost', self.port))
                    reactor.step()
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    reactor.step().step().step()

                    self.assertEqual(b'FAIL', sock.recv(1024))
                    self.assertEqual([503], codes)

    def testOnlyHandleAMaximumNrOfRequestsBelowBoundary(self):
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            yield "FAIL"
    
        with Reactor() as reactor:
            reactor.getOpenConnections = lambda: 5
            with HttpServer(reactor, self.port, handler, errorHandler=error_handler, maxConnections=10) as server:
                server.listen()

                with socket() as sock:
                    sock.connect(('localhost', self.port))
                    reactor.step()
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    reactor.step().step().step()

                    self.assertEqual(b'OK', sock.recv(1024))

    def testDefaultErrorHandler(self):
        def handler(**kwargs):
            yield "OK"

        with Reactor() as reactor:
            reactor.getOpenConnections = lambda: 10
            with HttpServer(reactor, self.port, handler, maxConnections=5) as server:
                server.listen()

                with socket() as sock:
                    sock.connect(('localhost', self.port))
                    reactor.step()
                    sock.send(b"GET / HTTP/1.0\r\n\r\n")
                    reactor.step().step().step()

                    self.assertEqual(b'HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>', sock.recv(1024))

    def testYieldInHttpServer(self):
        bucket = []
        def handler(RequestURI, **kwargs):
            yield 'A'
            while 'continue' not in bucket:
                yield Yield
            yield 'B'

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()
                with socket() as sok:
                    sok.connect(('localhost', self.port))
                    sok.send(b'GET /path/here HTTP/1.0\r\n\r\n')
                    for i in range(500):
                        reactor.step()
                    self.assertEqual(b'A', sok.recv(100))
                    bucket.append('continue')
                    reactor.step()
                    self.assertEqual(b'B', sok.recv(100))

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

        with Reactor(log=StringIO()) as reactor:
            with HttpServer(reactor, self.port, handler) as server:
                server.listen()

                def loopWithYield(use):
                    del ready[:]
                    del bucket[:]
                    del result[:]
                    del workDone[:]
                    useYield[:] = [use]
                    with socket() as sok0:
                        sok0.connect(('localhost', self.port))
                        sok0.send(b'GET /aLotOfWork HTTP/1.0\r\n\r\n')
                    with socket() as sok1:
                        sok1.connect(('localhost', self.port))
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

