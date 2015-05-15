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

from __future__ import with_statement

from seecr.test.io import stderr_replaced, stdout_replaced
from seecr.test.portnumbergenerator import PortNumberGenerator
from weightlesstestcase import WeightlessTestCase, StreamingData
from httpreadertest import server as testserver

import sys
from re import sub
from socket import socket, gaierror as SocketGaiError, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, SOL_TCP, TCP_NODELAY, SHUT_RDWR
from struct import pack
from sys import exc_info, version_info
from time import sleep, time
from traceback import format_exception, print_exc

from weightless.core import compose, identify, is_generator, Yield, local
from weightless.io import Reactor, Suspend, TimeoutException, reactor
from weightless.io.utils import asProcess
from weightless.http import HttpServer
from weightless.http._persistenthttprequest import httprequest, httpget, httppost, httpspost, httpsget, HttpRequest

from weightless.http._persistenthttprequest import _requestLine
from weightless.http import _persistenthttprequest as persistentHttpRequestModule


PYVERSION = '%s.%s' % version_info[:2]


# Context:
# - Request always HTTP/1.1
# - Requests always have Content-Length: <n> specified (less logic / no need for request chunking - or detection if the server is capable of recieving it)
# - Never send "Connection: close"; after processing request, determine if "back-in-Pool" or close.
# - Server response usually HTTP/1.1, HTTP/1.0 handled via closing socket (thus being persistent [FIXME: should we warn in that situation?]!)
# - Pool semantics extremly simple, more complex / tested behaviour only when extracted (DNA/Dependency Injection) and in a separate testcase covered!
# - Variables are:
#   {
#       http: <1.1/1.0>  # Server response HTTP version
#       EOR: chunking / content-length / close  # End-Of-Response, signaled by: "Transfer-Encoding: chunked", "Content-Length: <n>" or "Connection: close".
#       explicit-close: <True/(False|Missing)>  # Wether, irrespective of EOR-signaling, the server wants to close the connection at EOR.
#       comms: <ok/retry/double-fail/pooled-unusable>  # Comms goes awry somehow.
#   }

class PersistentHttpRequestTest(WeightlessTestCase):
    def setUp(self):
        WeightlessTestCase.setUp(self)
        self.reactor = Reactor()
        self.port = PortNumberGenerator.next()

    def startReferenceHttpServer(self):
        self.httpserver = HttpServer(self.reactor, self.port, self._dispatch)
        self.httpserver.listen()

    def tearDown(self):
        if hasattr(self, 'httpserver'):
            self.httpserver.shutdown()
        WeightlessTestCase.tearDown(self)

    def testRequestLine(self):
        self.assertEquals('GET / HTTP/1.1\r\n', _requestLine('GET', '/'))
        self.assertEquals('POST / HTTP/1.1\r\n', _requestLine('POST', '/'))

    def testHttp11WithoutResponseChunkingOrDataReusedOnce(self):
        # Happy-Path, least complex, still persisted
        # {http: 1.1, EOR: content-length, comms: ok}
        self.fail()

    ###                                  ###
    ### Old (Unported) Tests Demarkation ###
    ###                                  ###
    def testPassRequestThruToBackOfficeServer(self):
        self.startReferenceHttpServer()
        backofficeport = PortNumberGenerator.next()
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request)
            yield response
        self.handler = passthruhandler
        expectedrequest = "GET /depot?arg=1&arg=2 HTTP/1.1\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        client = clientget('localhost', self.port, '/depot?arg=1&arg=2')
        self._loopReactorUntilDone()
        response = client.recv(99)
        self.assertEquals('hello!', response)

    def testPassRequestThruToBackOfficeServerWithHttpRequest(self):
        self.startReferenceHttpServer()
        backofficeport = PortNumberGenerator.next()
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield HttpRequest().httprequest(host='localhost', port=backofficeport, request=request)
            yield response
        self.handler = passthruhandler
        expectedrequest = "GET /depot?arg=1&arg=2 HTTP/1.1\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        client = clientget('localhost', self.port, '/depot?arg=1&arg=2')
        self._loopReactorUntilDone()
        response = client.recv(99)
        self.assertEquals('hello!', response)

    @stderr_replaced
    def testConnectFails(self):
        self.startReferenceHttpServer()
        def failingserver(*args, **kwarg):
            response = yield httpget(*target)

        self.handler = failingserver

        clientget('localhost', self.port, '/')
        target = ('localhost', 'port', '/') # non-numeric port
        self._loopReactorUntilDone()

        expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 0, in handle
      yield self.handler(*args, **kwargs)
  File "%(__file__)s", line 85, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 78, in httprequest
    result = s.getResult()
  File "%(suspend.py)s", line 34, in __call__
    self._doNext(self)
  File "%(httprequest.py)s", line 35, in _do
    sok.connect((host, port))
  File "<string>", line 1, in connect
TypeError: an integer is required
       """ % fileDict)
        if PYVERSION == "2.7":
            expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 0, in handle
      yield self.handler(*args, **kwargs)
  File "%(__file__)s", line 85, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 78, in httprequest
    result = s.getResult()
  File "%(suspend.py)s", line 34, in __call__
    self._doNext(self)
  File "%(httprequest.py)s", line 35, in _do
    sok.connect((host, port))
  File "/usr/lib/python2.7/socket.py", line [#], in meth
    return getattr(self._sock,name)(*args)
TypeError: an integer is required
       """ % fileDict)
        self.assertEquals(TypeError, self.error[0])
        # FIXME: re-enable traceback testing (below)!
        #self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(''.join(format_exception(*self.error))))

        target = ('localhost', 87, '/') # invalid port
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(IOError, self.error[0])

        target = ('UEYR^$*FD(#>NDJ.khfd9.(*njnd', 9876, '/') # invalid host
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(SocketGaiError, self.error[0])

        target = ('127.0.0.1', PortNumberGenerator.next(), '/')  # No-one listens
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(IOError, self.error[0])
        self.assertEquals('111', str(self.error[1]))

    @stdout_replaced
    def testTracebackPreservedAcrossSuspend(self):
        self.startReferenceHttpServer()
        backofficeport = PortNumberGenerator.next()
        expectedrequest = ''
        testserver(backofficeport, [], expectedrequest)
        target = ('localhost', backofficeport, '/')

        exceptions = []
        def failingserver(*args, **kwarg):
            response = yield httpget(*target)
        self.handler = failingserver

        def requestLine(self, *args, **kwargs):
            raise RuntimeError("Boom!")

        try:
            originalRequestLine = persistentHttpRequestModule._requestLine
            persistentHttpRequestModule._requestLine = requestLine

            clientget('localhost', self.port, '/')
            with stderr_replaced():
                self._loopReactorUntilDone()

            expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 0, in handle
      yield self.handler(*args, **kwargs)
  File "%(__file__)s", line 192, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 129, in httprequest
    result = s.getResult()
  File "%(httprequest.py)s", line 83, in _do
    yield _sendHttpHeaders(sok, method, request, headers)
  File "%(httprequest.py)s", line 121, in _sendHttpHeaders
    data = _requestLine(method, request)
  File "%(__file__)s", line 198, in requestLine
    raise RuntimeError("Boom!")
RuntimeError: Boom!""" % fileDict)
            resultingTraceback = ''.join(format_exception(*self.error))
            # FIXME: re-enable traceback testing (below)!
            #self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(resultingTraceback))
            self.assertTrue('RuntimeError: Boom!' in resultingTraceback, resultingTraceback)

        finally:
            persistentHttpRequestModule._requestLine = originalRequestLine

    def testHttpPost(self):
        self.startReferenceHttpServer()
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request)
        body = u"BÖDY" * 20000
        responses = []
        def posthandler(*args, **kwargs):
            response = yield httppost('localhost', port, '/path', body,
                    headers={'Content-Type': 'text/plain'}
            )
            yield response
            responses.append(response)
        self.handler = posthandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue("POST RESPONSE" in responses[0], responses[0])
        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 100000\r\n', 'Content-Type: text/plain\r\n'], headers)
        self.assertEquals(body, post_request[0]['body'])

    def testHttpPostWithoutHeaders(self):
        self.startReferenceHttpServer()
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request)
        body = u"BÖDY" * 20000
        responses = []
        def posthandler(*args, **kwargs):
            response = yield httppost('localhost', port, '/path', body)
            yield response
            responses.append(response)
        self.handler = posthandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue("POST RESPONSE" in responses[0], responses[0])
        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 100000\r\n'], headers)
        self.assertEquals(body, post_request[0]['body'])

    def testHttpsPost(self):
        self.startReferenceHttpServer()
        post_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, post_request, ssl=True)
        body = u"BÖDY" * 20000
        responses = []
        def posthandler(*args, **kwargs):
            response = yield httpspost('localhost', port, '/path', body,
                    headers={'Content-Type': 'text/plain'}
            )
            yield response
            responses.append(response)
        self.handler = posthandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue("POST RESPONSE" in responses[0], responses[0])
        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 100000\r\n', 'Content-Type: text/plain\r\n'], headers)
        self.assertEquals(body, post_request[0]['body'])

    @stderr_replaced
    def testHttpsPostOnIncorrectPort(self):
        self.startReferenceHttpServer()
        responses = []
        def posthandler(*args, **kwargs):
            response = yield httpspost('localhost', PortNumberGenerator.next(), '/path', "body",
                    headers={'Content-Type': 'text/plain'}
            )
            yield response
            responses.append(response)
        self.handler = posthandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue(self.error[0] is IOError)
        self.assertEquals("111", str(self.error[1]))

    def testHttpGet(self):
        self.startReferenceHttpServer()
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        responses = []
        def gethandler(*args, **kwargs):
            response = 'no response yet'
            try:
                response = yield httpget('localhost', port, '/path',
                        headers={'Content-Type': 'text/plain', 'Content-Length': 0},
                        prio=4
                )
            finally:
                responses.append(response)
        self.handler = gethandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue("GET RESPONSE" in responses[0], responses[0])
        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])
        headers = get_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 0\r\n', 'Content-Type: text/plain\r\n'], headers)

    def testHttpRequest(self):
        self.startReferenceHttpServer()
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        responses = []
        def gethandler(*args, **kwargs):
            response = 'no response yet'
            try:
                response = yield httprequest(method='MYMETHOD', host='localhost', port=port, request='/path',
                    headers={'Content-Type': 'text/plain', 'Content-Length': 0},
                    prio=4
                )
            finally:
                responses.append(response)
        self.handler = gethandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        self.assertTrue("Message: Unsupported method ('MYMETHOD')" in responses[0], responses[0])

    # FIXME: Re-Enable me (gives referenceHttpServer printed stacktraces (another thread))!
    def testHttpRequestWithTimeout(self):
        # And thus too http(s)get/post/... and friends.
        self.startReferenceHttpServer()
        get_request = []
        port = PortNumberGenerator.next()
        def slowData():
            for i in xrange(5):
                yield i
                sleep(0.01)

        responses = []
        def handlerFactory(timeout):
            def gethandler(*args, **kwargs):
                try:
                    response = yield httprequest(method='GET', host='localhost', port=port, request='/path',
                        headers={'Content-Type': 'text/plain', 'Content-Length': 0, 'Host': 'localhost'},
                        timeout=timeout,
                    )
                    responses.append(response)
                except TimeoutException, e:
                    responses.append(e)
                finally:
                    assert responses, 'Either a timeout or response should have occurred.'
            return gethandler

        # Not timing out
        self.referenceHttpServer(port=port, request=get_request, streamingData=slowData())
        self.handler = handlerFactory(timeout=0.5)
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertTrue(len(responses) >= 1)
        responseText = ''.join(responses)
        self.assertTrue(responseText.startswith('HTTP/1.0 200 OK'), responseText)
        self.assertTrue('01234' in responseText, responseText)
        self.assertEquals(1, len(get_request))

        # Timing out
        del get_request[:]
        del responses[:]
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port=port, request=get_request, streamingData=slowData())
        self.handler = handlerFactory(timeout=0.02)
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals([TimeoutException], [type(r) for r in responses])
        self.assertEquals(1, len(get_request))
        self.assertEquals('GET', get_request[0]['command'])

    def testHttpGetWithReallyLargeHeaders(self):
        self.startReferenceHttpServer()
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request)

        responses = []
        headersOrig = {'Accept': 'text/plain'}
        headersOrig.update([
            ('X-Really-Largely-Large-%s' % i, 'aLargelyLargeValue')
            for i in range(10000)
        ])
        def gethandler(*args, **kwargs):
            response = 'no response yet'
            try:
                response = yield httpget('localhost', port, '/path',
                    headers=headersOrig,
                )
            finally:
                responses.append(response)
        self.handler = gethandler
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()

        headers = get_request[0]['headers'].headers
        headersAsDict = dict([tuple(h.strip().split(': ', 1)) for h in headers])
        self.assertEquals(len(headersOrig), len(headersAsDict))
        self.assertEquals(headersOrig, headersAsDict)

        self.assertTrue("GET RESPONSE" in responses[0], responses[0])
        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])

    def testHttpsGet(self):
        self.startReferenceHttpServer()
        get_request = []
        port = PortNumberGenerator.next()
        self.referenceHttpServer(port, get_request, ssl=True)

        responses = []
        def gethandler(*args, **kwargs):
            response = yield httpsget('localhost', port, '/path',
                    headers={'Content-Type': 'text/plain', 'Content-Length': 0}
            )
            yield response
            responses.append(response)
        self.handler = gethandler
        clientget('localhost', self.port, '/')

        self._loopReactorUntilDone()

        self.assertTrue("GET RESPONSE" in responses[0], responses[0])
        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])
        headers = get_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 0\r\n', 'Content-Type: text/plain\r\n'], headers)

    ## MockSocketServer tests (incomplete / rough) ##
    def testMockSocketServerFailsOnUnexpectedRequests(self):
        serverFailsRequestDoesNot = []
        def run():
            mss = MockSocketServer(); mss.listen()
            yield httprequest(method='GET', host='127.0.0.1', port=mss.port, request='/')
            serverFailsRequestDoesNot.append("Won't come here.")

        try:
            with stdout_replaced():  # Ignore reactor.shutdown() noticing httprequest still in-the-air.
                asProcess(run())
        except AssertionError, e:
            self.assertTrue(str(e).startswith('Unexpected Connection #1 from: 127.0.0.1:'), str(e))

        self.assertEquals(0, len(serverFailsRequestDoesNot))

    def testMockSocketServerOneRequestExpectedAndCompleted(self):
        def r1(sok, remoteAddress, connectionNr):
            sys.stdout.flush()
            #data = yield read(forSeconds=0.1)
            data = yield read(untilExpected='GET / HTTP/1.1\r\n\r\n')  # ??: host headers mandatory!
            yield write(data='HTTP/1.1 200 Okidokie\r\nContent-Length: 0\r\n\r\n')
            sok.shutdown(SHUT_RDWR); sok.close()
            raise StopIteration(data)

        def run():
            mss = MockSocketServer()
            mss.setHandlers(replies=[r1])
            mss.listen()

            response = yield httprequest(method='GET', host='127.0.0.1', port=mss.port, request='/')
            self.assertEquals('HTTP/1.1 200 Okidokie\r\nContent-Length: 0\r\n\r\n', response)
            self.assertEquals(1, mss.nrOfRequests)
            self.assertEquals({1: 'GET / HTTP/1.1\r\n\r\n'}, mss.connectionHandler.returnValues)

            mss.close()
            raise StopIteration(response)

        result = asProcess(run())



    ## referenceHttpServer helpers ##
    def _dispatch(self, *args, **kwargs):
        def handle():
            try:
                yield self.handler(*args, **kwargs)
            except Exception:
                self.error = exc_info()
                raise
            finally:
                self.done = True
        return compose(handle())

    def _loopReactorUntilDone(self):
        self.done = False
        self.error = None
        with self.loopingReactor():
            while not self.done:
                sleep(0.01)

class MockSocketServer(object):
    """
    Meaning of life being:
     - Mock a HTTP/1.1 Server

    Must be used **inside** asProcess (__reactor__ callstack variable must be accessable).
    """

    def __init__(self):
        self.port = PortNumberGenerator.next()
        self.nrOfRequests = 0
        self.setHandlers()  # Default handler - any connection fails.

    def setHandlers(self, replies=None):
        replies = replies or []
        self.connectionHandler = _ExactExpectationHandler(server=self, replies=replies)

    def listen(self):
        # setblocking(0) would be nice, but no novelty in testing code here :-s
        # @@ TODO: fix todo's and imports, ...
        self._listenSok = socket()
        self._listenSok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self._listenSok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        self._listenSok.bind(('127.0.0.1', self.port))
        self._listenSok.listen(5)  # FIXME: 1, ..., 5, ..., n ??
        reactor().addReader(sok=self._listenSok, sink=self._accept)

    def close(self, exclude=None):
        if self._listenSok is None:
            return  # Allow multiple calls to close (2..n no-op).
        reactor().removeReader(sok=self._listenSok)
        self._listenSok.shutdown(SHUT_RDWR)
        self._listenSok.close()
        self._listenSok = None
        self.connectionHandler.close(exclude=exclude)

    def _accept(self):
        self.nrOfRequests += 1
        newConnection, remoteAddress = self._listenSok.accept()
        #newConnection.setblocking(0)
        newConnection.setsockopt(SOL_TCP, TCP_NODELAY, 1)
        #newConnection.setsockopt(SOL_TCP, TCP_CORK, 1)
        self.connectionHandler(sok=newConnection, remoteAddress=remoteAddress, connectionNr=self.nrOfRequests)


class _ExactExpectationHandler(object):
    def __init__(self, server, replies):
        self._server = server
        self._replies = replies

        self._replyIndex = -1
        self._busy = set()
        self.returnValues = {}

    def __call__(self, sok, remoteAddress, connectionNr):
        self._replyIndex += 1
        if self._replyIndex >= len(self._replies):
            return self.noConnectionHandler(sok=sok, remoteAddress=remoteAddress, connectionNr=connectionNr)

        return self._startAndTrackCompletion(gf=self._replies[self._replyIndex], sok=sok, remoteAddress=remoteAddress, connectionNr=connectionNr)

    def _startAndTrackCompletion(self, gf, sok, remoteAddress, connectionNr):
        @identify
        @compose
        def wrapper():
            # Arguments easily callstack-retrievable.
            __sok__ = sok
            __remoteAddress__ = remoteAddress
            __connectionNr__ = connectionNr

            this = __this__ = yield
            self._busy.add(this)
            reactor().addProcess(process=this.next)
            yield
            try:
                try:
                    g = compose(gf(sok=sok, remoteAddress=remoteAddress, connectionNr=connectionNr))
                except Exception, e:
                    raise AssertionError('Test error, MockSocketServer handler riased %s - should have resulted in a generator' % repr(e))

                try:
                    try:
                        while True:
                            sys.stdout.flush()
                            _response = g.next()
                            sys.stdout.flush()
                            if _response is not Yield and callable(_response):
                                _response(reactor(), this.next)
                                yield
                                _response.resumeProcess()
                            yield
                    except StopIteration, e:
                        retval = e.args[0] if e.args else None
                except Exception, e:
                    print_exc()  # HCK
                    retval = e
                    # or: retval = exc_info() for TB stuff?
            except (AssertionError, KeyboardInterrupt, SystemExit):
                self._server.close(exclude=this)  # cleans up server and self.
                raise
            finally:
                reactor().removeProcess(process=this.next)
                self._busy.remove(this)

            self.returnValues[connectionNr] = retval
            yield  # Wait for GC

        wrapper()

    def close(self, exclude=None):
        for handler in self._busy:
            if handler == exclude:
                continue  # If set, excluded itself is initiating the close because of a fatal error.
            handler.throw(AbortException, AbortException('Handler not completed on time'), None)

    def noConnectionHandler(self, sok, remoteAddress, connectionNr):
        sok.shutdown(SHUT_RDWR); sok.close()
        self._server.close()  # cleans up server and self.
        raise AssertionError('Unexpected Connection #{0} from: {1}:{2}!'.format(connectionNr, *remoteAddress))


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
            if not forSeconds:
                raise AssertionError('Timeout reached.')

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
    """

    startTime = time()
    timeoutRelative = lambda: max(float(timeout) - (time() - startTime), 0)
    remaining = data

    while remaining:
        remaining = yield _writeOnce(remaining, timeout=timeoutRelative())


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


def clientget(host, port, path):
    client = socket()
    client.connect((host,  port))
    client.send('GET %s HTTP/1.1\r\n\r\n' % path)
    return client

fileDict = {
    '__file__': clientget.func_code.co_filename,
    'suspend.py': Suspend.__call__.func_code.co_filename,
    'httprequest.py': _requestLine.func_code.co_filename,
}

def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

