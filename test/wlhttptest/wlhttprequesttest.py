from __future__ import with_statement
from unittest import TestCase
from random import random
from threading import Thread
from time import sleep
from socket import socket

from weightless.wlhttp import WlHttpRequest
from weightless.wlsocket import WlSocket,  WlSelect
from weightless import WlGenerator

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5


from contextlib import contextmanager
@contextmanager
def server(response):
	reqData = []
	port = 2048 + int(random() * 2048.0)
	def server():
		s = socket()
		s.bind(('127.0.0.1', port))
		s.listen(1)
		conn, addr = s.accept()
		reqData.append(conn.recv(4096))
		conn.send(response)
		conn.close()
		s.close()
	t = Thread(None, server)
	t.setDaemon(True)
	t.start()
	sleep(0.001)
	yield reqData, port
	sleep(0.001)
	t.join()


class WlHttpRequestTest(TestCase):

	def testCreateSimple(self):
		req = WlHttpRequest('GET', 'http://aap.noot.nl/mies')
		data = req.next()
		self.assertEquals('GET /mies HTTP/1.1\r\nHost: aap.noot.nl\r\nUser-Agent: Weightless/0.1\r\n\r\n', data)

	def testSupportedMethod(self):
		try:
			req = WlHttpRequest('got', 'http://aap.noot.nl/mies')
			req.next()
			self.fail('Incorrect method must raise assert error.')
		except AssertionError, e:
			self.assertEquals('Method "got" not supported.  Supported are: GET.', str(e))

	def testSupportedScheme(self):
		try:
			req = WlHttpRequest('GET', 'ftp://aap.noot.nl/mies')
			req.next()
			self.fail('Incorrect scheme must raise assert error.')
		except AssertionError, e:
			self.assertEquals('Scheme "ftp" not supported.  Supported are: http.', str(e))

	def testHostHeader(self):
		req = WlHttpRequest('GET', 'http://this.host/path')
		data = req.next()
		self.assertEquals('GET /path HTTP/1.1\r\nHost: this.host\r\nUser-Agent: Weightless/0.1\r\n\r\n', data)

	def testAllIn(self):
		sel = WlSelect()
		req = WlHttpRequest('GET', 'http://this.host/path')
		with server('response') as (request, port):
			sok = WlSocket('localhost', port)
			sok.sink(req, sel)
		self.assertEquals(['GET /path HTTP/1.1\r\nHost: this.host\r\nUser-Agent: Weightless/0.1\r\n\r\n'], request)

	def testResponse(self):
		bodyLines = []
		def bodyHandler():
			bodyLines.append((yield None))
		sel = WlSelect()
		req = WlHttpRequest('GET', 'http://this.host/path')
		with server('response\r\n') as (request, port):
			sok = WlSocket('localhost', port)
			sok.sink(WlGenerator(h for h in [req, bodyHandler()]), sel)
		self.assertEquals('response\r\n', bodyLines[0])