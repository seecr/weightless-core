## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013 Seecr (Seek You Too B.V.) http://seecr.nl
#
# This file is part of "Weightless"
#
# "Weightless" is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# "Weightless" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "Weightless"; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##

from unittest import TestCase
from socket import socket
from seecr.test import CallTrace
from random import randint
from os import system
from subprocess import Popen, PIPE

from weightless.http import Acceptor
import collections

class AcceptorTest(TestCase):

    def testStartListening(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, None)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        sok = reactor.calledMethods[0].args[0]
        out = Popen(['netstat', '--numeric', '--listening', '--tcp'], stdout=PIPE, stderr=PIPE).communicate()[0]
        out = out.decode('UTF-8')
        self.assertTrue(str(port) in out, out)
        sok.close()
        callback = reactor.calledMethods[0].args[1]
        self.assertTrue(isinstance(callback, collections.Callable))

    def testConnect(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        acceptCallback = reactor.calledMethods[0].args[1]
        sok = socket()
        sok.connect(('localhost', port))
        acceptCallback()
        self.assertEqual(['addReader'], reactor.calledMethodNames())
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
        self.assertEqual('addReader', reactor.calledMethods[1].name)
        sink = reactor.calledMethods[1].args[1]
        self.assertEqual(socket, type(self.args[0]))
        reactor.calledMethods[0].args[0].close()
        sok.close()

    def testReadData(self):
        reactor = CallTrace('reactor')
        port = randint(2**10, 2**16)
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
            def __next__(inner):
                self.next = True
        acceptor = Acceptor(reactor, port, sinkFactory)
        acceptCallback = reactor.calledMethods[0].args[1]
        sok = socket()
        sok.connect(('localhost', port))
        acceptCallback()
        sink = reactor.calledMethods[1].args[1]
        self.next = False
        next(sink)
        self.assertTrue(self.next)
        reactor.calledMethods[0].args[0].close()
        sok.close()

    def testReuseAddress(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None)
        client = socket()
        client.connect(('127.0.0.1', port))
        acceptor._accept()
        acceptor.close()
        acceptor = Acceptor(reactor, port, lambda sok: None)
        client.close()

    def testAcceptorWithPrio(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None, prio=5)
        client = socket()
        client.connect(('127.0.0.1', port))
        acceptor._accept()
        self.assertEqual(5, reactor.calledMethods[0].kwargs['prio'])
        client.close()

    def testBindAddress_DefaultsTo_0_0_0_0(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None, prio=5)
        self.assertEqual(('0.0.0.0', port), acceptor._sok.getsockname())

    def testBindAddressCustom(self):
        reactor = CallTrace()
        port = randint(2**10, 2**16)
        acceptor = Acceptor(reactor, port, lambda sok: None, bindAddress='127.0.0.1', prio=5)
        self.assertEqual(('127.0.0.1', port), acceptor._sok.getsockname())

