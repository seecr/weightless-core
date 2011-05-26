# -*- coding: utf-8 -*-
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
from unittest import TestCase
from random import randint
from socket import socket, error as SocketError
from select import select
from weightless.io import Reactor
from time import sleep
from calltrace import CallTrace
from basetestcase import MATCHALL
from os.path import join, abspath, dirname
from StringIO import StringIO
from sys import getdefaultencoding

from weightless.http import HttpServer, _httpserver

def inmydir(p):
    return join(dirname(abspath(__file__)), p)

class HttpServerTest(TestCase):

    def setUp(self):
        self.reactor = Reactor()
        self._portNumber = randint(2048, 62000)

    def tearDown(self):
        self.reactor.shutdown()
        self.reactor = None

    def sendRequestAndReceiveResponse(self, request, recvSize=4096):
        self.responseCalled = False
        def response(**kwargs):
            yield 'The Response'
            self.responseCalled = True
        server = HttpServer(self.reactor, self._portNumber, response, recvSize=recvSize)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
        sok.send(request)
        while not self.responseCalled:
            self.reactor.step()
        return sok.recv(4096)

    def testConnect(self):
        self.req = False
        def onRequest(**kwargs):
            self.req = True
            yield 'nosens'
        reactor = Reactor()
        server = HttpServer(reactor, self._portNumber, onRequest)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, response)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        self.assertEquals(1, len(self.reactor._readers)) # only acceptor left
        self.assertEquals({}, self.reactor._writers)

    def testSmallFragments(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n', recvSize=3)
        self.assertEquals('The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):
        def response(**kwargs):
            yield 'some text that is longer than '
            yield 'the lenght of fragments sent'
        reactor = Reactor()
        server = HttpServer(reactor, self._portNumber, response, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, response, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, None, timeout=0.01)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
        sok.send('GET HTTP/1.0\r\n\r\n') # no path
        while select([sok],[], [], 0) != ([sok], [], []):
            reactor.step()
        response = sok.recv(4096)
        self.assertEquals('HTTP/1.0 400 Bad Request\r\n\r\n', response)
        self.assertEquals(1, len(timers))

    def testValidRequestResetsTimer(self):
        reactor = Reactor()
        server = HttpServer(reactor, self._portNumber, lambda **kwargs: ('a' for a in range(3)), timeout=0.01, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler, timeout=0.01)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler, timeout=0.01)
        server.listen()
        reactor.addTimer(0.02, onDone)
        sok = socket()
        sok.connect(('localhost', self._portNumber))
        sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: 8\r\n\r\n')

        while not done:
            reactor.step()


    def testReadChunkedPost(self):
        self.requestData = {}
        def handler(**kwargs):
            self.requestData = kwargs

        reactor = Reactor()
        server = HttpServer(reactor, self._portNumber, handler, timeout=0.01, recvSize=3)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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
        server = HttpServer(reactor, self._portNumber, handler)
        server.listen()
        sok = socket()
        sok.connect(('localhost', self._portNumber))
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

        server = HttpServer(self.reactor, self._portNumber, handler, errorHandler=error_handler, maxConnections=5)
        server.listen()

        self.reactor.getOpenConnections = lambda: 10

        sock = socket()
        sock.connect(('localhost', self._portNumber))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step()
        self.reactor.step()

        self.assertEquals('FAIL', sock.recv(1024))
        self.assertEquals([503], codes)

    def testOnlyHandleAMaximumNrOfRequestsBelowBoundary(self):
        def handler(**kwargs):
            yield "OK"

        def error_handler(**kwargs):
            yield "FAIL"

        server = HttpServer(self.reactor, self._portNumber, handler, errorHandler=error_handler, maxConnections=10)
        server.listen()

        self.reactor.getOpenConnections = lambda: 5

        sock = socket()
        sock.connect(('localhost', self._portNumber))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step()
        self.reactor.step()

        self.assertEquals('OK', sock.recv(1024))

    def testDefaultErrorHandler(self):
        def handler(**kwargs):
            yield "OK"

        server = HttpServer(self.reactor, self._portNumber, handler, maxConnections=5)
        server.listen()

        self.reactor.getOpenConnections = lambda: 10

        sock = socket()
        sock.connect(('localhost', self._portNumber))
        self.reactor.step()
        sock.send("GET / HTTP/1.0\r\n\r\n")
        self.reactor.step()
        self.reactor.step()

        self.assertEquals('HTTP/1.0 503 Service Unavailable\r\n\r\n<html><head></head><body><h1>Service Unavailable</h1></body></html>', sock.recv(1024))


    #def testUncaughtException(self):
        #done = []
        #def onRequest(**kwargs):
            #yield "HTTP\1.0 200 Ok\r\n\r\nStart data"
            #done.append('onRequest')
            #raise Exception("This exception is printed.")
        #port = randint(10000, 2**16)
        #reactor = Reactor()
        #server = HttpServer(reactor, port, onRequest)
        #sok = socket()
        #sok.connect(('localhost', port))
        #sok.send('GET / HTTP/1.0\r\n\r\n')
        #reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        #while not done:
            #reactor.step()

        #try:
            #sok.recv(4000) # wie een beter plan heeft mag het zeggen
            #self.fail('Socket not closed by server')
        #except SocketError, e:
            #print "asdf", type(e), str(e)

        ## 1. socket closed
        ## 2. exceptie geraised (print or whatever)



    #def testPrematureClientClose(self):
        """Seen in certain phases of the moon. Kvs has not (20071101) been able to reproduce this in tests."""
        #self.almostDone = False
        #self.done = False

        #def handler(**kwargs):
            #if self.almostDone == True:
                #self.done = True
                #raise StopIteration()
            #if kwargs.get("Body", None) == 'abcde':
                #self.almostDone = True

        #port = randint(20000,25000)
        #reactor = Reactor()
        #server = HttpServer(reactor, port, handler, timeout=0.01)
        #sok = socket()
        #sok.connect(('localhost', port))
        #sok.send('POST / HTTP/1.0\r\nContent-Type: application/x-www-form-urlencoded\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nabcde\r\n0\r\n')

        #reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        #while not self.done:
            #reactor.step()
