# -*- coding: utf-8 -*-
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

from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, AF_INET, SOCK_DGRAM
from struct import pack


class Acceptor(object):
    """Listens on a port for incoming UDP packets and calls a factory to create a handler for it.  It does not use threads but a asynchronous reactor instead."""

    def __init__(self, reactor, port, sinkFactory, prio=None, sok=None):
        """The reactor is a user specified reactor for dispatching I/O events asynchronously. The sinkFactory is called with the socket as its single argument. It is supposed to return a callable callback function that is called by the reactor when data is available."""
        self._reactor = reactor
        self._sok = sok or createSocket(port)
        sink = sinkFactory(self._sok)
        reactor.addReader(self._sok, sink, prio=prio)

    def close(self):
        self._sok.close()

    def shutdown(self):
        self._reactor.removeReader(self._sok)
        self.close()


def createSocket(port):
    sok = socket(AF_INET, SOCK_DGRAM)
    sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
    sok.bind(('0.0.0.0', port))
    return sok
