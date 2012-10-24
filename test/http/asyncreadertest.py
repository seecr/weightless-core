# -*- coding: utf-8 -*-
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2010-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from __future__ import with_statement
import sys
from sys import exc_info
from StringIO import StringIO
from traceback import format_exception
from time import sleep
from socket import socket, gaierror as SocketGaiError
from random import randint
from re import sub
from seecr.test import CallTrace
from httpreadertest import server as testserver
from weightless.http import HttpServer, httpget, httppost
from weightless.io import Reactor, Suspend
from weightless.core import compose
 
from weightless.http._httprequest import _httpRequest
from weightless.http import _httprequest as httpRequestModule

from weightlesstestcase import WeightlessTestCase

def clientget(host, port, path):
    client = socket()
    client.connect((host,  port))
    client.send('GET %s HTTP/1.1\r\n\r\n' % path)
    return client

fileDict = {
    '__file__': clientget.func_code.co_filename,
    'suspend.py': Suspend.__call__.func_code.co_filename,
    'httprequest.py': httpget.func_code.co_filename,
}
 
class AsyncReaderTest(WeightlessTestCase):

    def dispatch(self, *args, **kwargs):
        return compose(self.handler(*args, **kwargs))

    def setUp(self):
        WeightlessTestCase.setUp(self)
        self.reactor = Reactor()
        self.port = randint(2**10, 2**16)
        self.httpserver = HttpServer(self.reactor, self.port, self.dispatch)
        self.httpserver.listen()

    def tearDown(self):
        self.httpserver.shutdown()
        self.reactor.shutdown()
        WeightlessTestCase.tearDown(self)

    def testHttpRequest(self):
        self.assertEquals('GET / HTTP/1.0\r\n', _httpRequest('GET', '/'))
        self.assertEquals('POST / HTTP/1.0\r\n', _httpRequest('POST', '/'))

    def testPassRequestThruToBackOfficeServer(self):
        done = [False]
        backofficeport = self.port + 1
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request)
            yield response
            done[0] = True
        self.handler = passthruhandler
        expectedrequest = "GET /depot?arg=1&arg=2 HTTP/1.0\r\n\r\n"
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, expectedrequest)
        client = clientget('localhost', self.port, '/depot?arg=1&arg=2')
        while not done[0]:
            self.reactor.step()
        response = client.recv(99)
        self.assertEquals('hello!', response)

    def testConnectFails(self):
        exceptions = []
        def failingserver(*args, **kwarg):
            try:
                response = yield httpget(*target)
            except Exception, e:
                exceptions.append(exc_info())
        self.handler = failingserver

        clientget('localhost', self.port, '/')
        target = ('localhost', 'port', '/') # non-numeric port
        try:
            with self.stderr_replaced():
                with self.loopingReactor():
                    while not exceptions:
                        pass
        except Exception, e:
            pass

        expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 85, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 78, in httpget
    result = s.getResult()
  File "%(suspend.py)s", line 34, in __call__
    self._doNext(self)
  File "%(httprequest.py)s", line 35, in _do
    sok.connect((host, port))
  File "<string>", line 1, in connect
TypeError: an integer is required
       """ % fileDict)
        self.assertEquals(TypeError, exceptions[0][0])
        self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(''.join(format_exception(*exceptions[0]))))

        target = ('localhost', 87, '/') # invalid port
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            orgout = sys.stderr
            sys.stderr = StringIO()
            try:
                self.reactor.step()
            finally:
                sys.stderr = orgout
        self.assertEquals(IOError, exceptions[0][0])

        target = ('UEYR^$*FD(#>NDJ.khfd9.(*njnd', 9876, '/') # invalid host
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            orgout = sys.stderr
            sys.stderr = StringIO()
            try:
                self.reactor.step()
            finally:
                sys.stderr = orgout
        self.assertEquals(SocketGaiError, exceptions[0][0])

        target = ('127.0.0.255', 9876, '/')
        clientget('localhost', self.port, '/')
        print "E"
        exceptions = []
        while not exceptions:
            orgout = sys.stderr
            #sys.stderr = StringIO()
            try:
                print "stap "
                self.reactor.step()
            finally:
                sys.stderr = orgout
        self.assertEquals(IOError, exceptions[0][0])
        self.assertEquals('111', str(exceptions[0][1]))

    def testTracebackPreservedAcrossSuspend(self):
        backofficeport = self.port + 1
        expectedrequest = ''
        testserver(backofficeport, [], expectedrequest)
        target = ('localhost', backofficeport, '/')

        exceptions = []
        def failingserver(*args, **kwarg):
            try:
                response = yield httpget(*target)
            except Exception, e:
                exceptions.append(exc_info())
        self.handler = failingserver

        def httpRequest(self, *args, **kwargs):
            raise RuntimeError("Boom!")

        try:
            originalHttpRequest = httpRequestModule._httpRequest
            httpRequestModule._httpRequest = httpRequest

            clientget('localhost', self.port, '/')
            while not exceptions:
                self.reactor.step()

            expectedTraceback = ignoreLineNumbers("""Traceback (most recent call last):
  File "%(__file__)s", line 144, in failingserver
    response = yield httpget(*target)
  File "%(httprequest.py)s", line 80, in httpget
    result = s.getResult()
  File "%(httprequest.py)s", line 51, in _do
    _sendHttpHeaders(sok, method, request, headers)
  File "%(httprequest.py)s", line 82, in _sendHttpHeaders
    sok.send(_httpRequest(method, request))
  File "%(__file__)s", line 150, in httpRequest
    raise RuntimeError("Boom!")
RuntimeError: Boom!""" % fileDict)
            resultingTraceback = ''.join(format_exception(*exceptions[0]))
            self.assertEqualsWS(expectedTraceback, ignoreLineNumbers(resultingTraceback))

        finally:
            httpRequestModule._httpRequest = originalHttpRequest

    def testPost(self):
        post_request = []
        port = self.port + 1
        self.referenceHttpServer(port, post_request)
        body = u"BÖDY" * 20000
        done = []
        def posthandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httppost('localhost', port, '/path', body, 
                    headers={'Content-Type': 'text/plain'}
            )
            yield response
            done.append(response)
        self.handler = posthandler
        clientget('localhost', self.port, '/')
        with self.loopingReactor():
            while not done:
                pass

        self.assertTrue("POST RESPONSE" in done[0], done[0])
        self.assertEquals('POST', post_request[0]['command'])
        self.assertEquals('/path', post_request[0]['path'])
        headers = post_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 100000\r\n', 'Content-Type: text/plain\r\n'], headers)
        self.assertEquals(body, post_request[0]['body'])

    def testGet(self):
        get_request = []
        port = self.port + 1
        self.referenceHttpServer(port, get_request)

        done = []
        def gethandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', port, '/path',  
                    headers={'Content-Type': 'text/plain', 'Content-Length': 0}
            )
            yield response
            done.append(response)
        self.handler = gethandler
        clientget('localhost', self.port, '/')
        with self.loopingReactor():
            while not done:
                pass

        self.assertTrue("GET RESPONSE" in done[0], done[0])
        self.assertEquals('GET', get_request[0]['command'])
        self.assertEquals('/path', get_request[0]['path'])
        headers = get_request[0]['headers'].headers
        self.assertEquals(['Content-Length: 0\r\n', 'Content-Type: text/plain\r\n'], headers)


def ignoreLineNumbers(s):
    return sub("line \d+,", "line [#],", s)

