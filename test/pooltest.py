#!/usr/bin/env python2.5
## begin license ##
#
#    "Weightless" is a package with a wide range of valuable tools.
#    Copyright (C) 2005, 2006 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of "Weightless".
#
#    "Weightless" is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    "Weightless" is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with "Weightless"; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
#
from unittest import TestCase
from weightless import Pool
from StringIO import StringIO
from threading import Event
import sys
from time import sleep

class PoolTest(TestCase):

	def setUp(self):
		self.pool = Pool()

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

	def testReturnValue(self):
		self.retval = None
		def worker():
			return 'retval'
		def callback(retval):
			self.retval = retval
		self.pool.execute(worker, callback)
		while not self.retval: sleep(0.001)
		self.assertEquals('retval', self.retval)

	def testReturnException(self):
		self.retval = None
		def worker():
			raise Exception('something wrong')
		def callback(retval):
			self.retval = retval
		self.pool.execute(worker, callback)
		while not self.retval: sleep(0.001)
		self.assertEquals("Exception('something wrong',)", repr(self.retval))

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
