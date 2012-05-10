# -*- coding: utf-8 -*-
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    See http://weightless.io
#    Copyright (C) 2006-2011 Seek You Too (CQ2) http://www.cq2.nl
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
from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, SOL_TCP, TCP_CORK, TCP_NODELAY
from struct import pack

def createSocket(port):
    sok = socket()
    sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sok.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
    sok.bind(('0.0.0.0', port))
    sok.listen(127)
    return sok

class Acceptor(object):
    """Listens on a port for incoming internet (TCP/IP) connections and calls a factory to create a handler for the new connection.  It does not use threads but a asynchronous reactor instead."""

    def __init__(self, reactor, port, sinkFactory, prio=None, sok=None):
        """The reactor is a user specified reactor for dispatching I/O events asynchronously. The sinkFactory is called with the newly created socket as its single argument. It is supposed to return a callable callback function that is called by the reactor when data is available."""

        if sok == None:
            sok = createSocket(port)

        reactor.addReader(sok, self._accept, prio=prio)
        self._sinkFactory = sinkFactory
        self._sok = sok
        self._reactor = reactor
        self._prio = prio

    def _accept(self):
        newConnection, address = self._sok.accept()
        newConnection.setsockopt(SOL_TCP, TCP_CORK, 1)
        #newConnection.setsockopt(SOL_TCP, TCP_NODELAY, 1)
        self._reactor.addReader(newConnection,
            self._sinkFactory(newConnection), prio=self._prio)

    def close(self):
        self._sok.close()

    def shutdown(self):
        self._reactor.removeReader(self._sok)
        self.close()
