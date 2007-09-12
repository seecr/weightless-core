#!/usr/bin/env python2.5
## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
#
from __future__ import with_statement

from testcase import TestCase
from cq2utils.calltrace import CallTrace
from weightless import Select, Socket
from weightless._select import ReadIteration, WriteIteration
from threading import Event, Semaphore
from time import sleep
from StringIO import StringIO
import sys

def mockSelect(r, w, o):
	sleep(0.00001) # yield CPU, that's what select does normally !!
	return set(r), set(w), set(o)

class SelectTest(TestCase):

	def testAddSocketReading(self):
		class Sok:
			def __hash__(self): return 1
		selector = Select()
		mockSok = Sok()
		self.assertTrue(mockSok not in selector._readers)
		selector.add(mockSok)
		self.assertTrue(mockSok in selector._readers)
		selector._readers.remove(mockSok)

	def testAddSocketWriting(self):
		class Sok:
			def __hash__(self): return 1
		selector = Select()
		mockSok = Sok()
		self.assertTrue(mockSok not in selector._writers)
		selector.add(mockSok, 'w')
		self.assertTrue(mockSok in selector._writers)
		selector._writers.remove(mockSok)

	def testAddSocketRaisesException(self):
		class Sok: # raise exception when put into set
			def __hash__(self): raise Exception('aap')
		selector = Select()
		try:
			selector.add(Sok())
			self.fail()
		except Exception, e:
			self.assertEquals('aap', str(e))

	def testReadFile(self):
		wait = Event()
		selector = Select()
		data = [None]
		with self.mktemp('boom vuur vis') as f:
			wlsok = Socket(f.name)
			self.assertFalse(wlsok in selector._readers)
			def sink():
				data[0] = yield None
				wait.set()
			status = wlsok.sink(sink(), selector)
			self.assertTrue(wlsok in selector._readers)
		wait.wait()
		self.assertFalse(wlsok in selector._readers)
		self.assertEquals('boom vuur vis', data[0])

	def testRemoveFromREADERSWhenExceptionIsRaised(self):
		tmp = sys.stderr
		try:
			sys.stderr = StringIO() # suppress error messages
			f = Event()
			def mockSelect(r, w, o):
				f.wait()
				f.clear()
				return set(r), set(w), set(o)
			selector = Select(select_func = mockSelect)
			wlsok = CallTrace(returnValues = {'fileno': 999, 'send': 999, 'getsockopt': 999, '__hash__': 1})
			wlsok.exceptions['readable'] = Exception()
			selector.add(wlsok)
			f.set()
			sleep(0.0001)
			self.assertTrue(wlsok not in selector._readers)
			self.assertEquals('close()', str(wlsok.calledMethods[-2]))
		finally:
				sys.stderr = tmp

	def testRemoveFromWRITERSWhenExceptionIsRaised(self):
		tmp = sys.stderr
		try:
			sys.stderr = StringIO()
			selector = Select(select_func = mockSelect)
			mockSok = CallTrace(returnValues = {'fileno': 999, 'send': 999, 'getsockopt': 999})
			wlsok = Socket(mockSok)
			def sink():
				yield 'data to send'
				raise Exception('oops')
			wlsok.sink(sink(), selector)
			sleep(0.01)
			self.assertTrue(wlsok not in selector._writers)
			self.assertTrue(wlsok not in selector._readers)
			self.assertEquals('close()', str(mockSok.calledMethods[-1]))
		finally:
				sys.stderr = tmp

	def testWriteIterationException(self):
		f = Event()
		def mockSelect(r, w, o):
			f.wait()
			f.clear()
			return set(r), set(w), set(o)
		class MockSok:
			def readable(self): raise WriteIteration()
			def writable(self): raise ReadIteration()
		selector = Select(select_func = mockSelect)
		wlsok = MockSok()
		selector.add(wlsok)
		self.assertTrue(wlsok in selector._readers)
		self.assertTrue(wlsok not in selector._writers)
		f.set()
		sleep(0.01)
		self.assertTrue(wlsok not in selector._readers)
		self.assertTrue(wlsok in selector._writers)
		f.set()
		sleep(0.01)
		self.assertTrue(wlsok in selector._readers)
		self.assertTrue(wlsok not in selector._writers)
		f.set()
		sleep(0.01)
		self.assertTrue(wlsok not in selector._readers)
		self.assertTrue(wlsok in selector._writers)

	def testGlobalReactor(self):
		flag = Event()
		selector = Select(select_func = mockSelect)
		class MockSok:
			def readable(inner):
				self.assertEquals(selector, __reactor__)
				flag.set()
			def close(inner): pass
		sok1 = MockSok()
		selector.add(sok1, 'r')
		flag.wait()
		self.assertTrue(__reactor__)

	def testCurrent(self):
		selector = Select(select_func = mockSelect)
		class MockSok:
			def __init__(self):
				self.flag = Event()
			def readable(self):
				self.current = __current__
				self.flag.set()
			def writable(self):
				self.current = __current__
				self.flag.set()
			def close(self): pass
		sok1 = MockSok()
		sok2 = MockSok()
		selector.add(sok1, 'r')
		selector.add(sok2, 'w')
		sok1.flag.wait()
		sok2.flag.wait()
		self.assertEquals(sok1, sok1.current)
		self.assertEquals(sok2, sok2.current)
