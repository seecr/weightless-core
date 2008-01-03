## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2008 Seek You Too (CQ2) http://www.cq2.nl
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
from socket import socket
from weightless import Acceptor
from cq2utils import CallTrace
from random import randint
from os import system

class AcceptorTest(TestCase):

    def testStartListening(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, None)
        self.assertEquals('addReader', reactor.calledMethods[0].name)
        sok = reactor.calledMethods[0].args[0]
        self.assertEquals(0, system('netstat --ip --listening | grep "*:%d">/dev/null' % port))
        sok.close()
        callback = reactor.calledMethods[0].args[1]
        self.assertTrue(callable(callback))

    def testConnect(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None)
        self.assertEquals('addReader', reactor.calledMethods[0].name)
        acceptCallback = reactor.calledMethods[0].args[1]
        sok = socket()
        sok.connect(('localhost', port))
        acceptCallback()
        self.assertEquals('addReader', reactor.calledMethods[1].name)
        self.assertEquals(socket, type(reactor.calledMethods[1].args[0]))
        reactor.calledMethods[0].args[0].close()
        sok.close()

    def testCreateSink(self):
        reactor = CallTrace('reactor')
        port = randint(2**10, 2**16)
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs): self.args, self.kwargs = args, kwargs
        acceptor = Acceptor(reactor, port, sinkFactory)
        acceptCallback = reactor.calledMethods[0].args[1]
        sok = socket()
        sok.connect(('localhost', port))
        acceptCallback()
        self.assertEquals('addReader', reactor.calledMethods[1].name)
        sink = reactor.calledMethods[1].args[1]
        self.assertEquals(socket, type(self.args[0]))
        reactor.calledMethods[0].args[0].close()

    def testReadData(self):
        reactor = CallTrace('reactor')
        port = randint(2**10, 2**16)
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
            def next(inner):
                self.next = True
        acceptor = Acceptor(reactor, port, sinkFactory)
        acceptCallback = reactor.calledMethods[0].args[1]
        sok = socket()
        sok.connect(('localhost', port))
        acceptCallback()
        sink = reactor.calledMethods[1].args[1]
        self.next = False
        sink.next()
        self.assertTrue(self.next)
        reactor.calledMethods[0].args[0].close()
