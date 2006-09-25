#!/usr/bin/python2.5

from unittest import TestCase, main
from wlthreadpool import Pool
from StringIO import StringIO
from threading import Event
import sys

class WlThreadPoolTest(TestCase):

	def setUp(self):
		self.pool = Pool(with_status_and_bad_performance=True)

	def tearDown(self):
		self.pool.shutdown()

	def testOne(self):
		result = []
		def worker():
			result.append('aap')
			yield None
			result.append('noot')
		status = self.pool.execute(worker())
		status.wait()
		self.assertEquals(['aap','noot'], result)

	def testWrongInput(self):
		try:
			self.pool.execute(None)
			self.fail()
		except TypeError, e:
			self.assertEquals('execute() expects a generator', str(e))

	def testStatus(self):
		wait = Event()
		def worker():
			yield None
			wait.wait()
		status = self.pool.execute(worker())
		self.assertFalse(status.isSet())
		wait.set()
		status.wait()
		self.assertTrue(status.isSet())

	def testStatusWithException(self):
		def raiseException():
			yield None
			raise Exception('oops')
		saved_stderr = sys.stderr
		sys.stderr = StringIO()
		try:
			status = self.pool.execute(raiseException())
			try:
				status.sync()
				self.fail()
			except Exception, e:
				self.assertEquals('oops', str(e))
		finally:
			sys.stderr = saved_stderr

	def testExceptionInThreadIsAnnotatedWithThreadThatStartedTheThread(self):
		saved_stderr = sys.stderr
		sys.stderr = StringIO()
		try:
			def raiseA(): raise Exception('some exception')
			def raiseB(): raiseA()
			def raiseC():
				yield None
				raiseB()
			status = self.pool.execute(raiseC())
			status.wait()
		finally:
			txt = sys.stderr.getvalue().split('\n')
			self.assertEquals('A thread created at (unittest calls filtered out):', txt[0])
			self.assertTrue('wlthreadpooltest.py' in txt[1] or 'alltests.py' in txt[1])
			self.assertTrue('main()' in txt[2])
			self.assertTrue('testExceptionInThreadIsAnnotatedWithThreadThatStartedTheThread' in txt[3])
			self.assertTrue('execute(raiseC())' in txt[4])
			self.assertEquals('raised the following exception:', txt[6])
			self.assertEquals('Traceback (most recent call last):', txt[7])
			self.assertTrue('in raiseB' in txt[8])
			self.assertTrue('def raiseB(): raiseA()' in txt[9])
			self.assertTrue('in raiseA' in txt[10])
			self.assertTrue("def raiseA(): raise Exception('some exception')" in txt[11])
			self.assertEquals('Exception: some exception', txt[12])
			sys.stderr = saved_stderr

if __name__ == '__main__': main()