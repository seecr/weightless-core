from unittest import TestCase
from weightless.wlservice import WlService
from weightless.wlhttp import recvResponse, sendRequest
from weightless.wlcompose import compose
from time import sleep
from socket import socket
from threading import Thread
from random import random

PORT = 2048 + int(random() * 4096.0)

class WlServiceTest(TestCase):

	def tearDown(self):
		global PORT
		PORT = PORT + 1 # trick to avoid 'post already in use'

	def testOpen(self):
		service = WlService()
		def sink(buf):
			data = yield None
			buf.append(data)
		fileContents = []
		service.open('file:wlservicetest.py', sink(fileContents))
		sleep(0.1)
		self.assertEquals('from unittest import', fileContents[0][:20])

	def testListen(self):
		service = WlService()
		recv = []
		def handler():
			data = yield None
			recv.append(data)
			yield 'Response'
		service.listen('localhost', PORT, handler)
		def client():
			soc = socket()
			soc.connect(('localhost', PORT))
			soc.send('GET / HTTP/1.0\n\n')
			response = soc.recv(4096)
			self.assertEquals('Response', response)
			soc.close()
		thread = Thread(None, client)
		thread.start()
		thread.join()
		sleep(0.001)
		self.assertEquals(['GET / HTTP/1.0\n\n'], recv)

	def testOpenHTTP(self):
		codes = []
		def handler():
			yield sendRequest('GET', 'http://www.cq2.org/')
			response = yield recvResponse()
			codes.append(response)
		service = WlService()
		service.open('http://www.cq2.org:80', compose(handler()))
		sleep(0.1)
		self.assertEquals('302', codes[0].StatusCode)