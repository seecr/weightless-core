#!/usr/bin/env python2.5

"""
This is a simple Echo server that uses the HTTP Protocol to communicate.
The "recvRequest" call is capable of parsing HTTP request and will yield
a dictionary-like object containing the RequestURI, the HTTPVersion and the
headers sent with the request.
"""

from server import main
from weightless.wlhttp import recvRequest

CRLF = "\r\n"

def sendBody(path):
	result = "PATH: %s" % path
	yield "HTTP/1.1 200 OK" + CRLF + \
				"Content-Length: %s" % len(result) + CRLF +\
				CRLF + \
				result
	
def sinkFactory():
	"""endlessly read and echo back to the client"""
	while 1:
		request = yield recvRequest()
		yield sendBody(request.RequestURI)

if __name__ == '__main__':
	main(sinkFactory)