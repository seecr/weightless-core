from unittest import TestCase
from wlsocket import WlBaseSocket
from cq2utils.calltrace import CallTrace

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
		self.assertEquals('addReader(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[0]))

	def testStartWithWriting(self):
		sok = WlBaseSocket(CallTrace(returnValues={'getsockopt':10}))
		mockSelect = CallTrace()
		sok.sink((x for x in ['data']), mockSelect)
		self.assertEquals('addWriter(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[0]))

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
		self.assertEquals('addReader(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[0]))
		sok.readable()
		self.assertEquals('recv(5)', str(mockSok.calledMethods[1]))
		self.assertEquals('removeReader(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[1]))
		self.assertEquals('addWriter(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[2]))
		sok.writable()
		self.assertEquals("send('data to write')", str(mockSok.calledMethods[2]))
		sok.writable()
		self.assertEquals("send('more')", str(mockSok.calledMethods[3]))
		self.assertEquals('removeWriter(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[3]))
		self.assertEquals('addReader(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[4]))
		sok.readable()
		self.assertEquals('recv(5)', str(mockSok.calledMethods[4]))
		sok.readable()
		self.assertEquals('recv(5)', str(mockSok.calledMethods[5]))
		self.assertEquals('removeReader(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[5]))
		self.assertEquals('addWriter(<wlsocket.wlbasesocket.WlBaseSocket>)', str(mockSelect.calledMethods[6]))
		self.assertEquals(7, len(mockSelect.calledMethods))

	def testSendDidNotSendAllData(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10})
		sok = WlBaseSocket(mockSok)
		sok.sink((data for data in ['send in chunks', 'more', 'and more']), CallTrace())
		sok.writable()
		self.assertEquals("send('send in chunks')", str(mockSok.calledMethods[1]))
		sok.writable()
		self.assertEquals("send('in chunks')", str(mockSok.calledMethods[2]))
		sok.writable()
		self.assertEquals("send('unks')", str(mockSok.calledMethods[3]))
		sok.writable()
		self.assertEquals("send('more')", str(mockSok.calledMethods[4]))
