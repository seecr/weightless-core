#!/usr/bin/env python2.5
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

"""
This is a simple Echo server that uses the HTTP Protocol to communicate.
The "recvRequest" call is capable of parsing HTTP request and will yield
a dictionary-like object containing the RequestURI, the HTTPVersion and the
headers sent with the request.
"""

from server import main
from weightless.wlhttp import recvRequest
from weightless.wlhttp.httpspec import HTTP

CRLF = HTTP.CRLF

def sendBody(path, headers):
	result = "PATH: %s" % path + CRLF
	result += CRLF.join((':'.join(items) for items in headers.__dict__.items()))
	result += CRLF 
	yield "HTTP/1.1 200 OK" + CRLF + \
				"Content-Length: %s" % len(result) + CRLF * 2 +\
				result 
	
def sinkFactory():
	"""endlessly read and echo back to the client"""
	#while 1:
	request = yield recvRequest()
	if request:
		if hasattr(request, 'Error'):
			yield sendError()
		else:
			yield sendBody(request.RequestURI, request.headers)

if __name__ == '__main__':
	main(sinkFactory)
