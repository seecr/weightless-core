#!/usr/bin/env python2.5

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