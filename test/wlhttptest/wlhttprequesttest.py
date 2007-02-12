from __future__ import with_statement
from unittest import TestCase
from random import random
from threading import Thread
from time import sleep
from socket import socket

from weightless.wlhttp import sendRequest, recvRequest, MAX_REQUESTLENGTH, WlHttpException
from weightless.wlhttp.httpspec import HTTP, svnRevision
from weightless.wlsocket import WlSocket,  WlSelect
from weightless.wlcompose import compose, RETURN
from weightless.wldict import WlDict

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5

CRLF = HTTP.CRLF

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
	sleep(0.01)
	yield reqData, port
	sleep(0.01)
	t.join()


class WlHttpRequestTest(TestCase):

	def testCreateSimple(self):
		req = sendRequest('GET', 'http://aap.noot.nl/mies')
		data = req.next()
		self.assertEquals('GET /mies HTTP/1.1\r\nHost: aap.noot.nl\r\nUser-Agent: Weightless/v%s\r\n\r\n' % svnRevision, data)

	def testSupportedMethod(self):
		try:
			req = sendRequest('got', 'http://aap.noot.nl/mies')
			req.next()
			self.fail('Incorrect method must raise assert error.')
		except AssertionError, e:
			self.assertEquals('Method "got" not supported.  Supported are: GET.', str(e))

	def testSupportedScheme(self):
		try:
			req = sendRequest('GET', 'ftp://aap.noot.nl/mies')
			req.next()
			self.fail('Incorrect scheme must raise assert error.')
		except AssertionError, e:
			self.assertEquals('Scheme "ftp" not supported.  Supported are: http.', str(e))

	def testHostHeader(self):
		req = sendRequest('GET', 'http://this.host/path')
		data = req.next()
		self.assertEquals('GET /path HTTP/1.1\r\nHost: this.host\r\nUser-Agent: Weightless/v%s\r\n\r\n' % svnRevision, data)

	def testAllIn(self):
		sel = WlSelect()
		req = sendRequest('GET', 'http://this.host/path')
		with server('response') as (request, port):
			sok = WlSocket('localhost', port)
			sok.sink(req, sel)
		self.assertEquals(['GET /path HTTP/1.1\r\nHost: this.host\r\nUser-Agent: Weightless/v%s\r\n\r\n' % svnRevision], request)

	def testResponse(self):
		bodyLines = []
		def bodyHandler():
			bodyLines.append((yield None))
		sel = WlSelect()
		req = sendRequest('GET', 'http://this.host/path')
		with server('response\r\n') as (request, port):
			sok = WlSocket('localhost', port)
			sok.sink(compose(h for h in [req, bodyHandler()]), sel)
		self.assertEquals('response\r\n', bodyLines[0])

	def testRequest(self):
		generator = recvRequest()
		generator.next()
		generator.send('GET /path HTTP/1.1\r\n')
		opcode, request = generator.send('\r\n')
		self.assertEquals('1.1', request.HTTPVersion)
		self.assertEquals('/path', request.RequestURI)
		self.assertEquals('', request._headers)
		self.assertEquals('GET', request.Method)

	def testRequestWithHeaders(self):
		generator = recvRequest()
		generator.next()
		generator.send('GET /path HTTP/1.1\r\n')
		generator.send('host: we.want.more\r\n')
		generator.send('content-type: text/python\r\n')
		opcode, request = generator.send('\r\n')
		self.assertEquals('host: we.want.more\r\ncontent-type: text/python\r\n', request._headers)
		self.assertEquals('we.want.more', request.headers.Host)
		self.assertEquals('text/python', request.headers.ContentType)

	def testRequestCreatesArgsWhenNotGiven(self):
		generator = recvRequest()
		generator.next()
		opcode, request = generator.send('GET /path HTTP/1.1' + CRLF +'host: we.want.more' + CRLF * 2)
		self.assertEquals('we.want.more', request.headers.Host)

	def testIgnoreStartingCRLF(self):
		generator = recvRequest()
		generator.next()
		opcode, request = generator.send(CRLF * 3 + 'GET /path HTTP/1.1' + CRLF *2)
		self.assertEquals('/path', request.RequestURI)

	def testAllMethodsAreAllowed(self):
		message = WlDict()
		generator = recvRequest(message)
		generator.next()
		result = generator.send('METHOD /path HTTP/1.1' + CRLF + CRLF)
		request = result[1]
		self.assertEquals('METHOD', request.Method)

	def testOtherErrorsAreIgnored(self):
		message = WlDict()
		generator = recvRequest(message)
		generator.next()
		result = generator.send('REQUESTLINE' + CRLF *2)
		self.assertTrue(result == None)
		self.assertEquals({}, message.__dict__)
		try:
			generator.close()
			self.fail()
		except WlHttpException, e:
			pass

	def testStillNoValidRequestAfterEnormousDataRead(self):
		message = WlDict()
		generator = recvRequest(message)
		generator.next()
		try:
			result = generator.send('GOT /path HTTP/1.1' + 'a' * MAX_REQUESTLENGTH + CRLF *2)
		except WlHttpException, e:
			self.assertEquals('Maximum request length exceeded but no sensible headers found.', str(e))