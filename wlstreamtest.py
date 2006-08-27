import unittest
from wlstream import WlStream
from wlthread import WlThread
from wlselect import READ
import re

class MockSock:
	def __init__(self, buff, fd = 10):
		self.buff = buff
		self.fd = 10
	def recv(self, bufsize):
		return self.buff
	def fileno(self):
		return self.fd

class WlStreamTest(unittest.TestCase):

	def socketHandler(self, stream):
		# example handler to be supported by wlstream
		query = yield stream.read('query=(\w+)')
		yield '==>' + query + ' has 987 results'

	def testThisIsHowItIsMeantToBeUsed(self):
		stream = WlStream(MockSock('/cgi-bin?query=panic&option=full'))
		thread = WlThread(self.socketHandler(stream))
		result = thread.run() # init
		result = thread.run(result) # read()
		result = thread.run(result) # socketHandler
		self.assertEquals('==>query=panic has 987 results', result)

	def testDelegateToSocket(self): #deprecated
		wls = WlStream(MockSock('aap\nnoot\n'))
		fd = wls.fileno()
		self.assertEquals(10, fd)

	def testReadlineLowLevel(self):
		wls = WlStream(MockSock('aap\nnoot\n'))
		rl = WlThread(wls.readline())
		rl.run()
		response = rl.run()
		self.assertEquals('aap\n', response)
		rl = WlThread(wls.readline())
		response = rl.run()
		self.assertEquals('noot\n', response)

	def testReadlineWithNotEnoughData(self):
		mock = MockSock('aap')
		s = WlStream(mock)
		wlt = WlThread(s.readline())
		response = wlt.run()
		self.assertEquals((READ, 10), response)
		response = wlt.run()
		self.assertEquals((READ, 10), response)
		mock.buff = '\n'
		response = wlt.run()
		try:
			wlt.run()
			self.fail()
		except StopIteration:
			self.assertEquals('aap\n', response)

	def testReadAdvanceReadPointer(self):
		s = WlStream(MockSock('aap\nnoot\nmies\n'))
		wlt = WlThread(s.readline())
		response = wlt.run() # give it a chance to read data
		self.assertEquals((READ, 10), response)
		response = wlt.run()
		self.assertEquals('aap\n', response)
		response = WlThread(s.readline()).run()
		self.assertEquals('noot\n', response)
		response = WlThread(s.readline()).run()
		self.assertEquals('mies\n', response)

	def testReadMultiLine(self):
		s = WlStream(MockSock('aap\nnoot\nmies\n'))
		wlt = WlThread(s.read('.*noo(.*)ies.*'))
		wlt.run() # init
		response = wlt.run()
		self.assertEquals('aap\nnoot\nmies\n', response)
		self.assertEquals(('t\nm',), s.match())

	def testReadRegexp(self):
		s = WlStream(MockSock('aap:1\nnoot:2\nmies:3\ntail'))
		wlt = WlThread(s.read('(\w+):(\d)\n'))
		wlt.run()
		response = wlt.run()
		self.assertEquals('aap:1\n', response)
		self.assertEquals(('aap', '1'), s.match())
		self.assertEquals('noot:2\n', WlThread(s.read('(\w+):(\d)\n')).run())
		self.assertEquals(('noot', '2'), s.match())
		self.assertEquals('mies:3\n', WlThread(s.read('(\w+):(\d)\n')).run())
		self.assertEquals(('mies', '3'), s.match())
		self.assertEquals((READ, 10), WlThread(s.read('(\w+):(\d)\n')).run())

	def testReadWithCompiledRe(self):
		labelRe = re.compile('(?s).*(noot).*')
		s = WlStream(MockSock('aap:1\nnoot:2\nmies:3\n'))
		wlt = WlThread(s.read(labelRe))
		wlt.run()
		response = wlt.run()
		self.assertEquals('aap:1\nnoot:2\nmies:3\n', response)
		self.assertEquals(('noot',), s.match())

if __name__ == '__main__':
	unittest.main()