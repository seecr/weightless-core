from unittest import TestCase
from weightless.wlthread import WlPool
from StringIO import StringIO
from threading import Event
import sys

class WlPoolTest(TestCase):

	def setUp(self):
		self.pool = WlPool(with_status_and_bad_performance=True)

	def tearDown(self):
		self.pool.shutdown()

	def testOne(self):
		result = []
		def worker():
			result.append('aap')
			result.append('noot')
		status = self.pool.execute(worker)
		status.join()
		self.assertEquals(['aap','noot'], result)

	def testWrongInput(self):
		try:
			self.pool.execute(None)
			self.fail()
		except AssertionError, e:
			self.assertEquals('execute() expects a callable', str(e))

	def testStatus(self):
		wait = Event()
		def worker():
			wait.wait()
		status = self.pool.execute(worker)
		self.assertFalse(status.isSet())
		wait.set()
		status.join()
		self.assertTrue(status.isSet())

	def testStatusWithException(self):
		def raiseException():
			raise Exception('oops')
		saved_stderr = sys.stderr
		sys.stderr = StringIO()
		try:
			status = self.pool.execute(raiseException)
			try:
				status.join()
				self.fail()
			except Exception, e:
				self.assertEquals('oops', str(e))
		finally:
			sys.stderr = saved_stderr

	def xtestExceptionInThreadIsAnnotatedWithThreadThatStartedTheThread(self):
		try:
			def raiseA(): raise Exception('some exception')
			def raiseB(): raiseA()
			def raiseC():
				raiseB()
			status = self.pool.execute(raiseC)
			status.join()
			self.fail()
		except:
			f = StringIO()
			status.print_context(f)
			txt = f.getvalue()
			expected = """  File "./alltests.py", line 21, in <module>
    unittest.main()
  File "/home/erik/development/weightless/trunk/test/wlthreadtest/wlpooltest.py", line 66, in testExceptionInThreadIsAnnotatedWithThreadThatStartedTheThread
    status = self.pool.execute(raiseC())
  File "../src/wlthread/wlpool.py", line 43, in execute
    status = self._createStatus()
"""
			self.assertEquals(expected, txt)
