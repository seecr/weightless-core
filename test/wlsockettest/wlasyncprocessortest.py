from unittest import TestCase
from cq2utils.calltrace import CallTrace
from weightless.wlsocket import WlBaseSocket, WlAsyncProcessor, SuspendIteration

class WlAsyncProcessorTest(TestCase):

	def testGeneratorImmediatelyYieldAsyncProcessorAndTheSocketIsSuspended(self):
		mockSok = CallTrace(returnValues = {'send': 5, 'getsockopt':10, 'recv': 'indata'})
		sok = WlBaseSocket(mockSok)
		mockSelect = CallTrace()
		def handlerUsingAsyncProcessor():
			yield WlAsyncProcessor()
		sok.sink(handlerUsingAsyncProcessor(), mockSelect)
		#try:
			#sok.readable() # what wlselect normally does
			#self.fail('must raise suspend _iteration exception')
		#except SuspendIteration, e:
			#pass
		# socket must be suspended, i.e., not readable or writable
		self.assertEquals("[add(<weightless.wlsocket.wlbasesocket.WlBaseSocket>, 's')]", str(mockSelect.calledMethods))
