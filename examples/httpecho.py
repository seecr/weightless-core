#!/usr/bin/env python2.5

from server import main
from weightless.wlhttp import recvRequest

CRLF = "\r\n"

def sendBody(path):
	

def sinkFactory():
	"""endlessly read and echo back to the client"""
	while 1:
		request = yield recvRequest()
		yield "HTTP/1.1 200 OK" + CRLF +\
					CRLF +\
					"PATH: %s" % request.RequestURI + CRLF + 
		yield sendBody(request.RequestURI)

if __name__ == '__main__':
	main(sinkFactory)