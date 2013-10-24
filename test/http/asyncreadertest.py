# -*- coding: utf-8 -*-
## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from __future__ import with_statement
import sys
from sys import exc_info, version_info
from time import sleep
from StringIO import StringIO
from traceback import format_exception
from socket import socket, gaierror as SocketGaiError
from random import randint
from re import sub
from httpreadertest import server as testserver
from weightless.http import HttpServer, httpget, httppost, httpspost, httpsget
from weightless.io import Reactor, Suspend
from weightless.core import compose

from weightless.http._httprequest import _requestLine
from weightless.http import _httprequest as httpRequestModule

from weightlesstestcase import WeightlessTestCase, StreamingData
from seecr.test.io import stderr_replaced

PYVERSION = '%s.%s' % version_info[:2]


class AsyncReaderTest(WeightlessTestCase):
    def setUp(self):
        WeightlessTestCase.setUp(self)
        self.reactor = Reactor()
        self.port = randint(2**10, 2**16)
        self.httpserver = HttpServer(self.reactor, self.port, self._dispatch)
        self.httpserver.listen()

    def tearDown(self):
        self.httpserver.shutdown()
        self.reactor.shutdown()
        WeightlessTestCase.tearDown(self)

    def testHttpRequest(self):
        self.assertEquals('GET / HTTP/1.0\r\n', _requestLine('GET', '/'))
        self.assertEquals('POST / HTTP/1.0\r\n', _requestLine('POST', '/'))

    def testPassRequestThruToBackOfficeServer(self):
        backofficeport = self.port + 1
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request)
            yield response
        self.handler = passthruhandler
        expectedrequest = "GET /depot?arg=1&arg=2 HTTP/1.0\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        client = clientget('localhost', self.port, '/depot?arg=1&arg=2')
        self._loopReactorUntilDone()
        response = client.recv(99)
        self.assertEquals('hello!', response)

    @stderr_replaced
    def testConnectFails(self):
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
  File "%(httprequest.py)s", line 78, in _httpRequest
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
  File "%(httprequest.py)s", line 78, in _httpRequest
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
        self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(''.join(format_exception(*self.error))))

        target = ('localhost', 87, '/') # invalid port
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(IOError, self.error[0])

        target = ('UEYR^$*FD(#>NDJ.khfd9.(*njnd', 9876, '/') # invalid host
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(SocketGaiError, self.error[0])

        target = ('127.0.0.255', 9876, '/')
        clientget('localhost', self.port, '/')
        self._loopReactorUntilDone()
        self.assertEquals(IOError, self.error[0])
        self.assertEquals('111', str(self.error[1]))

    def testTracebackPreservedAcrossSuspend(self):
        backofficeport = self.port + 1
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

            clientget('localhost', self.port, '/')
            with stderr_replaced():
                self._loopReactorUntilDone()

            expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 0, in handle
      yield self.handler(*args, **kwargs)
  File "%(__file__)s", line 192, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 129, in _httpRequest
    result = s.getResult()
  File "%(httprequest.py)s", line 83, in _do
    yield _sendHttpHeaders(sok, method, request, headers)
  File "%(httprequest.py)s", line 121, in _sendHttpHeaders
    data = _requestLine(method, request)
  File "%(__file__)s", line 198, in requestLine
    raise RuntimeError("Boom!")
RuntimeError: Boom!""" % fileDict)
            resultingTraceback = ''.join(format_exception(*self.error))
            self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(resultingTraceback))

        finally:
            httpRequestModule._requestLine = originalRequestLine

    def testHttpPost(self):
        post_request = []
        port = self.port + 1
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
        post_request = []
        port = self.port + 1
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
        post_request = []
        port = self.port + 1
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

    def testHttpGet(self):
        get_request = []
        port = self.port + 1
        self.referenceHttpServer(port, get_request)

        responses = []
        def gethandler(*args, **kwargs):
            response = 'no response yet'
            try:
                response = yield httpget('localhost', port, '/path',
                        headers={'Content-Type': 'text/plain', 'Content-Length': 0}
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

    def testHttpGetWithReallyLargeHeaders(self):
        get_request = []
        port = self.port + 1
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

    def testHttpAndHttpsGetStreaming(self):
        for useSsl in [False, True]:
            get_request = []
            port = self.port + 1 + useSsl
            streamingData = StreamingData(data=[c for c in "STREAMING GET RESPONSE"])
            self.referenceHttpServer(port, get_request, ssl=useSsl, streamingData=streamingData)

            dataHandled = []
            def handleDataFragment(data):
                dataHandled.append(data)
                if '\r\n\r\n' in ''.join(dataHandled):
                    streamingData.doNext()

            responses = []
            def gethandler(*args, **kwargs):
                f = httpsget if useSsl else httpget
                response = 'no response yet'
                try:
                    response = yield f('localhost', port, '/path',
                        headers={'Accept': 'text/plain'},
                        processPartialResponse=handleDataFragment,
                    )
                finally:
                    responses.append(response)
            self.handler = gethandler
            clientget('localhost', self.port, '/')
            self._loopReactorUntilDone()

            self.assertEquals([None], responses)
            self.assertTrue("STREAMING GET RESPONSE" in ''.join(dataHandled), dataHandled)
            self.assertTrue(len(dataHandled) > len("STREAMING GET RESPONSE"), dataHandled)
            self.assertEquals('GET', get_request[0]['command'])
            self.assertEquals('/path', get_request[0]['path'])
            headers = get_request[0]['headers'].headers
            self.assertEquals(['Accept: text/plain\r\n'], headers)

    def testHttpsGet(self):
        get_request = []
        port = self.port + 1
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

