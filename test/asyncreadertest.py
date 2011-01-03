## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2010 Seek You Too (CQ2) http://www.cq2.nl
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
from sys import exc_info
from socket import socket, gaierror as SocketGaiError
from random import randint
from httpreadertest import server as testserver
from weightless import HttpServer, httpget, Reactor, compose

from weightless._httpget import _httpRequest

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
    
    def testHttpRequest(self):
        self.assertEquals('GET / HTTP/1.0\r\n', _httpRequest('/'))
        self.assertEquals('GET / HTTP/1.1\r\nHost: weightless.io\r\n', _httpRequest('/', vhost="weightless.io"))


    def testPassRequestThruToBackOfficeServer(self):
        done = [False]
        backofficeport = self.port + 1
        def passthruhandler(*args, **kwargs):
            request = kwargs['RequestURI']
            response = yield httpget('localhost', backofficeport, request)
            yield response
            done[0] = True
        self.handler = passthruhandler
        requests = []
        responses = (i for i in ['hel', 'lo!'])
        backofficeserver = testserver(backofficeport, responses, requests)
        client = clientget('localhost', self.port, '/depot?arg=1&arg=2')
        while not done[0]:
            self.reactor.step()
        response = client.recv(99)
        self.assertEquals('hello!', response)
        self.assertEquals('GET /depot?arg=1&arg=2 HTTP/1.0\r\n\r\n', requests[0])

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
        while not exceptions:
            self.reactor.step()
        self.assertEquals(TypeError, exceptions[0][0])

        target = ('localhost', 87, '/') # invalid port
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            self.reactor.step()
        self.assertEquals(IOError, exceptions[0][0])

        target = ('UEYR^$*FD(#>NDJ.khfd9.(*njnd', 9876, '/') # invalid host
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            self.reactor.step()
        self.assertEquals(SocketGaiError, exceptions[0][0])

        target = ('127.0.0.255', 9876, '/')
        clientget('localhost', self.port, '/')
        exceptions = []
        while not exceptions:
            self.reactor.step()
        self.assertEquals(IOError, exceptions[0][0])
        self.assertEquals(111, exceptions[0][1].message)

