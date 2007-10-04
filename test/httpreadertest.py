## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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
from time import sleep
from socket import socket
from threading import Thread, Event
from weightless import HttpReader, Reactor, VERSION as WlVersion
import sys
from StringIO import StringIO

def server(port, response, request):
    isListening = Event()
    def serverProcess():
        serverSok = socket()
        serverSok.bind(('0.0.0.0', port))
        serverSok.listen(1)
        isListening.set()
        newSok, addr = serverSok.accept()
        request.append(newSok.recv(4096))
        newSok.send(response)
        newSok.close()
        serverSok.close()

    thread=Thread(None, serverProcess)
    thread.start()
    isListening.wait()
    return thread

class HttpReaderTest(TestCase):

    def testRequestAndHeaders(self):
        HttpReader.RECVSIZE = 7
        port = randint(2**10, 2**16)
        request = []
        serverThread = server(port, "HTTP/1.1 200 OK\r\ncOnteNt-type: text/html\r\n\r\nHello World!", request)
        def receiveResponse(reader, Client=None, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            self.dataReceived = Client, HTTPVersion, StatusCode, ReasonPhrase, Headers
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://localhost:%s/aap/noot/mies' % port, receiveResponse)
        for i in range(8): reactor.step()
        self.assertEquals('GET /aap/noot/mies HTTP/1.0\r\nHost: localhost\r\nUser-Agent: Weightless/v%s\r\n\r\n' % WlVersion, request[0])
        serverThread.join()
        self.assertEquals(('1.1', '200', 'OK', {'Content-Type': 'text/html'}), self.dataReceived[1:])
        self.assertEquals('127.0.0.1', self.dataReceived[0][0])

    def testGetAllData(self):
        HttpReader.RECVSIZE = 7
        fragments = []
        port = randint(2**10, 2**16)
        serverThread = server(port, "HTTP/1.1 200 OK\r\ncOnteNt-type: text/html\r\n\r\nHello World!", [])
        def receiveFragment(fragment):
            fragments.append(fragment)
        def receiveResponse(reader, Client=None, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            reader.receiveFragment(receiveFragment)
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://localhost:%s/aap/noot/mies' % port, receiveResponse)
        for i in range(9): reactor.step()
        serverThread.join()
        self.assertEquals('Hello World!', ''.join(fragments))

    def testNoPort(self):
        fragments = []
        done = []
        def receiveFragment(fragment):
            if fragment == None:
                done.append(True)
            else:
                fragments.append(fragment)
        def receiveResponse(reader, Client=None, HTTPVersion=None, StatusCode=None, ReasonPhrase=None, Headers=None):
            self.dataReceived = HTTPVersion, StatusCode, ReasonPhrase, Headers
            reader.receiveFragment(receiveFragment)
        reactor = Reactor()
        reader = HttpReader(reactor, 'http://www.cq2.org/', receiveResponse)
        while not done:
            reactor.step()
        self.assertEquals('302', self.dataReceived[1])
        self.assertEquals('Found', self.dataReceived[2])
        self.assertEquals('close', self.dataReceived[3]['Connection'])
        self.assertEquals('<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>\n', ''.join(fragments))

    def testEmptyPath(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        request = []
        serverThread = server(port, "HTTP/1.0 200 OK\r\n\r\n", request)
        reader = HttpReader(reactor, "http://localhost:%s" % port, lambda data: 'a')
        reactor.step()
        #reactor.step()
        #reactor.step()
        serverThread.join()
        self.assertTrue(request[0].startswith('GET / HTTP/1.0\r\n'), request[0])

    def testTimeoutOnInvalidRequest(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        serverThread = server(port, "HTTP/1.0 *invalid reponse* 200 OK\r\n\r\n", [])
        errorArgs = []
        def error(*args, **kwargs):
            errorArgs.append(args)
        reader = HttpReader(reactor, "http://localhost:%s" % port, None, error)
        while not errorArgs:
            reactor.step()
        serverThread.join()
        self.assertEquals([('timeout while receiving headers',)], errorArgs)

    def testDefaultErrorHandling(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        serverThread = server(port, "HTTP/1.0 *invalid reponse* 200 OK\r\n\r\n", [])
        reader = HttpReader(reactor, "http://localhost:%s" % port, None, None)
        myerrorstream = StringIO()
        sys.stderr = myerrorstream
        try:
            while not myerrorstream.getvalue():
                reactor.step()
        finally:
            sys.stderr = sys.__stderr__
        serverThread.join()
        self.assertEquals('timeout while receiving headers', myerrorstream.getvalue())

    def testResetTimer(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        serverThread = server(port, "HTTP/1.0 200 OK\r\n\r\nresponse", [])
        self.msg = None
        fragments = []
        def connect(*args, **kwargs):
            reader.receiveFragment(response)
        def response(fragment):
            fragments.append(fragment)
        def error(msg):
            self.msg = msg
        HttpReader.RECVSIZE = 3
        reader = HttpReader(reactor, "http://localhost:%s" % port, connect, error, timeout=0.01)
        while not fragments:
            reactor.step()
        sleep(0.02) # 2 * timeout, just to be sure
        reactor.step()
        self.assertFalse(self.msg)
