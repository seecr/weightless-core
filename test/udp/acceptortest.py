## begin license ##
#
# "Weightless" is a High Performance Asynchronous Networking Library. See http://weightless.io
#
# Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
# Copyright (C) 2011-2013, 2015, 2020 Seecr (Seek You Too B.V.) https://seecr.nl
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
from seecr.test import CallTrace
from seecr.test.portnumbergenerator import PortNumberGenerator

from socket import socket, AF_INET, SOCK_DGRAM
from subprocess import Popen, PIPE

from weightless.udp import Acceptor


class UdpAcceptorTest(TestCase):
    def testStartListening(self):
        reactor = CallTrace()
        port = PortNumberGenerator.next()
        Acceptor(reactor, port, lambda sok: lambda: None)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        sok = reactor.calledMethods[0].args[0]
        with Popen(['netstat', '--numeric', '--listening', '--udp'], stdout=PIPE, stderr=PIPE) as proc:
            out, _ = proc.communicate()
        self.assertTrue(str(port) in out.decode(), out.decode())
        sok.close()
        callback = reactor.calledMethods[0].args[1]
        self.assertTrue(callable(callback))

    def testHandle(self):
        data = []
        def sinkFactory(sock):
            def handle():
                data.append(sock.recvfrom(2048))
            return handle
        reactor = CallTrace()
        port = PortNumberGenerator.next()
        Acceptor(reactor, port, sinkFactory)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        handleCallback = reactor.calledMethods[0].args[1]
        sok = socket(AF_INET, SOCK_DGRAM)
        sok.sendto(b"TEST", ('localhost', port))
        handleCallback()
        contents, remoteAddr = data[0]
        self.assertEqual(b"TEST", contents)
        sok.sendto(b"ANOTHER TEST", ('localhost', port))
        handleCallback()
        self.assertEqual(2, len(data))
        reactor.calledMethods[0].args[0].close()
        sok.close()

    def testAcceptorWithPrio(self):
        reactor = CallTrace()
        port = PortNumberGenerator.next()
        acc = Acceptor(reactor, port, lambda sok: None, prio=5)
        self.assertEqual('addReader', reactor.calledMethods[0].name)
        self.assertEqual(5, reactor.calledMethods[0].kwargs['prio'])
        acc.close()
