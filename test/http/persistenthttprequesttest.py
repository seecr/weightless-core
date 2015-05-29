# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2015 Seecr (Seek You Too B.V.) http://seecr.nl
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

from weightlesstestcase import WeightlessTestCase, StreamingData

from seecr.test import CallTrace
from seecr.test.io import stderr_replaced, stdout_replaced
from seecr.test.portnumbergenerator import PortNumberGenerator

from httpreadertest import server as testserver

import sys
from collections import namedtuple
from errno import ECONNREFUSED
from functools import wraps
from re import sub
from socket import socket, error as SocketError, gaierror as SocketGaiError, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, SOL_TCP, TCP_NODELAY, SHUT_RDWR, SHUT_RD
from struct import pack
from sys import exc_info, version_info
from time import sleep, time
from traceback import format_exception, print_exc

from weightless.core import compose, identify, is_generator, Yield, local, be, Observable
from weightless.io import Reactor, Suspend, TimeoutException, reactor
from weightless.io.utils import asProcess, sleep as zleep
from weightless.http import HttpServer, SocketPool, parseHeaders
from weightless.http._persistenthttprequest import HttpRequest1_1

from weightless.http._persistenthttprequest import _requestLine, _shutAndCloseOnce, _CHUNK_RE, _deChunk, _TRAILERS_RE, SocketWrapper
from weightless.http import _persistenthttprequest as persistentHttpRequestModule

httprequest1_1 = be(
    (HttpRequest1_1(),
        (SocketPool(reactor='Not-Under-Test-Here'),),
    )
).httprequest1_1

PYVERSION = '%s.%s' % version_info[:2]


# Context:
# - Request always HTTP/1.1
# - Requests always have Content-Length: <n> specified (less logic / no need for request chunking - or detection if the server is capable of recieving it)
# - Variables are:
#   {
#       http: <1.1/1.0>  # Server response HTTP version
#       EOR: chunking / content-length / close / noBodyAllowed # End-Of-Response, signaled by: "Transfer-Encoding: chunked", "Content-Length: <n>", "Connection: close" or type of request (method) or response (status code) does not allow a body.
#       explicit-close: <True/(False|Missing)>  # Wether, irrespective of EOR-signaling, the server wants to close the connection at EOR.
#       comms: <ok/retry/double-fail/pooled-unusable>  # Comms goes awry somehow.
#   }


class PersistentHttpRequestTest(WeightlessTestCase):
    ##
    ## HTTP/1.1 (and backwards compatible with HTTP/1.0) Protocol
    def testHttpRequestBasics(self):
        expectedrequest = "GET /path?arg=1&arg=2 HTTP/1.1\r\nHost: localhost\r\n\r\n"

        def r1(sok, log, remoteAddress, connectionNr):
            # Request
            data = yield read(untilExpected=expectedrequest)
            self.assertEquals(expectedrequest, data)

            # Response
            _headers = 'HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\n'
            yield write(data=_headers)
            yield write(data='hel')
            yield write(data='lo!')
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            top = be((Observable(),
                (HttpRequest1_1(),
                    (SocketPool(reactor=reactor()),),
                )
            ))
            try:
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/path?arg=1&arg=2')
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'Headers': {'Content-Length': '6'},
                        'ReasonPhrase': 'OK',
                        'StatusCode': '200',
                    },
                    statusAndHeaders
                )
                self.assertEquals('hello!', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals({1: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp10BodyDisallowed(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'HEAD /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.0 200 OK\r\n\r\n<BODY>')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'HEAD /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.0 200 OK\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1, r2])
            mss.listen()
            try:
                try:
                    _, _ = yield httprequest1_1(method='HEAD', host='localhost', port=mss.port, request='/first')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Body not empty.', str(e))
                statusAndHeaders, body = yield httprequest1_1(method='HEAD', host='localhost', port=mss.port, request='/second')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('', body)
                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals({1: (None, []), 2: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp11BodyDisallowed(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'POST /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.0 204 No Content\r\n\r\n<BODY>')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            # Should be a "conditional get request"; but we don't care (yet).
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.0 304 Not Modified\r\n\r\n<BODY>')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r3(sok, log, remoteAddress, connectionNr):
            # Should be a "conditional get request"; but we don't care (yet).
            toRead = 'GET /third HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.0 304 Not Modified\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1, r2, r3])
            mss.listen()
            try:
                try:
                    _, _ = yield httprequest1_1(method='POST', host='localhost', port=mss.port, request='/first')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Body not empty.', str(e))
                try:
                    _, _ = yield httprequest1_1(method='GET', host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Body not empty.', str(e))
                statusAndHeaders, body = yield httprequest1_1(method='GET', host='localhost', port=mss.port, request='/third')
                self.assertEquals('304', statusAndHeaders['StatusCode'])
                self.assertEquals({1: (None, []), 2: (None, []), 3: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp11OneHundredResponseDisallowed(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.1 101 Switching Protocols\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            try:
                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('1XX status code recieved.', str(e))
                self.assertEquals({1: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp10CloseDelimitedBody(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.0 200 Okee-Dan\r\n\r\n")
            yield write("Hi!")
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            try:
                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('Hi!', body)
                self.assertEquals({1: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp10ContentLengthDelimitedBody(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.0 200 Yes\r\nContent-Length: 4\r\n\r\n")
            yield write("1234<TOO-LONG>")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.0 200 Yes\r\nContent-Length: 4\r\n\r\n")
            yield write("A")  # Too short.
            sok.shutdown(SHUT_RDWR); sok.close()

        def r3(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /third HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.0 200 Yes\r\nContent-Length: 4\r\n\r\n")
            yield write("ABCD")
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1, r2, r3])
            mss.listen()
            try:
                try:
                    statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/first')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Excess bytes (> Content-Length) read.', str(e))

                try:
                    statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/third')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('ABCD', body)
                self.assertEquals({1: (None, []), 2: (None, []), 3: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    def testHttp11ContentLengthDelimited(self):
        # Bad Things Happen, not persisted - simple OK variants too.
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.1 200 ok\r\nContent-Length: 4\r\n')
            yield zleep(0.001)
            yield write('\r\n12')
            yield zleep(0.001)
            yield write('34<TOO-LONG>')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.1 200 ok\r\nContent-Length: 4\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r3(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /third HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write('HTTP/1.1 200 ok\r\nContent-Length: 4\r\n\r\n123')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r4(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /fourth HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            for c in 'HTTP/1.1 200 ok\r\nContent-Length: 4\r\nConnection: close\r\n\r\n1234':
                yield write(c)
            sok.shutdown(SHUT_RDWR); sok.close()

        def r5(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /fifth HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            for c in 'HTTP/1.1 200 ok\r\nContent-Length: 4\r\n\r\n1234':
                yield write(c)
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1, r2, r3, r4, r5])
            mss.listen()
            top = be((Observable(),
                (HttpRequest1_1(),
                    (SocketPool(reactor=reactor()),),
                )
            ))
            try:
                try:
                    _, _ = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Excess bytes (> Content-Length) read.', str(e))

                try:
                    _, _ = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                try:
                    _, _ = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/third')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/fourth')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('1234', body)

                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/fifth')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('1234', body)

                yield zleep(0.001)
                self.assertEquals(5, mss.nrOfRequests)
                self.assertEquals([None] * 5, [c.value for c in mss.state.connections.values()])
            finally:
                mss.close()

        asProcess(test())

    def testHttp11ContentLengthDelimitedReusedOnce(self):
        # Happy-Path, least complex, still persisted - /w 100 Continue
        # {http: 1.1, EOR: content-length, explicit-close: False, comms: ok}
        def r1(sok, log, remoteAddress, connectionNr):
            log.append(remoteAddress)
            # Request
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Weird servers say 100 Continue after request - even when not requested to do so.
            yield write(data='HTTP/1.1 100 Continue\r\nwEiRd: Header\r\n\r\n')

            # Response statusline & headers
            yield write(data='HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n')
            yield zleep(seconds=0.05)

            # Response body
            yield write(data='ACK')
            log.append('Response1Done')

            # Delay before answering the 2nd request.
            yield zleep(seconds=0.05)

            # Request
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Response statusline & headers
            yield write(data='HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
            log.append('Response2Done')
            sok.shutdown(SHUT_RDWR); sok.close()  # Server may do this, even if not advertised with "Connection: close"

            # Socket dead, but no-one currently uses it (in pool), so not noticed.
            yield zleep(0.05)
            raise StopIteration('Finished')

        @dieAfter(seconds=5.0)
        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            try:
                top = be((Observable(),
                    (HttpRequest1_1(),
                        (SocketPool(reactor=reactor()),),
                    ),
                ))
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first', timeout=1.0)
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'StatusCode': '200',
                        'ReasonPhrase': 'OK',
                        'Headers': {'Content-Length': '3'},
                    }, statusAndHeaders)
                self.assertEquals('ACK', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)
                conn1Log = mss.state.connections.get(1).log
                remoteAddress1Host = conn1Log[0][0]
                self.assertEquals('127.0.0.1', remoteAddress1Host)
                self.assertEquals(['Response1Done'], conn1Log[1:])

                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'StatusCode': '200',
                        'ReasonPhrase': 'OK',
                        'Headers': {'Content-Length': '0'},
                    }, statusAndHeaders)
                self.assertEquals('', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)
                conn1Log = mss.state.connections.get(1).log
                self.assertEquals(['Response1Done', 'Response2Done'], conn1Log[1:])

                yield zleep(0.06)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals('Finished', mss.state.connections.get(1).value)
            finally:
                mss.close()

        asProcess(test())

    def testHttp11ChunkingDelimitedBody(self):
        # Bad Things Happen, not persisted - simple OK variants too.
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r3(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /third HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\nBAD_DATA")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r4(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /fourth HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nRUBBISCH")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r5(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /fifth HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n\r\n0\r\nNOT_A_TRAILER\r\n\r")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r6(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /sixth HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n0\r\n\r\n")
            sok.shutdown(SHUT_RDWR); sok.close()

        def r7(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /seventh HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n3\r\nABC\r\n0\r\nTr: Ailer\r\n\r\n")
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1, r2, r3, r4, r5, r6, r7])
            mss.listen()
            try:
                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/first')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/third')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Data after last chunk', str(e))

                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/fourth')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                try:
                    _, _ = yield httprequest1_1(host='localhost', port=mss.port, request='/fifth')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/sixth')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('', body)

                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/seventh')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('ABC', body)

                yield zleep(0.001)
                self.assertEquals(7, mss.nrOfRequests)
                self.assertEquals([None] * 7, [c.value for c in mss.state.connections.values()])
            finally:
                mss.close()

        asProcess(test())

    def testHttp11ChunkedDelimitedReused(self):
        # Happy-Path, no trailers, still persisted
        # {http: 1.1, EOR: chunking, explicit-close: False, comms: ok}
        def r1(sok, log, remoteAddress, connectionNr):
            # Request 1
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Response statusline & headers
            yield write(data='HTTP/1.1 200 OK\r\nTransfer')
            yield zleep(seconds=0.01)
            yield write(data='-Encoding: chunked\r\n')
            yield zleep(seconds=0.01)

            # Last CRLF of header, begin Response body
            yield write(data='\r\na\r\n0123456789\r\n1;chunk-ext-name=chunk-ext-value;cen=cev\r\nA\r\n0\r\n\r\n')
            log.append('Response1Done')

            # Request 2
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Response statusline & headers
            yield write(data='HTTP/1.1 200 oK\r\nTRANSFER-encoding: blue, GREEN, Banana, GZip, ChunKeD\r\n\r\n1\r\nx\r\n0\r\n\r\n')  # As long as chunked is last, whatever.
            log.append('Response2Done')

            # Request 3
            toRead = 'GET /third HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Response statusline & headers
            yield write(data='HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n')
            log.append('Response3Done')
            sok.shutdown(SHUT_RDWR); sok.close()  # Server may do this, even if not advertised with "Connection: close"

            # Socket dead, but no-one currently uses it (in pool), so not noticed.
            yield zleep(0.01)
            raise StopIteration('Finished')

        @dieAfter(seconds=5.0)
        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            try:
                top = be((Observable(),
                    (HttpRequest1_1(),
                        (SocketPool(reactor=reactor()),),
                    ),
                ))
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first', timeout=1.0)
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'StatusCode': '200',
                        'ReasonPhrase': 'OK',
                        'Headers': {'Transfer-Encoding': 'chunked'},
                    }, statusAndHeaders)
                self.assertEquals('0123456789A', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)
                conn1Log = mss.state.connections.get(1).log
                self.assertEquals(['Response1Done'], conn1Log)

                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'StatusCode': '200',
                        'ReasonPhrase': 'oK',
                        'Headers': {'Transfer-Encoding': 'blue, GREEN, Banana, GZip, ChunKeD'},
                    }, statusAndHeaders)
                self.assertEquals('x', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)
                self.assertEquals(['Response1Done', 'Response2Done'], conn1Log)

                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/third')
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'StatusCode': '200',
                        'ReasonPhrase': 'OK',
                        'Headers': {'Transfer-Encoding': 'chunked'},
                    }, statusAndHeaders)
                self.assertEquals('', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)
                conn1Log = mss.state.connections.get(1).log
                self.assertEquals(['Response1Done', 'Response2Done', 'Response3Done'], conn1Log)

                yield zleep(0.015)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals('Finished', mss.state.connections.get(1).value)
            finally:
                mss.close()

        asProcess(test())

    def testHttp11CloseDelimitedBody(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 Okee-Dan\r\n\r\n")
            yield write("Hi!")
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            mss.listen()
            try:
                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('Hi!', body)
                self.assertEquals({1: (None, [])}, mss.state.connections)
            finally:
                mss.close()

        asProcess(test())

    ##
    ## Context (preconditions, aborting, ...)
    def testConnectMethodExplicitlyForbidden(self):
        def test():
            mss = MockSocketServer()
            mss.listen()
            try:
                try:
                    _, _ = yield httprequest1_1(method='CONNECT', host='localhost', port=mss.port, request='/')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('CONNECT method unsupported.', str(e))
            finally:
                mss.close()

        asProcess(test())

    def testWithTimeout(self):
        def r1(sok, log, remoteAddress, connectionNr):
            s = 'GET /path HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=s)
            self.assertEquals(s, data)

            # Force close, focus on timout testing without pooling here.
            yield write('HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\n')

            for i in xrange(5):
                yield zleep(0.01)
                yield write(str(i))

            sok.shutdown(SHUT_RDWR); sok.close()
            raise StopIteration('finished')

        def r2(sok, log, remoteAddress, connectionNr):
            s = 'GET /path HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=s)
            self.assertEquals(s, data)

            yield write('HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\n')
            log.append('headers')

            try:
                for i in xrange(5):
                    yield zleep(0.01)
                    yield write(str(i))
                    log.append(i)
            except SocketError, e:
                self.assertEquals(32, e.args[0])  # Broken pipe

            sok.close()  # shutdown would fail with errno: 107 / "Transport endpoint is not connected".
            raise StopIteration('finished')

        def test():
            port = []
            staticArgs = dict(method='GET', host='localhost', request='/path')
            mss = MockSocketServer()
            mss.setReplies(replies=[r1, r2])
            mss.listen()
            try:
                # Not timing out
                statusAndHeaders, body = yield httprequest1_1(
                    timeout=0.5, port=mss.port,
                    **staticArgs
                )
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('01234', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(('finished', []), mss.state.connections.get(1))

                # Timing out
                try:
                    _, _ = yield httprequest1_1(
                        timeout=0.015, port=mss.port,
                        **staticArgs
                    )
                    self.fail()
                except TimeoutException:
                    pass
                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals((IN_PROGRESS, ['headers', 0]), mss.state.connections.get(2))
                yield zleep(0.025)
                self.assertEquals(('finished', ['headers', 0, 1]), mss.state.connections.get(2))
            finally:
                mss.close()

        asProcess(test())

    def testPoolProtocol(self):
        def r1(sok, log, remoteAddress, connectionNr):
            s = "GET /first HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
            data = yield read(untilExpected=s)
            self.assertEquals(s, data)

            yield write('HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n')
            yield write('DATA')
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            # second request
            s = "GET /second HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
            data = yield read(untilExpected=s)
            self.assertEquals(s, data)

            yield write('HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n')
            yield write('DATA')
            log.append(2)
            yield zleep(0.01)

            # third request
            s = "GET /third HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
            data = yield read(untilExpected=s)
            self.assertEquals(s, data)

            yield write('HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n')
            yield write('DATA')
            log.append(3)
            yield zleep(0.01)  # Don't close before back-in-the-pool & tests done.
            sok.shutdown(SHUT_RDWR); sok.close()

        @dieAfter(seconds=5)
        def test():
            _realPool = SocketPool(reactor=reactor())
            getLog = []
            def getPooledSocket(*a, **kw):
                retval = yield _realPool.getPooledSocket(*a, **kw)
                getLog.append(retval)
                raise StopIteration(retval)
            putLog = []
            def putSocketInPool(*a, **kw):
                retval = yield _realPool.putSocketInPool(*a, **kw)
                putLog.append(retval)
                raise StopIteration(retval)
            loggingPool = CallTrace('LoggingSocketPool', methods={
                'getPooledSocket': getPooledSocket,
                'putSocketInPool': putSocketInPool,
            })
            top = be((Observable(),
                (HttpRequest1_1(),
                    (loggingPool,),
                )
            ))
            mss = MockSocketServer()
            mss.setReplies(replies=[r1, r2])
            mss.listen()
            try:
                # 1st request; no socket reuse by server request.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='127.0.0.1', port=mss.port, request='/first')
                # Request went ok.
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('DATA', body)

                # mss interaction ok.
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals((None, []), mss.state.connections.get(1))

                # Actual test:
                self.assertEquals(['getPooledSocket'], loggingPool.calledMethodNames())
                self.assertEquals(((), {'host': '127.0.0.1', 'port': mss.port}), (loggingPool.calledMethods[0].args, loggingPool.calledMethods[0].kwargs))
                self.assertEquals([None], getLog)
                loggingPool.calledMethods.reset()
                del getLog[:]

                # 2st request; socket reuse.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='127.0.0.1', port=mss.port, request='/second')
                # Request went ok.
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('DATA', body)

                # mss interaction ok.
                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals((IN_PROGRESS, [2]), mss.state.connections.get(2))

                # Actual test:
                self.assertEquals(['getPooledSocket', 'putSocketInPool'], loggingPool.calledMethodNames())
                _get, _put = loggingPool.calledMethods
                self.assertEquals(((), {'host': '127.0.0.1', 'port': mss.port}), (_get.args, _get.kwargs))
                self.assertEquals([None], getLog)
                self.assertEquals(((), set(['host', 'port', 'sock'])), (_put.args, set(_put.kwargs.keys())))
                self.assertEquals('127.0.0.1', _put.kwargs['host'])
                self.assertEquals(mss.port, _put.kwargs['port'])
                storedFileno = _put.kwargs['sock'].fileno()
                self.assertTrue(bool(storedFileno), _put.kwargs['sock'])
                self.assertEquals([None], putLog)
                del getLog[:]
                del putLog[:]
                loggingPool.calledMethods.reset()

                # 3st request; socket reused.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='127.0.0.1', port=mss.port, request='/third')
                # Request went ok.
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('DATA', body)

                # mss interaction ok.
                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals((IN_PROGRESS, [2, 3]), mss.state.connections.get(2))

                # Actual test:
                self.assertEquals(['getPooledSocket', 'putSocketInPool'], loggingPool.calledMethodNames())
                self.assertEquals(storedFileno, getLog[0].fileno())
                self.assertEquals(storedFileno, loggingPool.calledMethods[1].kwargs['sock'].fileno())
                pooledSocket = yield _realPool.getPooledSocket(host='127.0.0.1', port=mss.port)
                self.assertEquals(storedFileno, pooledSocket.fileno())

                # Wait for connection #2 close.
                yield zleep(0.02)

                self.assertEquals(None, mss.state.connections.get(2).value)
            finally:
                mss.close()

        asProcess(test())

    def testHttpRequestWorksWhenDrivenByHttpServer(self):
        # Old name: testPassRequestThruToBackOfficeServer
        expectedrequest = "GET /path?arg=1&arg=2 HTTP/1.1\r\nHost: localhost\r\n\r\n"

        def r1(sok, log, remoteAddress, connectionNr):
            # Request
            data = yield read(untilExpected=expectedrequest)
            self.assertEquals(expectedrequest, data)

            # Response
            _headers = 'HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\n'
            yield write(data=_headers)
            yield write(data='hel')
            yield write(data='lo!')
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies([r1])
            @compose
            def _passthruhandler(*args, **kwargs):
                request = kwargs['RequestURI']
                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=mss.port, request=request)
                yield 'HTTP/1.0 200 Ok\r\n\r\n'
                yield statusAndHeaders['StatusCode'] + '\n' + body
            wlPort = PortNumberGenerator.next()
            wlHttp = HttpServer(reactor=reactor(), port=wlPort, generatorFactory=_passthruhandler)

            wlHttp.listen()
            mss.listen()
            try:
                statusAndHeaders, body = yield httprequest1_1(host='localhost', port=wlPort, request='/path?arg=1&arg=2', timeout=1.0)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals({1: (None, [])}, mss.state.connections)
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('200\nhello!', body)
            finally:
                wlHttp.shutdown()
                mss.close()

        asProcess(test())

    def testTracebackPreservedAcrossSuspend(self):
        # Mocking getPooledSocket, since this is the first action after being suspended (that could potentially go wrong).
        class SocketPoolMock(object):
            def getPooledSocket(self, host, port):
                raise RuntimeError('Boom!')

        def r1(sok, log, remoteAddress, connectionNr):
            yield zleep(0.01)
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1])
            top = be((Observable(),
                (HttpRequest1_1(),
                    (SocketPoolMock(),),
                )
            ))
            mss.listen()
            try:
                _, _ = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/')
                self.fail()
            except RuntimeError, e:
                c, v, t = exc_info()
                self.assertEquals('Boom!', str(e))
            finally:
                mss.close()

            resultingTraceback = ''.join(format_exception(c, v, t))
            expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 967, in test
    _, _ = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/')
  File "%(_httprequest1_1.py)s", line 64, in httprequest1_1
    result = s.getResult()
  File "%(_httprequest1_1.py)s", line 81, in _do
    sok = yield observable.any.getPooledSocket(host=host, port=port)
  File "%(__file__)s", line 951, in getPooledSocket
    raise RuntimeError('Boom!')
RuntimeError: Boom!\n""" % fileDict)
            self.assertEquals(expectedTraceback, ignoreLineNumbers(resultingTraceback))

        asProcess(test())

    def testHttpsPostOnIncorrectPort(self):
        @dieAfter(seconds=5.0)
        def test():
            try:
                _, _ = yield httprequest1_1(
                    method='POST', host='localhost', port=PortNumberGenerator.next(), request='/path', body="body",
                    headers={'Content-Type': 'text/plain'}, secure=True,
                )
                self.fail()
            except IOError, e:
                self.assertEquals(ECONNREFUSED, e.args[0])  # errno: 111.

        asProcess(test())

    def testConnectFails(self):
        def test():
            # Non-numeric port
            try:
                _, _ = yield httprequest1_1(host='localhost', port='PORT', request='/')
                self.fail()
            except TypeError, e:
                self.assertEquals('an integer is required', str(e))

            #"Invalid" port (no-one listens)
            try:
                _, _ = yield httprequest1_1(host='localhost', port=87, request='/')  # 87 -> IANA: mfcobol (Micro Focus Cobol) "any private terminal link".
                self.fail()
            except IOError, e:
                self.assertEquals(ECONNREFUSED, e.args[0])  # errno: 111.

            # Invalid host
            try:
                _, _ = yield httprequest1_1(host='UEYR^$*FD(#>NDJ.khfd9.(*njnd', port=PortNumberGenerator.next(), request='/')
                self.fail()
            except SocketGaiError, e:
                self.assertEquals(-2, e.args[0])
                self.assertTrue('Name or service not known' in str(e), str(e))
            # No-one listens
            try:
                _, _ = yield httprequest1_1(host='127.0.0.1', port=PortNumberGenerator.next(), request='/')
                self.fail()
            except IOError, e:
                self.assertEquals(ECONNREFUSED, e.args[0])  # errno: 111.

        asProcess(test())

    def testUnconditionalRetryOnPooledSocketSendtoFailing(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            # One OK -> into pool
            yield zleep(0.001)

            # And server closed socket for some reason (timeout, # parallel connections, ...).
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nDone")
            # In pool (cleanup here).
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1, r2])
            socketPool = SocketPool(reactor=reactor())
            top = be((Observable(),
                (HttpRequest1_1(),
                    (socketPool,),
                )
            ))
            mss.listen()
            try:
                # new socket & into pool.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)

                # wait for socket to go "bad".
                yield zleep(0.002)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(1).value)

                # reuse -> send #fail -> new socket & retry.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('Done', body)

                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(2).value)
                pooledSocket = yield socketPool.getPooledSocket(host='localhost', port=mss.port)
                self.assertTrue(bool(pooledSocket.fileno()))
            finally:
                mss.close()

        asProcess(test())

    def testUnconditionalRetryOnlyOnce(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            # One OK -> into pool
            yield zleep(0.001)

            # And server closed socket for some reason (timeout, # parallel connections, ...).
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            yield zleep(0.001)
            # And again
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1, r2])
            socketPool = SocketPool(reactor=reactor())
            top = be((Observable(),
                (HttpRequest1_1(),
                    (socketPool,),
                )
            ))
            mss.listen()
            try:
                # new socket & into pool.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)

                # wait for socket to go "bad".
                yield zleep(0.002)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(1).value)

                # reuse -> send #fail -> new socket & retry -> #fails again
                try:
                    statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))

                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(2).value)
                pooledSocket = yield socketPool.getPooledSocket(host='localhost', port=mss.port)
                self.assertEquals(None, pooledSocket)
            finally:
                mss.close()

        asProcess(test())

    def testUnconditionalRetryOnPooledSocketFirstRecvNoDataOnlyFailing(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            # One OK -> into pool
            yield zleep(0.001)

            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            # Get the hopes up ...
            yield zleep(0.001)

            # ... and #fail.
            sok.shutdown(SHUT_RDWR); sok.close()

        def r2(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nDone")
            # In pool (cleanup here).
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1, r2])
            socketPool = SocketPool(reactor=reactor())
            top = be((Observable(),
                (HttpRequest1_1(),
                    (socketPool,),
                )
            ))
            mss.listen()
            try:
                # new socket & into pool.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])

                yield zleep(0.002)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(IN_PROGRESS, mss.state.connections.get(1).value)

                # reuse -> first recv #fail -> new socket & retry.
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('Done', body)

                self.assertEquals(2, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(1).value)
                self.assertEquals(None, mss.state.connections.get(2).value)
                pooledSocket = yield socketPool.getPooledSocket(host='localhost', port=mss.port)
                self.assertTrue(bool(pooledSocket.fileno()))
            finally:
                mss.close()

        asProcess(test())

    def testUnconditionalRetryOnPooledSocketEBADFFailing(self):
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nDone")
            # In pool (cleanup here).
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1])
            socketPool = SocketPool(reactor=reactor())
            top = be((Observable(),
                (HttpRequest1_1(),
                    (socketPool,),
                )
            ))
            mss.listen()
            try:
                # create new "bad" socket
                sok = socket(); sok.close()
                yield socketPool.putSocketInPool(host='localhost', port=mss.port, sock=sok)

                # new socket & into pool.
                with stderr_replaced() as err:
                    statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                    self.assertTrue('EBADF' in err.getvalue(), err.getvalue())
                    self.assertTrue('Bad file descriptor' in err.getvalue(), err.getvalue())
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                self.assertEquals('Done', body)

                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals(None, mss.state.connections.get(1).value)
                pooledSocket = yield socketPool.getPooledSocket(host='localhost', port=mss.port)
                self.assertTrue(bool(pooledSocket.fileno()))
            finally:
                mss.close()

        asProcess(test())

    def testNoUnconditionalRetryOnPooledSocketWhenDataAlreadyRecved(self):
        # ... in the context of the current connection.
        def r1(sok, log, remoteAddress, connectionNr):
            toRead = 'GET /first HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            log.append(1)

            toRead = 'GET /second HTTP/1.1\r\nHost: localhost\r\n\r\n'
            data = yield read(untilExpected=toRead)
            self.assertEquals(toRead, data)

            yield write("HTTP/1.1 Oh No!...")
            yield zleep(0.001)
            sok.shutdown(SHUT_RDWR); sok.close()

        def test():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1])
            socketPool = SocketPool(reactor=reactor())
            top = be((Observable(),
                (HttpRequest1_1(),
                    (socketPool,),
                )
            ))
            mss.listen()
            try:
                statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/first')
                self.assertEquals('200', statusAndHeaders['StatusCode'])
                yield zleep(0.001)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals((IN_PROGRESS, [1]), mss.state.connections.get(1))

                try:
                    statusAndHeaders, body = yield top.any.httprequest1_1(host='localhost', port=mss.port, request='/second')
                    self.fail()
                except ValueError, e:
                    self.assertEquals('Premature close', str(e))
            finally:
                mss.close()

        asProcess(test())

    def testHttpRequestAdapter(self):
        self.fail()

    ##
    ## Implementation-tests
    def testHttpPost(self):
        # Implementation-test for POST.
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request)
        body = u"BÖDY" * 20000

        def test():
            statusAndHeaders, _body = yield httprequest1_1(
                method='POST', host='localhost', port=port, request='/path', body=body,
                headers={
                    'Content-Type': 'text/plain',
                    'Host': 'vvvvvv.example.org',
                },
            )
            self.assertTrue("POST RESPONSE" in _body, _body)

        asProcess(test())

        self.assertEquals(1, len(post_request))
        post_req = post_request[0]
        self.assertEquals('POST', post_req['command'])
        self.assertEquals('/path', post_req['path'])
        headers = post_req['headers'].headers
        self.assertEquals(['Content-Length: 100000\r\n', 'Content-Type: text/plain\r\n', 'Host: vvvvvv.example.org\r\n'], sorted(headers))

    def testHttpPostWithoutExplicitHeaders(self):
        # Implementation-test:
        # Host header added (from host argument) if not given explicitly.
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request)
        body = u"BÖDY" * 20000
        def posthandler(*args, **kwargs):
            response = yield httprequest1_1(
                method='POST', host='localhost', port=port, request='/path', body=body,
            )
            yield response
            responses.append(response)

        def test():
            statusAndHeaders, _body = yield httprequest1_1(method='POST', host='localhost', port=port, request='/path', body=body)
            self.assertEquals('200', statusAndHeaders['StatusCode'])
            self.assertEquals("POST RESPONSE", _body)

        asProcess(test())

        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals([
                'Content-Length: 100000\r\n',
                'Host: localhost\r\n',
            ], sorted(headers))
        self.assertEquals(body, post_request[0]['body'])

    def testHttpsGet(self):
        # Implementation-test:
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request, ssl=True)

        def test():
            statusAndHeaders, body = yield httprequest1_1(
                    host='localhost', port=port, request='/path',
                    secure=True,
            )
            self.assertEquals('200', statusAndHeaders['StatusCode'])
            self.assertEquals("GET RESPONSE", body)

        asProcess(test())

        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])
        headers = get_request[0]['headers'].headers
        self.assertEquals(['Host: localhost\r\n'], headers)

    def testHttpsPost(self):
        # Implementation-test: Testing SSL/TLS with a "real" server.
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request, ssl=True)
        body = u"BÖDY" * 20000

        def test():
            statusAndHeaders, _body = yield httprequest1_1(
                method='POST', host='localhost', port=port, request='/path', body=body,
                headers={'Content-Type': 'text/plain'}, secure=True,
            )
            self.assertEquals('200', statusAndHeaders['StatusCode'])
            self.assertEquals("POST RESPONSE", _body)

        asProcess(test())

        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals([
                'Content-Length: 100000\r\n',
                'Content-Type: text/plain\r\n',
                'Host: localhost\r\n',
            ], sorted(headers))
        self.assertEquals(body, post_request[0]['body'])

    def testHttpGet(self):
        # Implementation-test
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        def test():
            statusAndHeaders, body = yield httprequest1_1(
                host='localhost', port=port, request='/path',
                headers={
                    'Content-Type': 'text/plain',
                    'Content-Length': 0
                },
                prio=4
            )
            self.assertEquals('200', statusAndHeaders['StatusCode'])
            self.assertEquals("GET RESPONSE", body)

        asProcess(test())

        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])
        headers = get_request[0]['headers'].headers
        self.assertEquals(sorted([
                'Content-Length: 0\r\n',
                'Content-Type: text/plain\r\n',
                'Host: localhost\r\n',
            ]),
            sorted(headers)
        )

    def testHttpWithUnsupportedMethod(self):
        # Implementation-test:
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        def test():
            statusAndHeaders, body = yield httprequest1_1(
                method='MYMETHOD', host='localhost', port=port, request='/path',
            )
            self.assertEquals('501', statusAndHeaders['StatusCode'])  # "Not Implemented"
            self.assertTrue("Message: Unsupported method ('MYMETHOD')" in body, body)

        asProcess(test())

    def testReallyLargeHeaders(self):
        # Implementation-test:
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        headersOrig = {'Accept': 'text/plain'}
        headersOrig.update([
            ('X-Really-Largely-Large-%s' % i, 'aLargelyLargeValue')
            for i in range(10000)
        ])
        def test():
            statusAndHeaders, body = yield httprequest1_1(
                host='localhost', port=port, request='/path',
                headers=headersOrig,
            )
            self.assertEquals('200', statusAndHeaders['StatusCode'])
            self.assertEquals("GET RESPONSE", body)

        asProcess(test())

        headers = get_request[0]['headers'].headers
        headersAsDict = dict([tuple(h.strip().split(': ', 1)) for h in headers])
        self.assertEquals(len(headersOrig), len(headersAsDict))
        self.assertEquals(headersOrig, headersAsDict)

        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])

    ##
    ## Internals
    def testSocketWrapper(self):
        trace = CallTrace(methods={'recv': lambda *a, **kw: '12'})
        trace.a = 'b'
        sw = SocketWrapper(sok=trace)

        # Wrapper used once per connection-request; recievedData initially False.
        self.assertEquals(False, sw.recievedData)

        # Any method / property passed on and memoized.
        self.assertTrue(callable(sw.whatever))
        self.assertEquals('b', sw.a)
        trace.a = 'c'
        self.assertEquals('b', sw.a)  # still a; properties on a socket obj. don't change - so not a problem.

        # Other method calls don't change recievedData state.
        sw.send('daataaa')
        self.assertEquals(False, sw.recievedData)

        # recv does
        result = sw.recv(44)
        self.assertEquals('12', result)
        self.assertEquals(True, sw.recievedData)
        self.assertTrue(trace is sw.unwrap_recievedData())

        # recv with no data does not
        trace = CallTrace(methods={'recv': lambda *a, **kw: ''})
        sw = SocketWrapper(sok=trace)
        self.assertEquals(False, sw.recievedData)
        result = sw.recv(bufsize=33, flags='No Idea')
        self.assertEquals('', result)
        self.assertEquals(False, sw.recievedData)

    def testDeChunk(self):
        # Initial size 0 - all-in-one "packet".
        dc = _deChunk()
        try:
            dc.send('0\r\n\r\n')
            self.fail()
        except StopIteration, e:
            self.assertEquals(0, len(e.args))

        # Initial size 1; then 0 - all-in-one "packet".
        dc = _deChunk()
        self.assertEquals('A', dc.send('1\r\nA\r\n0\r\n\r\n'))
        try:
            dc.send(None)
            self.fail()
        except StopIteration, e:
            self.assertEquals(0, len(e.args))

        # Initial size 3; then 0 - multiple "packets".
        dc = _deChunk()
        self.assertEquals(None, dc.send('3\r'))
        self.assertEquals(None, dc.send('\n'))
        self.assertEquals(None, dc.send('A'))
        self.assertEquals(None, dc.send('B'))
        self.assertEquals(None, dc.send('C'))
        self.assertEquals(None, dc.send('\r'))
        self.assertEquals('ABC', dc.send('\n'))
        self.assertEquals(None, dc.send(None))
        self.assertEquals(None, dc.send('0'))
        self.assertEquals(None, dc.send('\r'))
        self.assertEquals(None, dc.send('\n'))
        self.assertEquals(None, dc.send('\r'))
        try:
            dc.send('\n')
            self.fail()
        except StopIteration, e:
            self.assertEquals(0, len(e.args))

        # Initial size 2; then 3; then 0; then trailers - all-in-one "packet".
        dc = _deChunk()
        self.assertEquals('AB', dc.send('2\r\nAB\r\n3\r\nCDE\r\n0\r\nTrailing1: Header1\r\nTrailing2: Header2\r\n\r\n'))
        self.assertEquals('CDE', dc.send(None))
        try:
            dc.send(None)
            self.fail()
        except StopIteration, e:
            self.assertEquals(0, len(e.args))

        # Initial size 2; then 3; then 0 - multiple "packets".
        dc = _deChunk()
        self.assertEquals(None, dc.send('2\r\nA'))
        self.assertEquals('AB', dc.send('B\r\n3\r\nCDE\r'))
        self.assertEquals(None, dc.send(None))
        self.assertEquals('CDE', dc.send('\n0\r\nTrailing1: Header1\r'))
        self.assertEquals(None, dc.send(None))
        self.assertEquals(None, dc.send('\nTrailing2: Header2\r\n\r'))
        try:
            dc.send('\n')
            self.fail()
        except StopIteration, e:
            self.assertEquals(0, len(e.args))

    def testDeChunkFailsOnExcessData(self):
        # Note: this can only reliably be detection if sok.recv(n) data
        #       included (a bit of) excess-data.  Otherwise undetected
        #       until socket-reuse fails horribly.

        # after size 0
        dc = _deChunk()
        try:
            dc.send('0\r\n\r\n<EXCESS-DATA>')
            self.fail()
        except ValueError, e:
            self.assertEquals('Data after last chunk', str(e))

        # after trailers
        dc = _deChunk()
        self.assertEquals(None, dc.send('0\r\nTrai: ler\r\n\r'))
        try:
            dc.send('\nX')
        except ValueError, e:
            self.assertEquals('Data after last chunk', str(e))

    def testShutdownAndCloseOnce_OnlyOnce(self):
        sok = CallTrace()
        cb = _shutAndCloseOnce(sok)
        self.assertEquals([], sok.calledMethodNames())

        cb()
        self.assertEquals(['shutdown', 'close'], sok.calledMethodNames())
        shutdown, close = sok.calledMethods
        self.assertEquals(((), {}), (close.args, close.kwargs))
        self.assertEquals(((SHUT_RDWR,), {}), (shutdown.args, shutdown.kwargs))

        sok.calledMethods.reset()
        cb()
        self.assertEquals([], sok.calledMethodNames())

    def testShutdownAndCloseOnce_Exceptions(self):
        sok = CallTrace()
        sok.exceptions['shutdown'] = Exception('xcptn')
        cb = _shutAndCloseOnce(sok)
        self.assertEquals([], sok.calledMethodNames())

        self.assertRaises(Exception, lambda: cb())
        self.assertEquals(['shutdown'], sok.calledMethodNames())
        shutdown = sok.calledMethods[0]
        self.assertEquals(((SHUT_RDWR,), {}), (shutdown.args, shutdown.kwargs))

        sok.calledMethods.reset()
        cb()
        self.assertEquals(['close'], sok.calledMethodNames())
        close = sok.calledMethods[0]
        self.assertEquals(((), {}), (close.args, close.kwargs))

        sok.calledMethods.reset()
        cb()
        self.assertEquals([], sok.calledMethodNames())

    def testShutdownAndCloseOnce_IgnoreExceptions(self):
        sok = CallTrace()
        sok.exceptions['shutdown'] = Exception('xcptn')
        cb = _shutAndCloseOnce(sok)
        self.assertEquals([], sok.calledMethodNames())

        cb(ignoreExceptions=True)
        self.assertEquals(['shutdown', 'close'], sok.calledMethodNames())
        shutdown, close = sok.calledMethods
        self.assertEquals(((SHUT_RDWR,), {}), (shutdown.args, shutdown.kwargs))
        self.assertEquals(((), {}), (close.args, close.kwargs))

        sok.calledMethods.reset()
        cb(ignoreExceptions=True)
        self.assertEquals([], sok.calledMethodNames())

    def testRequestLine(self):
        self.assertEquals('GET / HTTP/1.1\r\n', _requestLine('GET', '/'))
        self.assertEquals('POST / HTTP/1.1\r\n', _requestLine('POST', '/'))

    def testChunkRe(self):
        def m(s):
            return _CHUNK_RE.match(s)

        s = '0\r\n'
        self.assertTrue(m(s))
        self.assertEquals((0, 1), (m(s).start(1), m(s).end(1)))
        self.assertEquals('0\r\n', m(s).group())
        self.assertEquals('0\r\n', m(s).group(0))
        self.assertEquals('0', m(s).group(1))
        self.assertEquals((0, 3), (m(s).start(), m(s).end()))
        self.assertEquals((0, 3), (m(s).start(0), m(s).end(0)))

        s = 'a05fBc\r\n'
        self.assertTrue(m(s))
        self.assertEquals(s, m(s).group())
        self.assertEquals('a05fBc', m(s).group(1))

        s = 'a5;chunky=extension;q=x;aap=noot\r\n'
        self.assertTrue(m(s))
        self.assertEquals(s, m(s).group())
        self.assertEquals('a5', m(s).group(1))

        s = 'a5;&*!@)_==++>>WHATEVER<<\r\n'  # We're more permissive than needed.
        self.assertTrue(m(s))
        self.assertEquals(s, m(s).group())
        self.assertEquals('a5', m(s).group(1))

        s = 'a5\r\nb4\r\n'
        self.assertTrue(m(s))
        self.assertEquals('a5\r\n', m(s).group())
        self.assertEquals('a5', m(s).group(1))

        self.assertFalse(m(''))
        self.assertFalse(m('g1\r\n'))  # Not hexadecimal.
        self.assertFalse(m('\r\n1\r\n'))
        self.assertFalse(m('\n1\r\n'))
        self.assertFalse(m('12'))
        self.assertFalse(m('12\r'))
        self.assertFalse(m('12\r\r'))
        self.assertFalse(m('12\r\r\n'))
        self.assertFalse(m('12\n'))
        self.assertFalse(m('12\n\r'))
        self.assertFalse(m('12\n\r\n'))

    def testTrailersRe(self):
        def m(s):
            return _TRAILERS_RE.match(s)

        s = '\r\n'
        self.assertTrue(m(s))
        self.assertEquals('\r\n', m(s).group())
        self.assertEquals(0, m(s).start())
        self.assertEquals(2, m(s).end())
        self.assertEquals({'_trailers': None}, m(s).groupdict())

        s = 'Head: Er\r\n\r\n'
        self.assertEquals(0, m(s).start())
        self.assertEquals(12, m(s).end())
        self.assertEquals({'_trailers': 'Head: Er\r\n'}, m(s).groupdict())

        s = 'H1: V1\r\nH2: V2\r\n\r\n'
        self.assertEquals(0, m(s).start())
        self.assertEquals(18, m(s).end())
        self.assertEquals({'_trailers': 'H1: V1\r\nH2: V2\r\n'}, m(s).groupdict())

        s = 'H1: V1\r\nH2: V2\r\nH3: V3\r\n\r\n'
        self.assertEquals(0, m(s).start())
        self.assertEquals(26, m(s).end())
        self.assertEquals({'_trailers': 'H1: V1\r\nH2: V2\r\nH3: V3\r\n'}, m(s).groupdict())

        # trailers parsable as headers
        self.assertEquals({
                'H1': 'V1',
                'H2': 'V2',
                'H3': 'V3',
            },
            parseHeaders(m(s).groupdict()['_trailers'])
        )

        self.assertFalse(m('\n\n'))
        self.assertFalse(m('\n\r'))
        self.assertFalse(m('\r\r'))
        self.assertFalse(m('\n\n\n'))
        self.assertFalse(m('\n\n\r'))
        self.assertFalse(m('\n\r\n'))
        self.assertFalse(m('\r\r\n'))

    ##
    ## MockSocketServer tests (incomplete / rough) ##
    def testMockSocketServerFailsOnUnexpectedRequests(self):
        serverFailsRequestDoesNot = []
        def run():
            mss = MockSocketServer(); mss.listen()
            yield httprequest1_1(method='GET', host='127.0.0.1', port=mss.port, request='/')
            serverFailsRequestDoesNot.append("Won't come here.")

        try:
            with stdout_replaced():  # Ignore reactor.shutdown() noticing httprequest1_1 still in-the-air.
                asProcess(run())
        except AssertionError, e:
            self.assertTrue(str(e).startswith('Unexpected Connection #1 from: 127.0.0.1:'), str(e))

        self.assertEquals(0, len(serverFailsRequestDoesNot))

    def testMockSocketServerOneRequestExpectedAndCompleted(self):
        def r1(sok, log, remoteAddress, connectionNr):
            #data = yield read(forSeconds=0.1)
            data = yield read(untilExpected='GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
            yield write(data='HTTP/1.1 200 Okidokie\r\nContent-Length: 0\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()
            raise StopIteration(data)

        def run():
            mss = MockSocketServer()
            mss.setReplies(replies=[r1])
            mss.listen()
            try:
                statusAndHeaders, body = yield httprequest1_1(method='GET', host='127.0.0.1', port=mss.port, request='/')
                self.assertEquals({
                        'HTTPVersion': '1.1',
                        'Headers': {
                            'Content-Length': '0'
                        },
                        'ReasonPhrase': 'Okidokie',
                        'StatusCode': '200'
                    },
                    statusAndHeaders
                )
                self.assertEquals('', body)
                self.assertEquals(1, mss.nrOfRequests)
                self.assertEquals({1: ('GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n', [])}, mss.state.connections)
            finally:
                mss.close()
            raise StopIteration(42)

        result = asProcess(run())
        self.assertEquals(42, result)


class MockSocketServer(object):
    """
    Meaning of life being:
     - Mock a HTTP/1.1 Server

    Must be used **inside** asProcess (__reactor__ callstack variable must be accessable).
    """

    def __init__(self):
        self.port = PortNumberGenerator.next()
        self.nrOfRequests = 0
        self.setReplies()  # Default handler - any connection fails.

    def setReplies(self, replies=None):
        replies = replies or []
        self.state = _ExactExpectationHandler(server=self, replies=replies)

    def listen(self):
        self._listenSok = socket()
        self._listenSok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self._listenSok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        self._listenSok.bind(('127.0.0.1', self.port))
        self._listenSok.listen(5)  # Kindof arbitrary.
        reactor().addReader(sok=self._listenSok, sink=self._accept)

    def close(self, exclude=None):
        if self._listenSok is None:
            return  # Allow multiple calls to close (2..n no-op).
        reactor().removeReader(sok=self._listenSok)
        self._listenSok.shutdown(SHUT_RDWR)
        self._listenSok.close()
        self._listenSok = None
        self.state.close(exclude=exclude)

    def _accept(self):
        self.nrOfRequests += 1
        newConnection, remoteAddress = self._listenSok.accept()
        newConnection.setblocking(0)  # Won't hang, some tests may be simples when (briefly) setting it to blocking again.
        newConnection.setsockopt(SOL_TCP, TCP_NODELAY, 1)  # Many small packets in a hurry.
        #newConnection.setsockopt(SOL_TCP, TCP_CORK, 1)  # Few large package waiting a bit for more data.
        self.state(sok=newConnection, remoteAddress=remoteAddress, connectionNr=self.nrOfRequests)


class _ExactExpectationHandler(object):
    def __init__(self, server, replies):
        self._server = server
        self._replies = replies

        self._replyIndex = -1
        self.busy = set()
        self.connections = {}

    def __call__(self, sok, remoteAddress, connectionNr):
        self._replyIndex += 1
        if self._replyIndex >= len(self._replies):
            return self._noConnectionHandler(sok=sok, remoteAddress=remoteAddress, connectionNr=connectionNr)

        return self._startAndTrackCompletion(gf=self._replies[self._replyIndex], sok=sok, remoteAddress=remoteAddress, connectionNr=connectionNr)

    def close(self, exclude=None):
        for handler in list(self.busy):
            if handler == exclude:
                continue  # If set, excluded itself is initiating the close because of a fatal error.
            handler.throw(AbortException, AbortException('Closing MockSocketServer connections'), None)

    def _startAndTrackCompletion(self, gf, sok, remoteAddress, connectionNr):
        @identify
        @compose
        def wrapper():
            # Arguments easily callstack-retrievable.
            __sok__ = sok
            __log__ = log = []
            __remoteAddress__ = remoteAddress
            __connectionNr__ = connectionNr

            this = __this__ = yield
            self.busy.add(this)
            self.connections[connectionNr] = _Connection(IN_PROGRESS, log)
            reactor().addProcess(process=this.next)
            _removeProcess = True
            yield
            try:
                try:
                    g = compose(gf(sok=sok, log=log, remoteAddress=remoteAddress, connectionNr=connectionNr))
                except Exception, e:
                    raise AssertionError('Test error: MockSocketServer connection reply #{connectionNr} riased %{error}s - should have resulted in a generator'.format({'error': repr(e), 'connectionNr': connectionNr}))

                try:
                    try:
                        while True:
                            sys.stdout.flush()
                            _response = g.next()
                            sys.stdout.flush()
                            if _response is not Yield and callable(_response):
                                _response(reactor(), this.next)
                                _removeProcess = False
                                yield
                                _removeProcess = True
                                _response.resumeProcess()
                            yield
                    except StopIteration, e:
                        retval = e.args[0] if e.args else None
                except AssertionError:
                    c, v, t = exc_info()
                    msg = 'Connection reply #{nr} from {host}:{port} failed with:\n'.format(**{
                        'nr': connectionNr,
                        'host': remoteAddress[0],
                        'port': remoteAddress[1],
                    }) + str(v)
                    raise c, c(msg), t
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception, e:
                    if not isinstance(e, AbortException):
                        print_exc()  # HCK
                    retval = e
            except (AssertionError, KeyboardInterrupt, SystemExit):
                self._server.close(exclude=this)  # cleans up server and self.
                raise
            finally:
                if _removeProcess:
                    reactor().removeProcess(process=this.next)
                self.busy.remove(this)

            self.connections[connectionNr] = _Connection(retval, log)
            yield  # Wait for GC

        wrapper()

    def _noConnectionHandler(self, sok, remoteAddress, connectionNr):
        sok.shutdown(SHUT_RDWR); sok.close()
        self._server.close()  # cleans up server and self.
        raise AssertionError('Unexpected Connection #{0} from: {1}:{2}!'.format(connectionNr, *remoteAddress))


IN_PROGRESS = type('IN_PROGRESS', (object,), {})()


def read(bytes=None, forSeconds=None, untilExpected=None, timeout=1.0):
    """
    MockSocketServer' handler helper functions.
    Use these instead of recv/write yourself.

    bytes:
        Minimal number of bytes to read.
    forSeconds:
        Attempt to read as much as possible within the given time.
    untilExpected:
        Expected string (startswith check) or function which must return true when read data is "expected."
    timeout:
        Must be set to some sane, low value - otherwise test hangs indefinitely.
    """
    if not (sum((int(bytes is not None), int(forSeconds is not None), int(untilExpected is not None))) == 1):
        raise AssertionError('One of either bytes, forSeconds or untilExpected must be given.')

    bytesRead = ''
    startTime = time()

    timeoutRelative = lambda: max(float(timeout) - (time() - startTime), 0)

    if bytes is not None:
        test = lambda bytesRead: len(bytesRead) >= bytes
    if untilExpected is not None:
        if isinstance(untilExpected, basestring):
            test = lambda bytesRead: bytesRead.startswith(untilExpected)
        else:  # callable presumed
            test = lambda bytesRead: untilExpected(bytesRead)
    if forSeconds is not None:
        if timeout < forSeconds:
            raise AssertionError('timeout < forSeconds')
        test = lambda bytesRead: time() - startTime >= forSeconds
        timeout = forSeconds

    while not test(bytesRead):
        try:
            bytesRead += yield _readOnce(timeout=timeoutRelative())
        except (AssertionError, KeyboardInterrupt, SystemExit):
            raise
        except TimeoutException:
            if forSeconds is None:
                msg = '''Timeout reached while trying:
    read(bytes={bytes}, forSeconds={forSeconds}, untilExpected={untilExpected}, timeout={timeout})

Read so far:\n{bytesRead}'''.format(**{
                    'bytes': bytes,
                    'forSeconds': forSeconds,
                    'untilExpected': repr(untilExpected),
                    'timeout': timeout,
                    'bytesRead': repr(bytesRead),
                })
                raise AssertionError(msg)

    raise StopIteration(bytesRead)

def _readOnce(timeout):
    sok = local('__sok__')
    g = _readOnceGF(sok=sok)
    def onTimeout():
        g.throw(TimeoutException, TimeoutException(), None)
    s = Suspend(doNext=g.send, timeout=timeout, onTimeout=onTimeout)
    yield s
    result = s.getResult()
    raise StopIteration(result)

@identify
@compose
def _readOnceGF(sok):
    this = yield
    suspend = yield

    suspend._reactor.addReader(sok=sok, sink=this.next)
    try:
        try:
            yield
            data = sok.recv(4096)
        finally:
            suspend._reactor.removeReader(sok=sok)
        suspend.resume(data)
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        pass
    except Exception:
        suspend.throw(*exc_info())
    yield  # wait for GC


def write(data, timeout=1.0):
    """
    MockSocketServer' handler helper functions.
    Use these instead of recv/write yourself.

    data:
        Data to write (minimum)
    timeout:
        Must be set to some sane, low value - otherwise test hangs indefinitely.
    """

    startTime = time()
    timeoutRelative = lambda: max(float(timeout) - (time() - startTime), 0)
    remaining = data

    while remaining:
        try:
            remaining = yield _writeOnce(remaining, timeout=timeoutRelative())
        except TimeoutException:
            msg = '''Timeout reached while trying:
    write(data={data}, timeout={timeout})

Written so far:\n{written}'''.format(**{
                'data': repr(data),
                'timeout': timeout,
                'written': repr(data[:-len(remaining)]),
            })
            raise AssertionError(msg)


def _writeOnce(data, timeout):
    sok = local('__sok__')
    if isinstance(data, unicode):
        raise AssertionError('Expects a string, not unicode')

    g = _writeOnceGF(sok=sok, data=data)
    def onTimeout():
        g.throw(TimeoutException, TimeoutException(), None)
    s = Suspend(doNext=g.send, timeout=timeout, onTimeout=onTimeout)
    yield s
    result = s.getResult()
    raise StopIteration(result)

@identify
@compose
def _writeOnceGF(sok, data):
    this = yield
    suspend = yield

    suspend._reactor.addWriter(sok=sok, source=this.next)
    try:
        try:
            yield
            bytesSent = sok.send(data)
            remaining = data[bytesSent:]
        finally:
            suspend._reactor.removeWriter(sok=sok)
        suspend.resume(remaining)
    except (AssertionError, KeyboardInterrupt, SystemExit):
        raise
    except TimeoutException:
        pass
    except Exception:
        suspend.throw(*exc_info())
    yield  # wait for GC

class AbortException(Exception):
    pass

_Connection = namedtuple('Connection', ['value', 'log'])

def dieAfter(seconds=5.0):
    """
    Decorator for generator-function passed to asProcess to execute; for setting deadline.
    """
    def dieAfter(generatorFunction):
        @wraps(generatorFunction)
        @identify
        def helper(*args, **kwargs):
            this = yield
            yield  # Works within an asProcess-passed generatorFunction only (needs contextual addProcess driving this generator and a reactor).
            tokenList = []
            def cb():
                tokenList.pop()
                this.throw(AssertionError, AssertionError('dieAfter triggered after %s seconds.' % seconds), None)
            tokenList.append(reactor().addTimer(seconds=seconds, callback=cb))
            try:
                retval = yield generatorFunction(*args, **kwargs)
            except:
                c, v, t = exc_info()
                if tokenList:
                    reactor().removeTimer(token=tokenList[0])
                raise c, v, t
        return helper
    return dieAfter

def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

fileDict = {
    '__file__': ignoreLineNumbers.func_code.co_filename,
    '_suspend.py': Suspend.__call__.func_code.co_filename,
    '_httprequest1_1.py': _requestLine.func_code.co_filename,
}

