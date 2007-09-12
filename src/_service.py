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
from weightless import Socket, Select, compose
from urlparse import urlsplit
from weightless import compose

class WlService:
	def __init__(self, selector = None):
		self._selector = selector or WlSelect()

	def open(self, url, sink = None):
		addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
		if addressing_scheme == 'file':
			wlsok = WlFileSocket(path)
		else:
			hostPort = network_location.split(':')
			host = hostPort[0]
			port = 80
			if len(hostPort) > 1:
				port = int(hostPort[1])
			wlsok = WlSocket(host, port)
		if sink:
			wlsok.sink(compose(sink), self._selector)
		else:
			return wlsok

	def listen(self, host, port, sinkFactory = None):
		def acceptor(wlsok):
			wlsok.sink(compose(sinkFactory()), self._selector)
		wlistener =  WlListen(host, port, acceptor)
		self._selector.add(wlistener, 'r')
		return wlistener

	def stop(self):
		self._selector.stop()
