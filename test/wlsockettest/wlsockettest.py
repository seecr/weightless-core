from unittest import TestCase
from wlsocket import WlBaseSocket, WlSocket, WlSelect

class WlSocketTest(TestCase):

	def fileno(self) :return 9999
	def recv(self, size): return ''
	def send(self, data): pass
	def close(self): pass
	def addReader(self,sok): pass
	def removeReader(self,sok): pass

	def testSinkUntilEndOfFile(self):
		sok = WlBaseSocket(self)
		sok.register(self)
		stopped = [None]
		def sink():
			try:
				yield None
			except StopIteration:
				stopped[0] = True
		sok.sink(sink())
		sok.readable()
		self.assertTrue(stopped[0])

	def testLowLevelOpen(self):
		sok = WlSocket('www.google.nl')
		sok.send('GET / HTTP/1.0\n\n')
		data = sok.recv(4096)
		self.assertEquals('HTTP/1.0 302 Found\r\nLocation: http://www.google.nl', data[:50])

	def xtestOpenAndSource(self):
		selector = WlSelect()
		sok = WlSocket('www.cq2.nl', with_status_and_bad_performance = True)
		selector.register(sok)
		data = [None]
		def http_get_handler(path):
			yield 'GET / HTTP/1.0\n\n'
			data[0] = yield None
		status = sok.sink(http_get_handler('/'))
		status.join()
		self.assertEquals('HTTP/1.1 401 Authorization Required', data[0][:35])