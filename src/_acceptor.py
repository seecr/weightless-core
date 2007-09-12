## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
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
from socket import socket

class Acceptor(object):
    """Listens on a port for incoming internet (TCP/IP) connections and calls a factory to create a handler for the new connection.  It does not use threads but a asynchronous reactor instead."""

    def __init__(self, reactor, port, sinkFactory):
        """The reactor is a user specified reactor for dispatching I/O events asynchronously. The sinkFactory is called with the newly created socket as its single argument. It is supposed to return a callable callback function that is called by the reactor when data is available."""
        sok = socket()
        sok.bind(('0.0.0.0', port))
        sok.listen(1)
        reactor.addReader(sok, self._accept)
        self._sinkFactory = sinkFactory
        self._sok = sok
        self._reactor = reactor

    def _accept(self):
        newConnection, address = self._sok.accept()
        self._reactor.addReader(newConnection, self._sinkFactory(newConnection))
