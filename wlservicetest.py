import unittest, os, sys, threading, socket

import wlservice

PORT = 7653

class WlServiceTest(unittest.TestCase):

	def tearDown(self):
		global PORT
		PORT = PORT + 1

	def testCreateService(self):
		service = wlservice.create()
		self.assertEquals('wlservice:localhost:80', str(service))
		service = wlservice.create('cq2.org', 8080, 'testservice')
		self.assertEquals('testservice:cq2.org:8080', str(service))

	def testStartService(self):
		service = wlservice.create('localhost', PORT)
		service.listen(None)
		self.assertEquals(0, os.system('netstat --ip --listening | grep localhost.*%d>/dev/null' % PORT))

	def runInThread(self, function):
		serviceThread = threading.Thread(None, function)
		serviceThread.start()
		return serviceThread

	def testConnect(self):
		accept = [None]
		def acceptor(sock, host):
			accept[0] = 'y'
			return (None for x in [])
		service = wlservice.create('localhost', PORT)
		service.listen(acceptor)
		serviceThread = self.runInThread(service.select)
		soc = socket.socket()
		soc.connect(('localhost', PORT))
		serviceThread.join()
		self.assertEquals('y', accept[0])

	def testSendData(self):
		recv = [None]
		def produmer(sock, host):
			recv[0] = yield -1
		def acceptor(sock, host):
			return produmer(sock, host)
		service = wlservice.create('localhost', PORT)
		service.listen(acceptor)
		serviceThread = self.runInThread(service.select)
		soc = socket.socket()
		soc.connect(('localhost', PORT))
		serviceThread.join()
		serviceThread = self.runInThread(service.select)
		response = soc.send('hello there!')
		serviceThread.join()
		self.assertEquals('hello there!', recv[0])


if __name__ == '__main__':
	unittest.main()