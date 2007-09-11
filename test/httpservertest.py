from unittest import TestCase
from random import randint
from socket import socket
from weightless import Reactor, HttpServer
from time import sleep
from weightless import _httpserver

class HttpServerTest(TestCase):

    def setUp(self):
        self.reactor = Reactor()

    def tearDown(self):
        self.reactor.shutdown()
        self.reactor = None

    def testConnect(self):
        self.req = False
        def onRequest(**kwargs):
            self.req = True
            yield 'nosens'
        port = randint(2**10, 2**16)
        reactor = Reactor()
        server = HttpServer(reactor, port, onRequest)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send('GET / HTTP/1.0\r\n\r\n')
        reactor.step() # connect/accept
        reactor.step() # read GET request
        reactor.step() # call onRequest for response data
        self.assertEquals(True, self.req)

    def testSendHeader(self):
        def response(**kwargs):
            self.kwargs = kwargs
            yield 'nosense'
        port = randint(2**10, 2**16)
        reactor = Reactor()
        server = HttpServer(reactor, port, response)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        reactor.step() # connect/accept
        reactor.step() # read GET request
        reactor.step() # call onRequest for response data
        self.assertEquals({'RequestURI': '/path/here', 'HTTPVersion': '1.0', 'Method': 'GET', 'Headers': {'Connection': 'close', 'Ape-Nut': 'Mies'}}, self.kwargs)

    def testGetResponse(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEquals('The Response', response)

    def testCloseConnection(self):
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEquals('The Response', response)
        self.assertEquals(1, len(self.reactor._readers)) # only acceptor left
        self.assertEquals({}, self.reactor._writers)

    def sendRequestAndReceiveResponse(self, request):
        self.responseCalled = False
        def response(**kwargs):
            yield 'The Response'
            self.responseCalled = True
        port = randint(2**10, 2**16)
        server = HttpServer(self.reactor, port, response)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send(request)
        while not self.responseCalled:
            self.reactor.step()
        return sok.recv(4096)

    def testSmallFragments(self):
        _httpserver.RECVSIZE = 3
        response = self.sendRequestAndReceiveResponse('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        self.assertEquals('The Response', response)

    def testSmallFragmentsWhileSendingResponse(self):
        def response(**kwargs):
            yield 'some text that is longer than '
            yield 'the lenght of fragments sent'
        port = randint(2**10, 2**16)
        reactor = Reactor()
        server = HttpServer(reactor, port, response)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send('GET /path/here HTTP/1.0\r\nConnection: close\r\nApe-Nut: Mies\r\n\r\n')
        while not reactor._writers:
            reactor.step()
        serverSok, handler = reactor._writers.items()[0]
        orgSend = serverSok.send
        def fckdUpSend(data):
            orgSend(data[:3])
            return 3
        serverSok.send = fckdUpSend
        for i in range(21):
            reactor.step()
        fragment = sok.recv(4096)
        self.assertEquals('some text that is longer than the lenght of fragments sent', fragment)

    def testInvalidRequest(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        server = HttpServer(reactor, port, None, timeout=0.01)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send('GET HTTP/1.0\r\n\r\n') # no path
        reactor.step()
        reactor.step()
        reactor.step()
        response = sok.recv(4096)
        self.assertEquals('HTTP/1.0 400 Bad Request\r\n\r\n', response)

    def testValidRequestResetsTimer(self):
        port = randint(2**10, 2**16)
        reactor = Reactor()
        server = HttpServer(reactor, port, lambda **kwargs: ('a' for a in range(3)), timeout=0.01)
        sok = socket()
        sok.connect(('localhost', port))
        sok.send('GET / HTTP/1.0\r\n\r\n')
        sleep(0.02)
        for i in range(10):
            reactor.step()
        response = sok.recv(4096)
        self.assertEquals('aaa', response)
