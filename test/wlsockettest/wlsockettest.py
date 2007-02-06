from __future__ import with_statement

from unittest import TestCase
from weightless.wlsocket import WlSocket, WlBaseSocket, ReadIteration, WriteIteration
from cq2utils.calltrace import CallTrace
from select import select
from socket import gaierror

class WlSocketTest(TestCase):

	def testCreateSocketGetsReceiveBufferSizeFromSocketItself(self):
		socket = CallTrace()
		socket.returnValues['getsockopt'] = 98765  # kernel reports twice the size
		sok = WlBaseSocket(socket)
		self.assertEquals('getsockopt(1, 8)', str(socket.calledMethods[0]))
		sok._recv()
		self.assertEquals('recv(49382)', str(socket.calledMethods[1]))

	def testSocketClose(self):
		socket = CallTrace(returnValues={'getsockopt':10})
		sok = WlBaseSocket(socket)
		sok.close()
		self.assertEquals('close()', str(socket.calledMethods[1]))

	def testSinkNonGenerator(self):
		try:
			WlBaseSocket(CallTrace(returnValues={'getsockopt':4096})).sink('wrong', None)
		except TypeError, e:
			self.assertEquals('need generator', str(e))

	def testAddingExhaustedGeneratorRaisesException(self):
		sok = WlBaseSocket(CallTrace(returnValues={'getsockopt':10}))
		try:
			sok.sink((i for i in []), None)
			self.fail()
		except ValueError, e:
			self.assertEquals('useless generator: exhausted at first next()', str(e))

	def testSink(self):
		socket = CallTrace(returnValues={'getsockopt':10})
		socket.returnValues['recv'] = 'aap noot mies'
		sok = WlBaseSocket(socket)
		data = [None]
		def generator():
			data[0] = yield None
			data[1] = yield None
		sok.sink(generator(), CallTrace())
		sok.readable()
		self.assertEquals('aap noot mies', data[0])

	def testThrowStopIterationWhenEndOfFile(self):
		sok = WlBaseSocket(CallTrace(returnValues = {'recv': '', 'getsockopt':4096}))
		stopped = [None]
		def sink():
			try:
				yield None
			except StopIteration:
				stopped[0] = True
			yield None
		sok.sink(sink(), CallTrace())
		sok.readable()
		self.assertTrue(stopped[0])

	def testStartWithReading(self):
		sok = WlBaseSocket(CallTrace(returnValues={'getsockopt':10}))
		mockSelect = CallTrace()
		sok.sink((x for x in [None]), mockSelect)
		self.assertEquals("add(<weightless.wlsocket.wlbasesocket.WlBaseSocket>, 'r')", str(mockSelect.calledMethods[0]))

	def testStartWithWriting(self):
		sok = WlBaseSocket(CallTrace(returnValues={'getsockopt':10}))
		mockSelect = CallTrace()
		sok.sink((x for x in ['data']), mockSelect)
		self.assertEquals("add(<weightless.wlsocket.wlbasesocket.WlBaseSocket>, 'w')", str(mockSelect.calledMethods[0]))

	def testReadDataFromSocketAndSendToGenerator(self):
		mockSok = CallTrace(returnValues={'getsockopt':10})
		sok = WlBaseSocket(mockSok)
		data = []
		def collect():
			while True:
				received = yield None
				data.append(received)
		sok.sink(collect(), CallTrace())
		mockSok.returnValues['recv'] = 'aap'
		sok.readable()
		self.assertEquals('aap', data[0])
		mockSok.returnValues['recv'] = 'noot'
		sok.readable()
		self.assertEquals('noot', data[1])

	def testGetDataFromGeneratorAndSendToSocket(self):
		mockSok = CallTrace(returnValues = {'send': 999, 'getsockopt': 10})
		sok = WlBaseSocket(mockSok)
		sok.sink((data for data in ['aap', 'noot', 'mies']), CallTrace())
		sok.writable()
		sok.writable()
		self.assertEquals("send('aap')", str(mockSok.calledMethods[1]))
		self.assertEquals("send('noot')", str(mockSok.calledMethods[2]))

	def testSwitchFromReadingToWriting(self):
		mockSok = CallTrace(returnValues = {'send': 999, 'recv': 'keep things going', 'getsockopt': 10})
		sok = WlBaseSocket(mockSok)
		mockSelect = CallTrace()
		sok.sink((data for data in [None, 'data to write', 'more', None, None, 'even more to write']), mockSelect)
		self.assertEquals("add(<weightless.wlsocket.wlbasesocket.WlBaseSocket>, 'r')", str(mockSelect.calledMethods[0]))
		try:
			sok.readable()
			self.fail()
		except WriteIteration:
			self.assertEquals('recv(5)', str(mockSok.calledMethods[1]))
		sok.writable()
		self.assertEquals("send('data to write')", str(mockSok.calledMethods[2]))
		try:
			sok.writable()
			self.fail()
		except ReadIteration:
			self.assertEquals("send('more')", str(mockSok.calledMethods[3]))
		sok.readable()
		self.assertEquals('recv(5)', str(mockSok.calledMethods[4]))
		try:
			sok.readable()
			self.fail()
		except WriteIteration:
			self.assertEquals('recv(5)', str(mockSok.calledMethods[5]))
		try:
			sok.writable()
			self.fail()
		except StopIteration:
			pass

	def testSendDidNotSendAllData(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10})
		sok = WlBaseSocket(mockSok)
		sok.sink((data for data in ['send in chunks', 'more', 'and more']), CallTrace())
		sok.writable()
		self.assertEquals("send('send in chunks')", str(mockSok.calledMethods[1]))
		sok.writable()
		self.assertEquals("in chunks", str(mockSok.calledMethods[2].arguments[0]))
		sok.writable()
		self.assertEquals("unks", str(mockSok.calledMethods[3].arguments[0]))
		sok.writable()
		self.assertEquals("more", str(mockSok.calledMethods[4].arguments[0]))

	def testFromOneSocketToTheOther(self):
		def thisIsHowYouCanUseDifferentSocketsInOneGenerator(sokje):
			requestedFile = yield None
			yield 'header'
			source = yield wlopen('/tmp/somefile')	# A: open a socket
			with source:													# B: replace implicit socket in __enter__
				yield 'GET / HTTP/1.1'									# C: yield to new socket
																					# D: restore old socket in __exit__
			while True:
				with source:
					data = yield None
				yield data
			yield 'trailer'

	def testConnectAsync(self):
		s = WlSocket('www.cq2.nl', 80) # async connect
		counter = 0
		while not select([], [s], [], 0)[1]:
			counter += 1
		self.assertTrue(counter > 1, counter) # it easily counts to 2000 when async

	def testAsyncConnectWithUnknownHost(self):
		try:
			s = WlSocket('fhfkdieustdjcm.nl', 80) # async connect
			self.fail()
		except gaierror:
			pass
