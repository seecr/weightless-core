from unittest import TestCase
from socket import socket
from httpreadertest import server as testserver
from weightless import HttpServer, httpget, Reactor, compose

class AsyncReaderTest(TestCase):

    def testOne(self):
        done = [False]
        reactor = Reactor()
        backofficeport = 98765
        passthruport = 98766
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('http://localhost:%d/%s' % (backofficeport, request))
            yield response
            done[0] = True
        passthruserver = HttpServer(reactor, passthruport, 
                lambda *args, **kwargs: compose(passthruhandler(*args, **kwargs)))
        backofficeserver = testserver(backofficeport, "hello!", [])
        client = socket()
        client.connect(('localhost', passthruport))
        client.send('GET / HTTP/1.1\r\n\r\n')
        while not done[0]:
            reactor.step()
        response = client.recv(99)
        self.assertEquals('hello!', response)


