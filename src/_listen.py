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
from socket import socket, SOL_SOCKET, SO_REUSEADDR, SO_LINGER, \
	SHUT_RDWR, SOL_TCP, TCP_CORK
from wlserversocket import WlServerSocket
from traceback import print_exc


BACKLOG = 1

class WlListen:

	def __init__(self, hostname, port, acceptor):
		self._sok = socket()
		self._sok.bind((hostname, port))
		self._sok.listen(BACKLOG)
		self._sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self._acceptor = acceptor
		self.fileno = self._sok.fileno

	def readable(self):
		#try:
		#sok, (host, port) =
		sok = self._sok.accept()[0]
		#sok.setsockopt(SOL_TCP, TCP_CORK, 1)
		sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self._acceptor(WlServerSocket(sok))
		#except Exception, e:
		#	print_exc()

	def close(self):
		self._sok.shutdown(SHUT_RDWR)
		self._sok.close()
