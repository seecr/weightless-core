# -*- coding: utf-8 -*-
## begin license ##
# 
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io 
# 
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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

from weightlesstestcase import WeightlessTestCase, MATCHALL
from random import randint
from socket import socket, error as SocketError
from select import select
from weightless.io import Reactor
from time import sleep
from seecr.test import CallTrace
from os.path import join, abspath, dirname
from StringIO import StringIO
from sys import getdefaultencoding

from weightless.http import HttpServer, _httpserver
from weightless.core import Yield

def inmydir(p):
    return join(dirname(abspath(__file__)), p)

class HttpServerTest(WeightlessTestCase):

    def sendRequestAndReceiveResponse(self, request, recvSize=4096):
        self.responseCalled = False
        def response(**kwargs):
            yield 'The Response'
            self.responseCalled = True
        server = HttpServer(self.reactor, self.port, response, recvSize=recvSize)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send(request)
        with self.stdout_replaced():
            while not self.responseCalled:
                self.reactor.step()
        server.shutdown()
        r = sok.recv(4096)
        sok.close()
        return r

    def testConnect(self):
        self.req = False
        def onRequest(**kwargs):
            self.req = True
            yield 'nosens'
        reactor = Reactor()
        server = HttpServer(reactor, self.port, onRequest)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET / HTTP/1.0\r\n\r\n')
        reactor.step() # connect/accept
        reactor.step() # read GET request
        reactor.step() # call onRequest for response data
        self.assertEquals(True, self.req)

    def testSendHeader(self):
        self.kwargs = None
        def response(**kwargs):
            self.kwargs = kwargs
            yield 'nosense'
        reactor = Reactor()
        server = HttpServer(reactor, self.port, response)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        while not self.kwargs:
            reactor.step()
        self.assertEquals({'Body': '', 'RequestURI': '/path/here', 'HTTPVersion': '1.0', 'Method': 'GET', 'Headers': {'Connection': 'close', 'Ape-Nut': 'Mies'}, 'Client': ('127.0.0.1', MATCHALL)}, self.kwargs)

    def testGetResponse(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEquals('The Response', response)

    def testCloseConnection(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEquals('The Response', response)
        self.assertEquals({}, self.reactor._readers)
        self.assertEquals({}, self.reactor._writers)

    def testSmallFragments(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n', recvSize=3)
        self.assertEquals('The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):
        def response(**kwargs):
            yield 'some text that is longer than '
            yield 'the lenght of fragments sent'
        reactor = Reactor()
        server = HttpServer(reactor, self.port, response, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        while not reactor._writers:
            reactor.step()
        serverSok, handler = reactor._writers.items()[0]
        originalSend = serverSok.send
        def sendOnlyManagesToActuallySendThreeBytesPerSendCall(data, *options):
            originalSend(data[:3], *options)
            return 3
        serverSok.send = sendOnlyManagesToActuallySendThreeBytesPerSendCall
        for i in range(21):
            reactor.step()
        fragment = sok.recv(4096)
        self.assertEquals('some text that is longer than the lenght of fragments sent', fragment)

    def testHttpServerEncodesUnicode(self):
        unicodeString = u'some t\xe9xt' 
        oneStringLength = len(unicodeString.encode(getdefaultencoding()))
        self.assertTrue(len(unicodeString) != oneStringLength)
        def response(**kwargs):
            yield unicodeString * 6000
        reactor = Reactor()
        server = HttpServer(reactor, self.port, response, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        while not reactor._writers:
            reactor.step()
        reactor.step()
        fragment = sok.recv(100000) # will read about 49152 chars
        reactor.step()
        fragment += sok.recv(100000)
        self.assertEquals(oneStringLength * 6000, len(fragment))
        self.assertTrue("some t\xc3\xa9xt" in fragment, fragment)

    def testInvalidRequestStartsOnlyOneTimer(self):
        _httpserver.RECVSIZE = 3
        reactor = Reactor()
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
        self.assertEquals('HTTP/1.0 400 Bad Request\r\n\r\n', response)
        self.assertEquals(1, len(timers))

    def testValidRequestResetsTimer(self):
        reactor = Reactor()
        server = HttpServer(reactor, self.port, lambda **kwargs: ('a' for a in range(3)), timeout=0.01, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET / HTTP/1.0\r\n\r\n')
        sleep(0.02)
        for i in range(11):
            reactor.step()
        response = sok.recv(4096)
        self.assertEquals('aaa', response)

    def testPostMethodReadsBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler, timeout=0.01)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\nbodydata')

        while not self.requestData:
            reactor.step()
        self.assertEquals(dict, type(self.requestData))
        self.assertTrue('Headers' in self.requestData)
        headers = self.requestData['Headers']
        self.assertEquals('POST', self.requestData['Method'])
        self.assertEquals('application/x-www-form-urlencoded', headers['Content-Type'])
        self.assertEquals(8, int(headers['Content-Length']))

        self.assertTrue('Body' in self.requestData)
        self.assertEquals('bodydata', self.requestData['Body'])

    def testPostMethodTimesOutOnBadBody(self):
        self.requestData = None
        def handler(**kwargs):
            self.requestData = kwargs

        done = []
        def onDone():
            fromServer = sok.recv(1024)
            self.assertTrue('HTTP/1.0 400 Bad Request' in fromServer)
            done.append(True)

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler, timeout=0.01)
        server.listen()
        reactor.addTimer(0.02, onDone)
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\n')

        while not done:
            reactor.step()


    def testReadChunkedPost(self):
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler, timeout=0.01, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nabcde\r\n5\r\nfghij\r\n0\r\n')

        reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        while self.requestData.get('Body', None) != 'abcdefghij':
            reactor.step()

    def testPostMultipartForm(self):
        httpRequest = open(inmydir('data/multipart-data-01')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send(httpRequest)

        reactor.addTimer(2, lambda: self.fail("Test Stuck"))
        while self.requestData.get('Form', None) == None:
            reactor.step()
        form = self.requestData['Form']
        self.assertEquals(4, len(form))
        self.assertEquals(['SOME ID'], form['id'])

    def testWindowsPostMultipartForm(self):
        httpRequest = open(inmydir('data/multipart-data-02')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send(httpRequest)

        reactor.addTimer(2, lambda: self.fail("Test Stuck"))
        while self.requestData.get('Form', None) == None:
            reactor.step()
        form = self.requestData['Form']
        self.assertEquals(4, len(form))
        self.assertEquals(['SOME ID'], form['id'])
        self.assertEquals(1, len(form['somename']))
        filename, mimetype, data = form['somename'][0]
        self.assertEquals('Bank Gothic Medium BT.ttf', filename)
        self.assertEquals('application/octet-stream', mimetype)

    def testTextFileSeenAsFile(self):
        httpRequest = open(inmydir('data/multipart-data-03')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send(httpRequest)

        reactor.addTimer(2, lambda: self.fail("Test Stuck"))
        while self.requestData.get('Form', None) == None:
            reactor.step()
        form = self.requestData['Form']
        self.assertEquals(4, len(form))
        self.assertEquals(['SOME ID'], form['id'])
        self.assertEquals(1, len(form['somename']))
        filename, mimetype, data = form['somename'][0]
        self.assertEquals('hello.bas', filename)
        self.assertEquals('text/plain', mimetype)

    def testReadMultipartFormEndBoundary(self):
        httpRequest = open(inmydir('data/multipart-data-04')).read()
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send(httpRequest)

        reactor.addTimer(2, lambda: self.fail("Test Stuck"))
        while self.requestData.get('Form', None) == None:
            reactor.step()
        form = self.requestData['Form']
        self.assertEquals(1, len(form))
        self.assertEquals(3521*'X', form['id'][0])

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

        self.assertEquals('FAIL', sock.recv(1024))
        self.assertEquals([503], codes)

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

        self.assertEquals('OK', sock.recv(1024))

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

        self.assertEquals('HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>', sock.recv(1024))
        server.shutdown()

    def testYieldInHttpServer(self):
        bucket = []
        def handler(RequestURI, **kwargs):
            yield 'A'
            while 'continue' not in bucket:
                yield Yield
            yield 'B'

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self.port))
        sok.send('GET /path/here HTTP/1.0\r\n\r\n')
        for i in xrange(500):
            reactor.step()
        self.assertEquals('A', sok.recv(100))
        bucket.append('continue')
        reactor.step()
        self.assertEquals('B', sok.recv(100))

    def testYieldPossibleUseCase(self):
        bucket = []
        ready = []
        useYield = []
        workDone = []
        def handler(RequestURI, **kwargs):
            name = 'work' if 'aLotOfWork' in RequestURI else 'lazy'
            bucket.append('%s_A' % name)
            yield 'A'
            if '/aLotOfWork' in RequestURI:
                bucket.append('%s_part_1' % name)
                if True in useYield:
                    while not workDone:
                        yield Yield
                bucket.append('%s_part_2' % name)
            bucket.append('%s_B' % name)
            ready.append('yes')
            yield 'B'

        reactor = Reactor()
        server = HttpServer(reactor, self.port, handler)
        server.listen()

        def loopWithYield(use):
            del ready[:]
            del bucket[:]
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
            workDone.append(True)
            while ready != ['yes', 'yes']:
                reactor.step()
            return bucket

        self.assertEquals(['work_A', 'work_part_1',
            'lazy_A', 'lazy_B',
            'work_part_2', 'work_B'], loopWithYield(True))
        self.assertEquals([
            'work_A', 'work_part_1', 'work_part_2', 'work_B',
            'lazy_A', 'lazy_B'], loopWithYield(False))

