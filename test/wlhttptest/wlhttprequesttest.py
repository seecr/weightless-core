from unittest import TestCase
from random import random
from threading import Thread
from time import sleep
from socket import socket

from weightless import WlHttpRequest
from weightless.wlsocket import WlSocket,  WlSelect

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5

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
		reqData = []
		port = 2048 + int(random() * 2048.0)
		def server():
			s = socket()
			s.bind(('127.0.0.1', port))
			s.listen(1)
			conn, addr = s.accept()
			reqData.append(conn.recv(4096))
			conn.send('response\n\n')
			conn.close()
			s.close()
		t = Thread(None, server)
		t.setDaemon(True)
		t.start()
		sleep(0.1)
		req = WlHttpRequest('GET', 'http://this.host/path')
		sok = WlSocket('localhost', port)
		sok.sink(req, sel)
		sleep(0.1)
		self.assertEquals(['GET /path HTTP/1.1\r\nHost: this.host\r\nUser-Agent: Weightless/0.1\r\n\r\n'], reqData)
