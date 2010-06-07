from unittest import TestCase
from socket import socket, gaierror as SocketGaiError
from random import randint
from httpreadertest import server as testserver
from weightless import HttpServer, httpget, Reactor, compose

def clientget(host, port, path):
    client = socket()
    client.connect((host,  port))
    client.send('GET %s HTTP/1.1\r\n\r\n' % path)
    return client
 
class AsyncReaderTest(TestCase):

    def dispatch(self, *args, **kwargs):
        return compose(self.handler(*args, **kwargs))

    def setUp(self):
        self.reactor = Reactor()
        self.port = randint(2**10, 2**16)
        self.httpserver = HttpServer(self.reactor, self.port, self.dispatch)

    def testOne(self):
        done = [False]
        backofficeport = self.port + 1
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request)
            yield response
            done[0] = True
        self.handler = passthruhandler
        backofficeserver = testserver(backofficeport, "hello!", [])
        client = clientget('localhost', self.port, '/')
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
                exceptions.append(e)
        self.handler = failingserver
        clientget('localhost', self.port, '/')
        target = ('localhost', 'port', '/')
        while not exceptions:
            self.reactor.step()
        self.assertEquals(TypeError, type(exceptions[0]))

        target = ('localhost', 87, '/')
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            self.reactor.step()
        self.assertEquals(IOError, type(exceptions[0]))

        target = ('localhosta', self.port, '/')
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            self.reactor.step()
        self.assertEquals(SocketGaiError, type(exceptions[0]))
