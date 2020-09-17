# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2016, 2018-2019 Seecr (Seek You Too B.V.) http://seecr.nl
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


from socket import gaierror as SocketGaiError
from sys import exc_info, version_info
from time import sleep
from traceback import format_exception

from weightless.core import compose
from weightless.http import HttpServer, httprequest, httpget, httppost, httpspost, httpsget, HttpRequest
from weightless.io import Suspend, TimeoutException, TooBigResponseException

from weightless.http._httprequest import _requestLine
from weightless.http import _httprequest as httpRequestModule

from seecr.test.io import stderr_replaced, stdout_replaced
from seecr.test.portnumbergenerator import PortNumberGenerator
from weightlesstestcase import WeightlessTestCase, StreamingData
from .httpreadertest import server as testserver
from testutils import clientget
from seecr.test.utils import ignoreLineNumbers


PYVERSION = '%s.%s' % version_info[:2]

class AsyncReaderTest(WeightlessTestCase):
    def setUp(self):
        WeightlessTestCase.setUp(self)
        self.httpserver = HttpServer(self.reactor, self.port, self._dispatch)
        self.httpserver.listen()

    def tearDown(self):
        self.httpserver.shutdown()
        WeightlessTestCase.tearDown(self)

    def testRequestLine(self):
        self.assertEqual('GET / HTTP/1.0\r\n', _requestLine('GET', '/'))
        self.assertEqual('POST / HTTP/1.0\r\n', _requestLine('POST', '/'))

    def testEmptyRequestConvenientlyTranslatedToSlash(self):
        self.assertEqual('GET / HTTP/1.0\r\n', _requestLine('GET', ''))
        self.assertEqual('POST / HTTP/1.0\r\n', _requestLine('POST', ''))

    def testPassRequestThruToBackOfficeServer(self):
        backofficeport = PortNumberGenerator.next()
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request.decode())
            yield response
        self.handler = passthruhandler
        expectedrequest = b"GET /depot?arg=1&arg=2 HTTP/1.0\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        with clientget('localhost', self.port, '/depot?arg=1&arg=2') as client:
            self._loopReactorUntilDone()
            response = client.recv(99)
            self.assertEqual(b'hello!', response)

    def testPassRequestThruToBackOfficeServerWithHttpRequest(self):
        backofficeport = PortNumberGenerator.next()
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield HttpRequest().httprequest(host='localhost', port=backofficeport, request=request.decode())
            yield response
        self.handler = passthruhandler
        expectedrequest = b"GET /depot?arg=1&arg=2 HTTP/1.0\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        with clientget('localhost', self.port, '/depot?arg=1&arg=2') as client:
            self._loopReactorUntilDone()
            response = client.recv(99)
            self.assertEqual(b'hello!', response)

    @stderr_replaced
    def testConnectFails(self):
        def failingserver(*args, **kwarg):
            response = yield httpget(*target)

        self.handler = failingserver

        with clientget('localhost', self.port, '/') as client:
            target = ('localhost', 'port', '/') # non-numeric port
            self._loopReactorUntilDone()

            self.assertEqual(TypeError, self.error[0])
            stacktrace = ignoreLineNumbers(''.join(format_exception(*self.error)))
            self.assertTrue("TypeError: an integer is required (got type str)" in stacktrace, stacktrace)

        target = ('localhost', 87, '/') # invalid port
        with clientget('localhost', self.port, '/') as client:
            self._loopReactorUntilDone()
            self.assertEqual(IOError, self.error[0])

        target = ('UEYR^$*FD(#>NDJ.khfd9.(*njnd', PortNumberGenerator.next(), '/') # invalid host
        with clientget('localhost', self.port, '/') as client:
            self._loopReactorUntilDone()
            self.assertEqual(SocketGaiError, self.error[0])

        target = ('127.0.0.1', PortNumberGenerator.next(), '/')  # No-one listens
        with clientget('localhost', self.port, '/') as client:
            self._loopReactorUntilDone()
            self.assertEqual(IOError, self.error[0])
            self.assertEqual('111', str(self.error[1]))


    @stdout_replaced
    def testTracebackPreservedAcrossSuspend(self):
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
            originalRequestLine = httpRequestModule._requestLine
            httpRequestModule._requestLine = requestLine

            with clientget('localhost', self.port, '/') as client:
                with stderr_replaced():
                    self._loopReactorUntilDone()

                stacktrace = ignoreLineNumbers(''.join(format_exception(*self.error)))
                methodTrace = ([each.split("\n")[0].rsplit(' ',1)[-1] for each in format_exception(*self.error) if '  File "' in each])
                self.assertEqual(
                    ['handle', 'failingserver', 'httprequest', 'getResult', '_do', '_sendHttpHeaders', 'requestLine'], 
                    methodTrace)
                self.assertTrue(stacktrace.strip().endswith("RuntimeError: Boom!"), stacktrace)

        finally:
            httpRequestModule._requestLine = originalRequestLine

    def testHttpPost(self):
        post_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, post_request):
            body = "BÖDY" * 20000
            responses = []
            def posthandler(*args, **kwargs):
                response = yield httppost('localhost', port, '/path', body,
                        headers={'Content-Type': 'text/plain'}
                )
                yield response
                responses.append(response)
            self.handler = posthandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"POST RESPONSE" in responses[0], responses[0])
            self.assertEqual('POST', post_request[0]['command'])
            self.assertEqual('/path', post_request[0]['path'])
            headers = post_request[0]['headers']
            for key, value in [('Content-Length', '100000'), ('Content-Type', 'text/plain')]:
                self.assertEqual(value, headers[key])
            self.assertEqual(body.encode(), post_request[0]['body'])

    def testHttpPostWithoutHeaders(self):
        post_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, post_request):
            body = "BÖDY" * 20000
            responses = []
            def posthandler(*args, **kwargs):
                response = yield httppost('localhost', port, '/path', body)
                yield response
                responses.append(response)
            self.handler = posthandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"POST RESPONSE" in responses[0], responses[0])
            self.assertEqual('POST', post_request[0]['command'])
            self.assertEqual('/path', post_request[0]['path'])
            headers = post_request[0]['headers']
            self.assertEqual("100000", headers['Content-Length'])
            self.assertEqual(body.encode(), post_request[0]['body'])

    def testHttpsPost(self):
        post_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, post_request, ssl=True):
            body = "BÖDY" * 20000
            responses = []
            def posthandler(*args, **kwargs):
                response = yield httpspost('localhost', port, '/path', body,
                        headers={'Content-Type': 'text/plain'}
                )
                yield response
                responses.append(response)
            self.handler = posthandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"POST RESPONSE" in responses[0], responses[0])
            self.assertEqual('POST', post_request[0]['command'])
            self.assertEqual('/path', post_request[0]['path'])
            headers = post_request[0]['headers']
            for key, value in [('Content-Length', '100000'), ('Content-Type', 'text/plain')]:
                self.assertEqual(value, headers[key])
            self.assertEqual(body.encode(), post_request[0]['body'])

    @stderr_replaced
    def testHttpsPostOnIncorrectPort(self):
        responses = []
        def posthandler(*args, **kwargs):
            response = yield httpspost('localhost', PortNumberGenerator.next(), '/path', "body",
                    headers={'Content-Type': 'text/plain'}
            )
            yield response
            responses.append(response)
        self.handler = posthandler
        with clientget('localhost', self.port, '/') as client:
            self._loopReactorUntilDone()

        self.assertTrue(self.error[0] is IOError)
        self.assertEqual("111", str(self.error[1]))

    def testHttpGet(self):
        get_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, get_request):
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
                yield 'HTTP/1.0 200 OK\r\n\r\n'
            self.handler = gethandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"GET RESPONSE" in responses[0], responses[0])
            self.assertEqual('GET', get_request[0]['command'])
            self.assertEqual('/path', get_request[0]['path'])
            headers = get_request[0]['headers']
            for key, value in [('Content-Length', '0'), ('Content-Type', 'text/plain')]:
                self.assertEqual(value, headers[key])

    def testHttpRequest(self):
        get_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, get_request):
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
                yield 'HTTP/1.0 200 OK\r\n\r\n'
            self.handler = gethandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"Message: Unsupported method ('MYMETHOD')" in responses[0], responses[0])

    def testHttpRequestWithTimeout(self):
        # And thus too http(s)get/post/... and friends.
        get_request = []
        port = PortNumberGenerator.next()
        def slowData():
            for i in range(5):
                yield str(i)
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
                except TimeoutException as e:
                    responses.append(e)
                finally:
                    assert responses, 'Either a timeout or response should have occurred.'

                yield 'HTTP/1.0 200 OK\r\n\r\n'
            return gethandler

        # Not timing out
        with self.referenceHttpServer(port=port, request=get_request, streamingData=slowData()):
            self.handler = handlerFactory(timeout=0.5)
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()
            self.assertTrue(len(responses) >= 1)
            responseText = b''.join(responses)
            self.assertTrue(responseText.startswith(b'HTTP/1.0 200 OK'), responseText)
            self.assertTrue(b'01234' in responseText, responseText)
            self.assertEqual(1, len(get_request))

        # Timing out
        del get_request[:]
        del responses[:]
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port=port, request=get_request, streamingData=slowData()):
            self.handler = handlerFactory(timeout=0.02)
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()
            self.assertEqual([TimeoutException], [type(r) for r in responses])
            self.assertEqual(1, len(get_request))
            self.assertEqual('GET', get_request[0]['command'])

    def testHttpGetWithReallyLargeHeaders(self):
        get_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, get_request):
            responses = []
            headersOrig = {'Accept': 'text/plain'}
            headersOrig.update([
                ('X-Really-Largely-Large-{}'.format(i), 'aLargelyLargeValue')
                for i in range(98)
            ])
            def gethandler(*args, **kwargs):
                response = 'no response yet'
                try:
                    response = yield httpget('localhost', port, '/path', headers=headersOrig)
                finally:
                    responses.append(response)

                yield 'HTTP/1.0 200 OK\r\n\r\n'
            self.handler = gethandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()
            headers = dict(get_request[0]['headers'])
            self.assertEqual(len(headersOrig), len(headers))
            self.assertEqual(headersOrig, headers)

            self.assertTrue(b"GET RESPONSE" in responses[0], responses[0])
            self.assertEqual('GET', get_request[0]['command'])
            self.assertEqual('/path', get_request[0]['path'])

    def testHttpGetWithMaxSize(self):
        get_requests = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, get_requests, streamingData="response"*1024):
            responses = []
            def gethandler(*args, **kwargs):
                try:
                    response = yield httpget('localhost', port, '/path', maxResponseSize=1024)
                    responses.append(response)
                except Exception as e:
                    responses.append(e)
            self.handler = gethandler
            with clientget('localhost', self.port, '/') as client:
                with stderr_replaced():
                    with stdout_replaced():
                        self._loopReactorUntilDone()

            self.assertEqual([TooBigResponseException], [type(r) for r in responses])
            self.assertEqual(1024, responses[0].args[0])
            self.assertEqual(1, len(get_requests))
            self.assertEqual('GET', get_requests[0]['command'])

    def testHttpAndHttpsGetStreaming(self):
        for useSsl in [False, True]:
            get_request = []
            port = PortNumberGenerator.next()
            streamingData = StreamingData(data=[c for c in "STREAMING GET RESPONSE"])
            with self.referenceHttpServer(port, get_request, ssl=useSsl, streamingData=streamingData):
                dataHandled = []
                def handleDataFragment(data):
                    dataHandled.append(data)
                    if b'\r\n\r\n' in b''.join(dataHandled):
                        streamingData.doNext()

                responses = []
                def gethandler(*args, **kwargs):
                    f = httpsget if useSsl else httpget
                    response = 'no response yet'
                    try:
                        response = yield f('localhost', port, '/path',
                            headers={'Accept': 'text/plain'},
                            handlePartialResponse=handleDataFragment,
                        )
                    finally:
                        responses.append(response)
                    yield 'HTTP/1.0 200 OK\r\n\r\n'
                self.handler = gethandler
                with clientget('localhost', self.port, '/') as client:
                    self._loopReactorUntilDone()

                self.assertEqual([None], responses)
                self.assertTrue(b"STREAMING GET RESPONSE" in b''.join(dataHandled), dataHandled)
                self.assertTrue(len(dataHandled) > len("STREAMING GET RESPONSE"), dataHandled)
                self.assertEqual('GET', get_request[0]['command'])
                self.assertEqual('/path', get_request[0]['path'])
                headers = get_request[0]['headers']
                self.assertEqual('text/plain', headers['Accept'])

    def testHttpsGet(self):
        get_request = []
        port = PortNumberGenerator.next()
        with self.referenceHttpServer(port, get_request, ssl=True):
            responses = []
            def gethandler(*args, **kwargs):
                response = yield httpsget('localhost', port, '/path',
                        headers={'Content-Type': 'text/plain', 'Content-Length': 0}
                )
                yield response
                responses.append(response)
            self.handler = gethandler
            with clientget('localhost', self.port, '/') as client:
                self._loopReactorUntilDone()

            self.assertTrue(b"GET RESPONSE" in responses[0], responses[0])
            self.assertEqual('GET', get_request[0]['command'])
            self.assertEqual('/path', get_request[0]['path'])
            headers = get_request[0]['headers']
            for key, value in [('Content-Length', '0'), ('Content-Type', 'text/plain')]:
                self.assertEqual(value, headers[key])

    def testHttpGetViaProxy(self):
        get_request = []
        port = PortNumberGenerator.next()
        proxyPort = PortNumberGenerator.next()
        with self.proxyServer(proxyPort, get_request):
            with self.referenceHttpServer(port, get_request):
                responses = []
                def gethandler(*args, **kwargs):
                    response = yield httpget('localhost', port, '/path',
                            headers={'Content-Type': 'text/plain', 'Content-Length': 0},
                            proxyServer="http://localhost:%s" % proxyPort
                    )
                    yield response
                    responses.append(response)
                self.handler = gethandler
                with clientget('localhost', self.port, '/') as client:
                    self._loopReactorUntilDone()

                self.assertTrue(b"GET RESPONSE" in responses[0], responses[0])
                self.assertEqual('CONNECT', get_request[0]['command'])
                self.assertEqual('localhost:%s' % port, get_request[0]['path'])
                self.assertEqual('GET', get_request[1]['command'])
                self.assertEqual('/path', get_request[1]['path'])

    def _dispatch(self, *args, **kwargs):
        @compose
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
