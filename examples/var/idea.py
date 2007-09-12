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
class WlStream:
	pass

class WlIStream(WlStream):
	def sink(generator): pass

class WlOStream(WlStream):
	def source(generator): pass

class WlIOStream(WlIStream, WlOStream):

# low level primitives
wlistream1 = storage.open('file1')
wlostream1 = storage.open('file2', 'w')
wliostream1 = wlsocket.connect('123.456.2.34', 80)

def queue(buff):
	ready = lambda: len(buff) > 0
	while True:
		yield buff.pop()

wlsocket1 = wlsocket.bind('127.0.0.1', 80, accept)

def accept(awlsocket):
	wliostream = awlsocket.accept()
	wliostream.sink(handle_http())

def handle_http():
	request_vars = {}
	yield HTTPRequestParser(request_vars)
	if request_vars['method'] == 'PUT':
		yield storage.open(request_vars['path'], 'w')
	else:
		yield storage.open(request_vars['path'])

class Scope(): pass
g = Scope()
s = Scope(cookie) # only with http!? or from same IP?
def template(g, s, r = Scope())
	g.name = 'server' # remember this globally
	s.user = 'john' # remember this for the session
	r.file = file # remember this for the request (statically)
	yield sub_template(g, s, r)

