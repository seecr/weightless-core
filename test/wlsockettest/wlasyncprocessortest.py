from unittest import TestCase
from cq2utils.calltrace import CallTrace
from weightless.wlsocket import WlBaseSocket, WlAsyncProcessor, SuspendIteration
from weightless.wlsocket import WlSelect
from threading import Event
from time import sleep

class WlAsyncProcessorTest(TestCase):

	def testGeneratorImmediatelyYieldAsyncProcessorAndTheSocketIsSuspended(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10, 'recv': 'indata'})
		sok = WlBaseSocket(mockSok)
		mockSelect = CallTrace()
		def handlerUsingAsyncProcessor():
			yield WlAsyncProcessor()
		sok.sink(handlerUsingAsyncProcessor(), mockSelect)
		self.assertEquals([], mockSelect.calledMethods) # i.e. no add called

	def testSuspendWhenYieldingAsyncProcessorWhileReading(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10, 'recv': 'indata'})
		sok = WlBaseSocket(mockSok)
		mockSelect = CallTrace()
		def handlerUsingAsyncProcessor():
			yield None
			yield WlAsyncProcessor()
		sok.sink(handlerUsingAsyncProcessor(), mockSelect)
		try:
			sok.readable() # what wlselect normally does
			self.fail('must raise suspend _iteration exception')
		except SuspendIteration, e:
			pass

	def testSuspendWhenYieldingAsyncProcessorWhileWriting(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10, 'recv': 'indata'})
		sok = WlBaseSocket(mockSok)
		mockSelect = CallTrace()
		def handlerUsingAsyncProcessor():
			yield 'send this'
			yield WlAsyncProcessor()
		sok.sink(handlerUsingAsyncProcessor(), mockSelect)
		try:
			sok.writable() # first send 'send this'
			sok.writable() # what wlselect normally does
			self.fail('must raise suspend _iteration exception')
		except SuspendIteration, e:
			pass

	def testStartAsyncOperation(self):
		sok = WlBaseSocket(CallTrace(returnValues = {'send': 5, 'getsockopt':10, 'recv': 'indata'}))
		started = []
		class MyAsyncProcessor(WlAsyncProcessor):
			def start(self, sokket):
				started.append(True)
		def myHandler():
			yield MyAsyncProcessor()
		sok.sink(myHandler(), CallTrace())
		self.assertTrue(started[0])
		def readHandler():
			yield None
			yield MyAsyncProcessor()
		sok.sink(readHandler(), CallTrace())
		try:
			sok.readable()
			self.fail()
		except SuspendIteration:
			self.assertTrue(started[1])
		def writeHandler():
			yield 'write'
			yield MyAsyncProcessor()
		sok.sink(writeHandler(), CallTrace())
		try:
			sok.writable()
			self.fail()
		except SuspendIteration:
			self.assertTrue(started[2])

	def testCompletion(self):
		flag = Event()
		work = []
		class MyAsyncProcessor(WlAsyncProcessor):
			def process(self):
				work.append('work')
		asyncp = MyAsyncProcessor()
		class MockSok:
			def async_completed(self, retval):
				flag.set()
		asyncp.start(MockSok())
		flag.wait()
		self.assertEquals('work', work[0])

	def testStartAndComplete(self):
		def mock_select(r,w,o):
			sleep(0.01) # Mimic thread suspend that select does
			return set(r), set(w), set(o)
		selector = WlSelect(mock_select)
		done = Event()
		class MyAsyncWriter(WlAsyncProcessor):
			def process(self):
				self.wlsok.send('in between')
		def startAndCompleteAsyncOperation():
			yield 'something to write'
			whatIsItIGetBack = yield MyAsyncWriter()
			yield 'more to write'
			done.set()
		mockSok = CallTrace(returnValues = {'send': 999, 'getsockopt': 999, 'recv': 'indata'})
		sok = WlBaseSocket(mockSok)
		sok.sink(startAndCompleteAsyncOperation(), selector)
		done.wait()
		self.assertEquals("send('something to write')", str(mockSok.calledMethods[1]))
		self.assertEquals("send('in between')", str(mockSok.calledMethods[2]))
		self.assertEquals("send('more to write')", str(mockSok.calledMethods[3]))
