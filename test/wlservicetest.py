from __future__ import with_statement
from contextlib import contextmanager

import unittest, os, sys, threading, socket

from wlservice import WlService

PORT = 7653

@contextmanager
def runInThread(function):
	serviceThread = threading.Thread(None, function)
	serviceThread.start()
	yield serviceThread
	serviceThread.join()

class WlServiceTest(unittest.TestCase):

	def xtearDown(self):
		global PORT
		PORT = PORT + 1 # trick to avoid 'post already in use'

	def testCreateService(self):
		"""		def sink(buf):
			buf += yield None
create service: create thread pool, and run select loop"""
		service = WlService()
		wlFileSok = service.open('file:///home/erik/development/wlservicetest.py')
		fileContents = ''
		wlFileSok.sink(sink(fileContents))
		self.assertEquals('', fileContents)


	def xtestStartService(self):
		service = wlservice.create('localhost', PORT)
		service.listen(None)
		self.assertEquals(0, os.system('netstat --ip --listening | grep localhost.*%d>/dev/null' % PORT))


	def xtestConnect(self):
		accept = [None]
		def acceptor(sock, host):
			accept[0] = 'y'
			return (None for x in [])
		service = wlservice.create('localhost', PORT)
		service.listen(acceptor)
		with runInThread(service.select):
			soc = socket.socket()
			soc.connect(('localhost', PORT))
		self.assertEquals('y', accept[0])

	def xtestSendData(self):
		recv = []
		def produmer(sock, host):
			while True:
				data = yield -1
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