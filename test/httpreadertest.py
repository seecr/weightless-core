## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2009 Seek You Too (CQ2) http://www.cq2.nl
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
from socket import socket, timeout
from threading import Thread, Event


from weightless import HttpReader, Reactor, VERSION as WlVersion
from weightless._httpreader import HttpReaderFacade, Connector, HandlerFacade, _httpParseUrl
import sys
from StringIO import StringIO
from cq2utils import CallTrace
from cq2utils.cq2testcase import MatchAll

def server(port, response, expectedrequest, delay=0, loop=50):
    isListening = Event()
    def serverProcess():
        serverSok = socket()
        serverSok.bind(('0.0.0.0', port))
        serverSok.listen(1)
        isListening.set()
        newSok, addr = serverSok.accept()
        newSok.settimeout(1)

        msg = ''
        for i in xrange(loop):
            if expectedrequest:
                try:
                    msg += newSok.recv(4096)
                    if msg == expectedrequest:
                        break
                    if len(msg) >= len(expectedrequest):
                        print "hihi"
                        raise timeout
                except timeout:
                    print "Received:", repr(msg)
                    print "expected:", repr(expectedrequest)
                    return
        if response:
            if hasattr(response, 'next'):
                for r in response:
                    newSok.send(r)
            else:
                newSok.send(response)
            sleep(delay)
            newSok.close()
        else:
            sleep(0.5)
        serverSok.close()

    thread=Thread(None, serverProcess)
    thread.start()
    isListening.wait()
    return thread

class HttpReaderTest(TestCase):

    def testRequestAndHeaders(self):
        port = randint(2**10, 2**16)
        expectedrequest = "GET /aap/noot/mies HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        dataReceived = []
        serverThread = server(port, "HTTP/1.1 200 OK\r\ncOnteNt-type: text/html\r\n\r\nHello World!", expectedrequest)
        class Generator(object):
            def __init__(self):
                self.throw = None
                self.next = None
            def send(self, data):
                dataReceived.append(data)
        reactor = Reactor()
        connection = Connector(reactor, 'localhost', port)
        reader = HttpReader(reactor, connection, Generator(), 'GET', 'localhost', '/aap/noot/mies', recvSize=7)
        reactor.addTimer(0.1, lambda: self.fail("Test Stuck"))
        while 'Hello World!' != "".join((x for x in dataReceived[1:] if x)):
            reactor.step()
        serverThread.join()
        self.assertEquals({'HTTPVersion': '1.1', 'StatusCode': '200', 'ReasonPhrase': 'OK', 'Headers': {'Content-Type': 'text/html'}, 'Client': ('127.0.0.1', MatchAll())}, dataReceived[0])

    def testHttpUrlParse(self):
        host, port, path = _httpParseUrl('http://www.cq2.org')
        self.assertEquals('www.cq2.org', host)
        self.assertEquals(80, port)
        self.assertEquals('/', path)

        host, port, path = _httpParseUrl('http://www.cq2.org:5000/page#anchor')
        self.assertEquals('www.cq2.org', host)
        self.assertEquals(5000, port)
        self.assertEquals('/page#anchor', path)

        host, port, path = _httpParseUrl('http://www.cq2.org:5000/page?x=1')
        self.assertEquals('www.cq2.org', host)
        self.assertEquals(5000, port)
        self.assertEquals('/page?x=1', path)


    def testEmptyPath(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        request = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "HTTP/1.1 200 OK\r\n\r\n", request)
        reader = HttpReaderFacade(reactor, "http://localhost:%s" % port, lambda data: 'a')
        reactor.step()
        reactor.step()
        serverThread.join()
        #self.assertTrue(request[0].startswith('GET / HTTP/1.1\r\n'), request[0])

    def testTimeoutOnInvalidRequest(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "HTTP/1.1 *invalid reponse* 200 OK\r\n\r\n", expectedrequest)
        errorArgs = []
        def error(exception):
            errorArgs.append(exception)
        reader = HttpReaderFacade(reactor, "http://localhost:%s" % port, None, error, timeout=0.01)
        while not errorArgs:
            reactor.step()
        serverThread.join()
        self.assertEquals('timeout while receiving data', str(errorArgs[0]))

    def testTimeoutOnSilentServer(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "", expectedrequest)
        errorArgs = []
        class Handler:
            def throw(self, exception):
                errorArgs.append(exception)
        def error(exception):
            errorArgs.append(exception)
        reader = HttpReader(reactor, Connector(reactor, 'localhost', port), Handler(), "GET", "localhost", "/", timeout=0.01)
        reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        while not errorArgs:
            reactor.step()
        serverThread.join()
        self.assertEquals('timeout while receiving data', str(errorArgs[0]))

    def testTimeoutOnServerGoingSilentAfterHeaders(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "HTTP/1.1 200 OK\r\n\r\n", expectedrequest, delay=1)
        errorArgs = []
        class Handler:
            def send(self, data):
                pass
            def throw(self, exception):
                errorArgs.append(exception)
        def error(exception):
            errorArgs.append(exception)
        reader = HttpReader(reactor, Connector(reactor, 'localhost', port), Handler(), "GET", "localhost", "/", timeout=0.01)
        reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        while not errorArgs:
            reactor.step()
        serverThread.join()
        self.assertEquals('timeout while receiving data', str(errorArgs[0]))

    def testClearTimer(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "HTTP/1.1 200 OK\r\n\r\nresponse", expectedrequest)
        self.exception = None
        sentData = []
        def send(data):
            sentData.append(data)
        def throw(exception):
            self.exception = exception
        reader = HttpReaderFacade(reactor, "http://localhost:%s" % port, send, throw, timeout=0.01, recvSize=3)
        while not self.exception:
            reactor.step()
        sleep(0.02) # 2 * timeout, just to be sure

        self.assertTrue(isinstance(self.exception, StopIteration))

    def testPost(self):
        port = randint(2048, 4096)
        reactor = Reactor()
        request = "POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\nSOAPAction: blah\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n1\r\nA\r\n1\r\nB\r\n1\r\nC\r\n0\r\n\r\n"
        serverThread = server(port, "HTTP/1.1 200 OK\r\n\r\nresponse", request, loop=9)
        sentData = []
        done = []
        def send(data):
            sentData.append(data)
        def throw(exception):
            if isinstance(exception, StopIteration):
                done.append(True)
        def next():
            yield "A"
            yield "B"
            yield "C"
            yield None

        reader = HttpReaderFacade(reactor, "http://localhost:%s" % port, send, errorHandler=throw, timeout=0.5, headers={'SOAPAction': 'blah'}, bodyHandler=next)

        reactor.addTimer(3.0, lambda: self.fail("Test Stuck"))
        while not done:
            reactor.step()

        self.assertEquals(['response'], sentData[1:])
        self.assertEquals('200', sentData[0]['StatusCode'])
        expected = 'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\nSOAPAction: blah\r\nUser-Agent: Weightless/v%s\r\n\r\n' % WlVersion + '1\r\nA\r\n' + '1\r\nB\r\n' + '1\r\nC\r\n' + '0\r\n\r\n'
        self.assertEquals(expected, "".join(request))

    def testWriteChunks(self):
        reader  = HttpReader(CallTrace("reactor"), CallTrace("socket"), HandlerFacade(None, None, None), '', '', '')
        self.assertEquals('1\r\nA\r\n', reader._createChunk('A'))
        self.assertEquals('A\r\n' + 10*'B' + '\r\n', reader._createChunk(10*'B'))

    def testDealWithChunkedResponse(self):
        port = randint(2048, 4096)
        reactor = Reactor()
        sentData = []
        done = []
        expectedrequest = "GET / HTTP/1.1\r\nHost: localhost\r\nUser-Agent: Weightless/v0.4.x\r\n\r\n"
        serverThread = server(port, "\r\n".join("""HTTP/1.1 302 Found
Date: Fri, 26 Oct 2007 07:23:26 GMT
Server: Apache/2.2.3 (Debian) mod_python/3.2.10 Python/2.4.4 mod_ssl/2.2.3 OpenSSL/0.9.8c
Location: /page/softwarestudio.page/show
Transfer-Encoding: chunked
Content-Type: text/html; charset=utf-8

4F
<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>

0


""".split("\n")), expectedrequest)
        class Handler:
            def send(self, data):
                sentData.append(data)
            def throw(self, exception):
                if isinstance(exception, StopIteration):
                    done.append(True)
        reader = HttpReader(reactor, Connector(reactor, 'localhost', int(port)), Handler(), 'GET', 'localhost', '/', recvSize=5)

        reactor.addTimer(0.2, lambda: self.fail("Test Stuck"))
        while not done:
            reactor.step()
        self.assertEquals("""<p>The document has moved <a href="/page/softwarestudio.page/show">here</a></p>""", "".join(sentData[1:]))

    def testChunkedAllTheWay(self):
        reactor = CallTrace('Reactor')
        sokket = CallTrace('Sokket')
        data = []
        class Handler:
            def send(self, chunk):
                data.append(chunk)
            def throw(self, exception):
                pass
        httpreader = HttpReader(reactor, sokket, Handler(), 'GET', 'host,nl', '/')
        httpreader._chunked = True
        # chunk == network message
        httpreader._sendFragment('4\r\n1234\r\n')
        self.assertEquals(['1234'], data)
        httpreader._sendFragment('10\r\n0123456789abcdef\r\n')
        self.assertEquals(['1234', '0123456789abcdef'], data)
        del data[0]
        del data[0]
        # chunk = 2 network messages
        httpreader._sendFragment('10\r\nfedcba')
        #self.assertEquals(['fedcba'], data)
        httpreader._sendFragment('9876543210\r\n')
        self.assertEquals(['fedcba9876543210'], data)

    def testLastRecvContainsCompleteChunk(self):
        reactor = CallTrace('Reactor')
        sokket = CallTrace('Sokket')
        data = []
        done = []
        class Handler:
            def send(self, chunk):
                data.append(chunk)
            def throw(self, exception):
                done.append(True)
        httpreader = HttpReader(reactor, sokket, Handler(), 'GET', 'host,nl', '/')
        httpreader._chunked = True
        chunkOne = '9\r\n123456789\r\n'
        chunkTwo = '8\r\n87654321\r\n'
        httpreader._sendFragment(chunkOne)
        self.assertEquals(['123456789'], data)
        httpreader._sendFragment(chunkTwo)
        self.assertEquals(['123456789', '87654321'], data)
        while data: del data[0] # now both in one network message
        httpreader._sendFragment(chunkOne + chunkTwo +'0\r\n\r\n')
        # Send fragment will only read one fragment.
        # Now feed it until all chunks are finished
        httpreader._sendFragment('')
        httpreader._sendFragment('')
        self.assertEquals(['123456789', '87654321'], data)
        self.assertEquals([True], done)
