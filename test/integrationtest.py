#!/usr/bin/env python2.5

from glob import glob
import os, sys

for file in glob('../deps.d/*'):
    sys.path.insert(0, file)

if os.environ.get('PYTHONPATH', '') == '':
    sys.path.insert(0, '..')

from unittest import TestCase, main

from weightless import Reactor, HttpServer
from socket import socket
from time import sleep

class IntegrationTest(TestCase):
    def testPostWithNoBodyDoesNotStartInfiniteLoop(self):
        reactor = Reactor()
        port = 23456
        def connect(*args, **kwargs):
            yield "HTTP 200 ok\r\n\r\nHello World!"

        server = HttpServer(reactor, port, connect, timeout=1)
        s = socket()
        s.connect(('localhost', port))
        reactor.step()
        self.assertEquals(2, len(reactor._readers))

        s.send('POST / HTTP/1.0\r\n\r\n')
        reactor.step()
        s.close()
        self.assertEquals(1, len(reactor._readers))


if __name__ == '__main__':
    main()