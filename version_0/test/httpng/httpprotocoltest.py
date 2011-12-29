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
from weightless.core import compose, autostart
from weightless.core.utils import copyBytes, readAll
from weightless.httpng import HttpProtocol, http

class MockTimer(object):
    def __init__(self, timeout):
        pass
    def __enter__(self):
        pass
    def __exit__(self, *args, **kwargs):
        pass

class HttpProtocolTest(TestCase):

    def setUp(self):
        self._timer = HttpProtocol.Timer
        HttpProtocol.Timer = MockTimer
        self.p = HttpProtocol()

    def tearDown(self):
        HttpProtocol.Timer = self._timer

    def addHandler(self, handler):
        self.p.addObserver(handler)

    def processConnection(self):
        stack = compose(self.p.processConnection())
        self.assertEquals(None, stack.next()) # i.e. it starts with accepting data
        return stack

    def testRequestHandledByDifferentObservers(self):
        class GetHandler(object):
            def processRequest(self, Method=None, **kwargs):
                if Method=='GET':
                    return (x for x in ['HTTP/1.1 200 Ok\r\n', 'hello GET'])
        class PostHandler(object):
            def processRequest(self, Method=None, **kwargs):
                if Method=='HEAD':
                    return (x for x in ['HTTP/1.1 200 Ok\r\n', 'hello POST'])
        self.addHandler(PostHandler())
        self.addHandler(GetHandler())
        stack = self.processConnection()
        response = stack.send('GET / HTTP/1.1\r\n\r\n')
        self.assertEquals('HTTP/1.1 200 Ok\r\n', response)
        self.assertEquals('hello GET', stack.next())
        stack.next()
        response = stack.send('HEAD / HTTP/1.1\r\n\r\n')
        self.assertEquals('HTTP/1.1 200 Ok\r\n', response)
        self.assertEquals('hello POST', stack.next())

    def testForwardParsedGETRequest(self):
        args = []
        class MyHandler(object):
            def processRequest(self, **kwargs):
                args.append(kwargs)
                yield 'HTTP/1.....etc'
        self.addHandler(MyHandler())
        stack = self.processConnection()
        uri = 'http://host:80/path;user=jan/show;a=all?&a=b&a=c#ref'
        header = 'Content-Type: text/xml; encoding="utf-8"; version="1.0"'
        message = 'GET %s HTTP/1.1\r\n%s\r\n\r\n' % (uri, header)
        response = stack.send(message)
        self.assertEquals('HTTP/1.....etc', response)
        args = args[0]
        self.assertEquals('HTTP/1.....etc', response)
        self.assertEquals(args['fragment'], 'ref')
        self.assertEquals(args['RequestURI'], 'http://host:80/path;user=jan/show;a=all?&a=b&a=c#ref')
        self.assertEquals(args['netloc'], ('host', '80')),
        headers = args['Headers']
        self.assertEquals(headers['content-type'], {'text/xml': {'encoding':'utf-8', 'version':'1.0'}})
        self.assertEquals(args['query'], {'a': ['b', 'c']})
        self.assertEquals(args['path'], '/path;user=jan/show;a=all')
        self.assertEquals(args['scheme'], 'http')
        self.assertEquals(args['Method'], 'GET')
        self.assertEquals(args['HTTPVersion'], '1.1')

    def testForwardParsedPOSTRequest(self):
        args = []
        class MyHandler(object):
            def processRequest(self, **kwargs):
                args.append(kwargs)
                yield 'HTTP/1.....etc'
        self.addHandler(MyHandler())
        stack = self.processConnection()
        uri = 'http://ahost:8000/a/b;user=pete/a;b=any?&x=y&p=q#anchor'
        header = 'Content-Type: text/plain; encoding="utf-16"; version="1.1"\r\nContent-Length: 20'
        message = 'POST %s HTTP/1.0\r\n%s\r\n\r\n' % (uri, header)
        response = stack.send(message)
        args = args[0]
        self.assertEquals('HTTP/1.....etc', response)
        self.assertEquals(args['fragment'], 'anchor')
        self.assertEquals(args['RequestURI'], 'http://ahost:8000/a/b;user=pete/a;b=any?&x=y&p=q#anchor')
        self.assertEquals(args['netloc'], ('ahost', '8000')),
        headers = args['Headers']
        self.assertEquals(headers['content-length'], {'20': {}})
        self.assertEquals(headers['content-type'], {'text/plain': {'encoding':'utf-16', 'version':'1.1'}})
        self.assertEquals(args['ContentLength'], 20)
        self.assertEquals(args['query'], {'x': ['y'], 'p': ['q']})
        self.assertEquals(args['path'], '/a/b;user=pete/a;b=any')
        self.assertEquals(args['scheme'], 'http')
        self.assertEquals(args['Method'], 'POST')
        self.assertEquals(args['HTTPVersion'], '1.0')

    def testPOST(self):
        class Buffer(object):
            def __init__(self):
                self.buff = []
            @autostart
            def sink(self):
                while True:
                    self.buff.append((yield))
            def value(self):
                return ''.join(self.buff)
        buff = Buffer()
        class MyHandler(object):
            def processRequest(self, ContentLength=None, **kwargs):
                yield copyBytes(ContentLength, buff.sink())
                yield 'HTTP/1.1 2'
                yield '00 Ok\r\n'
        self.addHandler(MyHandler())
        stack = self.processConnection()
        response = stack.send('POST / HTTP/1.1\r')
        self.assertEquals(None, response)
        response = stack.send('\nContent-Length: 5\r\n\r\n12345')
        self.assertEquals('HTTP/1.1 2', response)
        response = stack.next()
        self.assertEquals('00 Ok\r\n', response)
        self.assertEquals('12345', buff.value())

    def testPostWith100Continue(self):
        class Buffer(object):
            def __init__(self):
                self.buff = []
            @autostart
            def sink(self):
                while True:
                    self.buff.append((yield))
            def value(self):
                return ''.join(self.buff)
        buff = Buffer()
        class MyHandler(object):
            def processRequest(self, ContentLength=None, **kwargs):
                yield copyBytes(ContentLength, buff.sink())
                yield 'HTTP/1.1 200 Ok\r\n'
        self.addHandler(MyHandler())
        stack = self.processConnection()
        response = stack.send('POST / HTTP/1.1\r\nContent-Length: 5\r\nExpect: 100-continue\r\n\r\n')
        self.assertEquals('HTTP/1.1 100 Continue\r\n', response)
        response = stack.send(None)
        self.assertEquals(None, response)
        response = stack.send('12345')
        self.assertEquals('HTTP/1.1 200 Ok\r\n', response)
        self.assertEquals('12345', buff.value())

    def testPostWith100ContinueNOT(self):
        class MyHandler(object):
            def processRequest(self, ContentLength=None, **kwargs):
                return
        self.addHandler(MyHandler())
        stack = self.processConnection()
        response = stack.send('POST / HTTP/1.1\r\nContent-Length: 5\r\nExpect: 100-continue\r\n\r\n')
        self.assertEquals('HTTP/1.1 417 Expectation failed\r\n', response)

    def testNotImplemented(self):
        stack = self.processConnection()
        response = stack.send('POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\n')
        self.assertEquals('HTTP/1.1 501 Not Implemented\r\n', response)

    def testReadChunkEncoded(self):
        parts = []
        class MyHandler(object):
            def processRequest(self, **kwargs):
                while True:
                    try:
                        part = yield
                    except StopIteration:
                        break
                    else:
                        parts.append(part)
                yield 'HTTP/1.1 200 Ok\r\n'
                yield ''.join(parts)

        self.addHandler(MyHandler())
        stack = self.processConnection()
        response = stack.send('POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n12345\r\n0')
        self.assertEquals(None, response)
        response = stack.send('\r\n')
        self.assertEquals('HTTP/1.1 200 Ok\r\n', response)
        response = stack.next()
        self.assertEquals('12345', response)
        self.assertEquals('12345', ''.join(parts))

    #Client
