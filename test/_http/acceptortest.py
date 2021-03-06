## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013, 2015, 2020-2021 Seecr (Seek You Too B.V.) https://seecr.nl
# Copyright (C) 2015 Koninklijke Bibliotheek (KB) http://www.kb.nl
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
from seecr.test.portnumbergenerator import PortNumberGenerator

from socket import socket
from seecr.test import CallTrace
from os import system
from subprocess import Popen, PIPE

from weightless.http import Acceptor


class AcceptorTest(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.port = PortNumberGenerator.next()
        self.socketCatcher = []

    def tearDown(self):
        [sok.close() for sok in self.socketCatcher]
        TestCase.tearDown(self)

    def testStartListening(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, None)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        sok = reactor.calledMethods[0].args[0]
        try:
            with Popen(['netstat', '--numeric', '--listening', '--tcp'], stdout=PIPE, stderr=PIPE) as p:
                out, _ = p.communicate()
        finally:
            sok.close()
        self.assertTrue(str(self.port).encode() in out, out)
        callback = reactor.calledMethods[0].args[1]
        self.assertTrue(callable(callback))

    def testConnect(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, self.socketCatcher.append)
        try:
            self.assertEqual('addReader', reactor.calledMethods[0].name)
            acceptCallback = reactor.calledMethods[0].args[1]
            with socket() as sok:
                sok.connect(('localhost', self.port))
                acceptCallback()
                self.assertEqual(['addReader'], reactor.calledMethodNames())
                reactor.calledMethods[0].args[0].close()
        finally:
            acceptor.close()

    def testCreateSink(self):
        reactor = CallTrace('reactor')
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
                self.socketCatcher.append(args[0])
        acceptor = Acceptor(reactor, self.port, sinkFactory)
        try:
            acceptCallback = reactor.calledMethods[0].args[1]
            with socket() as sok:
                sok.connect(('localhost', self.port))
                acceptCallback()
                self.assertEqual('addReader', reactor.calledMethods[1].name)
                sink = reactor.calledMethods[1].args[1]
                self.assertEqual(socket, type(self.args[0]))
                reactor.calledMethods[0].args[0].close()
        finally:
            acceptor.close()

    def testReadData(self):
        reactor = CallTrace('reactor')
        class sinkFactory(object):
            def __init__(inner, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
                self.socketCatcher.append(args[0])
            def __next__(inner):
                self.next = True
        acceptor = Acceptor(reactor, self.port, sinkFactory)
        try:
            acceptCallback = reactor.calledMethods[0].args[1]
            with socket() as sok:
                sok.connect(('localhost', self.port))
                acceptCallback()
                sink = reactor.calledMethods[1].args[1]
                self.next = False
                next(sink)
                self.assertTrue(self.next)
                reactor.calledMethods[0].args[0].close()
        finally:
            acceptor.close()

    def testReuseAddress(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, self.socketCatcher.append)
        with socket() as client:
            client.connect(('127.0.0.1', self.port))
            acceptor._accept()
            acceptor.close()
            acceptor = Acceptor(reactor, self.port, lambda sok: None)
            acceptor.close()

    def testAcceptorWithPrio(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, self.socketCatcher.append, prio=5)
        try:
            with socket() as client:
                client.connect(('127.0.0.1', self.port))
                acceptor._accept()
                self.assertEqual(5, reactor.calledMethods[0].kwargs['prio'])
        finally:
            acceptor.close()

    def testBindAddress_DefaultsTo_0_0_0_0(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, lambda sok: None, prio=5)
        try:
            self.assertEqual(('0.0.0.0', self.port), acceptor._sok.getsockname())
        finally:
            acceptor.close()

    def testBindAddressCustom(self):
        reactor = CallTrace()
        acceptor = Acceptor(reactor, self.port, lambda sok: None, bindAddress='127.0.0.1', prio=5)
        try:
            self.assertEqual(('127.0.0.1', self.port), acceptor._sok.getsockname())
        finally:
            acceptor.close()

