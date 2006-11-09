from __future__ import with_statement
from contextlib import contextmanager
from unittest import TestCase
from wlsocket import WlListen
from os import system
from threading import Thread
from socket import socket
from wlsocket import WlSocket
from cq2utils.calltrace import CallTrace

PORT = 4500

class WlListenTest(TestCase):

	def setUp(self):
		global PORT
		PORT = PORT + 1

	def testCreate(self):
		s = WlListen('localhost', PORT, None)
		self.assertEquals(0, system('netstat --ip --listening | grep localhost.*%d>/dev/null' % PORT))

	def testConnect(self):
		accept = [None]
		def acceptor(wlsok):
			accept[0] = wlsok
		s = WlListen('localhost', PORT, acceptor)
		def client():
			soc = socket()
			soc.connect(('localhost', PORT))
		thread = Thread(None, client)
		thread.start()
		s.readable() # fake what select does
		thread.join()
		wlsok = accept[0]
		self.assertEquals('127.0.0.1', wlsok.host)
		self.assertTrue(30000 < wlsok.port < 90000, wlsok.port)

	def testHandleConnection(self):
		data = []
		def handler():
			received = yield None
			data.append(received)
		accept = [None]
		def acceptor(wlsok):
			accept[0] = wlsok
			wlsok.sink(handler(), CallTrace())
			try:
				wlsok.readable()
			except StopIteration:
				pass
		s = WlListen('localhost', PORT, acceptor)
		def client():
			soc = socket()
			soc.connect(('localhost', PORT))
			soc.send('GET / HTTP/1.0\n\n')
			soc.close()
		thread = Thread(None, client)
		thread.start()
		s.readable() # fake what select does
		thread.join()
		self.assertEquals('GET / HTTP/1.0\n\n', data[0])

	def testClose(self):
		s = WlListen('localhost', PORT, None)
		s.close()