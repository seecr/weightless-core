#!/usr/bin/python2.5
from __future__ import with_statement
from contextlib import contextmanager

import unittest, os, sys, threading, socket

from wlservice import WlService

PORT = 7653


class WlServiceTest(unittest.TestCase):

	def xtearDown(self):
		global PORT
		PORT = PORT + 1 # trick to avoid 'post already in use'

	def testCreateService(self):
		service = WlService()
		def sink(buf):
			data = yield None
			buf.append(data)
		fileContents = []
		wlFileSok = service.open('file:wlservicetest.py', sink(fileContents))
		from time import sleep
		sleep(0.1)
		self.assertEquals('#!/usr/bin/python2.5', fileContents[0][:20])




	def xtestSendData(self):
		recv = []
		def produmer(sock, host):
			while True:
				data = yield ''
				recv.append(data)
		def acceptor(sock, host):
			return produmer(sock, host)
		service = wlservice.create('localhost', PORT)
		service.listen(acceptor)
		with runInThread(service.select):
			soc = socket.socket()
			soc.connect(('localhost', PORT))
		with runInThread(service.select):
			soc.send((wlservice.BUFFSIZE + 10) * 'A')
		self.assertEquals(wlservice.BUFFSIZE, len(recv[0]))
		with runInThread(service.select): pass
		self.assertEquals(10 * 'A', recv[1])


if __name__ == '__main__':
	unittest.main()