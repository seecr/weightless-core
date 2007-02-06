from __future__ import with_statement

from wltestcase import TestCase
from cq2utils.calltrace import CallTrace
from weightless.wlsocket import WlSelect, WlFileSocket, WlBaseSocket, ReadIteration, WriteIteration
from threading import Event
from time import sleep
from StringIO import StringIO
import sys

def mockSelect(r, w, o):
	sleep(0.00001) # yield CPU, that's what select does normally !!
	return set(r), set(w), set(o)

class WlSelectTest(TestCase):

	def testAddSocketReading(self):
		class Sok:
			def __hash__(self): return 1
		selector = WlSelect()
		mockSok = Sok()
		self.assertTrue(mockSok not in selector._readers)
		selector.add(mockSok)
		self.assertTrue(mockSok in selector._readers)
		selector._readers.remove(mockSok)

	def testAddSocketWriting(self):
		class Sok:
			def __hash__(self): return 1
		selector = WlSelect()
		mockSok = Sok()
		self.assertTrue(mockSok not in selector._writers)
		selector.add(mockSok, 'w')
		self.assertTrue(mockSok in selector._writers)
		selector._writers.remove(mockSok)

	def testAddSocketRaisesException(self):
		class Sok: # raise exception when put into set
			def __hash__(self): raise Exception('aap')
		selector = WlSelect()
		try:
			selector.add(Sok())
			self.fail()
		except Exception, e:
			self.assertEquals('aap', str(e))

	def testReadFile(self):
		wait = Event()
		selector = WlSelect()
		data = [None]
		with self.mktemp('boom vuur vis') as f:
			wlsok = WlFileSocket(f.name)
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
			selector = WlSelect(select_func = mockSelect)
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
			selector = WlSelect(select_func = mockSelect)
			mockSok = CallTrace(returnValues = {'fileno': 999, 'send': 999, 'getsockopt': 999})
			wlsok = WlBaseSocket(mockSok)
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
		selector = WlSelect(select_func = mockSelect)
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