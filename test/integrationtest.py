#!/usr/bin/env python2.5
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

    def testUnknownMethodDoesNotStartInfiniteLoop(self):
        reactor = Reactor()
        port = 23457
        def connect(*args, **kwargs):
            yield "HTTP 200 ok\r\n\r\nHello World!"

        server = HttpServer(reactor, port, connect, timeout=1)
        s = socket()
        s.connect(('localhost', port))
        reactor.step()
        self.assertEquals(2, len(reactor._readers))

        s.send('SOMETHING / HTTP/1.0\r\n\r\n')
        reactor.step()
        s.close()
        self.assertEquals(1, len(reactor._readers))

    def testUnknownCrapDoesNotStartInfiniteLoop(self):
        reactor = Reactor()
        port = 23458
        def connect(*args, **kwargs):
            yield "HTTP 200 ok\r\n\r\nHello World!"

        server = HttpServer(reactor, port, connect, timeout=1)
        s = socket()
        s.connect(('localhost', port))
        reactor.step()
        self.assertEquals(2, len(reactor._readers))

        s.send('NONSENSE')
        self.assertEquals(2, len(reactor._readers))
        sleep(1)
        reactor.step()
        reactor.step()
        reactor.step()
        s.close()
        self.assertEquals(1, len(reactor._readers))

if __name__ == '__main__':
    main()