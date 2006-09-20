#!/usr/bin/python2.5

import unittest

from wlsocket import WlSocket

class WlSocketTest(unittest.TestCase):

	def fileno(self) :return 0
	def recv(self, size): return ''
	def close(self): pass
	def addReader(self,sok): pass
	def removeReader(self,sok): pass

	def testSinkUntilEndOfFile(self):
		sok = WlSocket(self)
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


if __name__ =='__main__':
	unittest.main()