from __future__ import with_statement
from unittest import TestCase
from wlthread import WlStatus
from traceback import format_tb
from sys import exc_info
from threading import Event
from cq2utils.calltrace import CallTrace
from StringIO import StringIO

class WlStatusTest(TestCase):

	def testCreateStatus(self):
		status = WlStatus()

	def testJoinWithoutException(self):
		status = WlStatus()
		status.capture(lambda: None)
		try:
			status.join()
		except Exception, e:
			self.fail()

	def testJoinWithException(self):
		status = WlStatus()
		def f(): raise Exception('oops')
		status.capture(f)
		try:
			status.join()
			self.fail()
		except Exception, e:
			self.assertEquals('oops', str(e))

	def testJoinWithExceptionHasCorrectStackTrace(self):
		status = WlStatus()
		def f(): raise Exception('oops')
		def g(): f()
		status.capture(g)
		try:
			status.join()
			self.fail()
		except:
			etype, evalue, etraceback = exc_info()
			self.assertEquals('oops', str(evalue))
			tb_lines = format_tb(etraceback)
			self.assertEquals(', in g\n    def g(): f()\n', tb_lines[1][-24:])

	def testCaptureSignalsEvent(self):
		status = WlStatus()
		self.assertFalse(status._event.isSet())
		status.capture(lambda: None)
		self.assertTrue(status._event.isSet())

	def testJoinWaitsForEvent(self):
		status = WlStatus()
		status._event = CallTrace()
		status.join()
		self.assertTrue('wait', status._event.calledMethods[0].name)

	def testUseAsContext(self):
		status = WlStatus()
		status._event = CallTrace()
		with status:
			raise Exception('oops')
		try:
			status.join()
			self.fail()
		except:
			etype, evalue, etraceback = exc_info()
			self.assertEquals('oops', str(evalue))
			self.assertEquals(2, len(format_tb(etraceback)))
			self.assertTrue('set', status._event.calledMethods[0].name)
			self.assertTrue('wait', status._event.calledMethods[1].name)

	def testGetContext(self):
		status = WlStatus()
		def raiser(): raise Exception('aap')
		status.capture(raiser)
		sink = StringIO()
		status.print_context(sink)
		result = sink.getvalue()
		self.assertEquals('testGetContext\n    status = WlStatus()\n', result[-39:])
		self.assertFalse('unittest.py' in result)

	def testIsSet(self):
		status = WlStatus()
		self.assertFalse(status.isSet())
