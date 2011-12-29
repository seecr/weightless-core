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
from __future__ import with_statement
from socket import socket, SHUT_RDWR, SOL_SOCKET, SOL_TCP, SO_REUSEADDR, SO_LINGER, TCP_CORK, SO_ERROR
from struct import pack
from weightless.core import Observable
from weightless.io import Gio, SocketContext

class Server(Observable):
    def __init__(self, reactor, port):
        Observable.__init__(self)
        ear = socket()
        err = ear.getsockopt(SOL_SOCKET, SO_ERROR)
        if err != 0:    # connection created succesfully?
            raise IOError(err)
        ear.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        ear.setsockopt(SOL_SOCKET, SO_LINGER, pack('ii', 0, 0))
        ear.bind(('0.0.0.0', port))
        ear.listen(127)
        reactor.addReader(ear, self.connect)
        self._ear = ear
        self._reactor = reactor

    def connect(self):
        connection, address = self._ear.accept()
        connection.setsockopt(SOL_TCP, TCP_CORK, 1)
        Gio(self._reactor, self.processConnection(SocketContext(connection)))

    def processConnection(self, connection):
        try:
            with connection:
                yield self.any.processConnection()
        finally:
            connection.shutdown(SHUT_RDWR)
            connection.close()

    def stop(self):
        try:
            self._reactor.removeReader(self._ear)
        except KeyError:
            pass
        self._ear.close()
        self._reactor = None
