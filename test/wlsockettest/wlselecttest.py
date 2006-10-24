from __future__ import with_statement

from wltestcase import TestCase
from cq2utils.calltrace import CallTrace
from wlsocket import WlSelect, WlFileSocket, WlBaseSocket
from threading import Event
from time import sleep

class WlSelectTest(TestCase):

	def testAddSocket(self):
		class Sok: # raise exception when put into set
			def __hash__(self): return 1
		selector = WlSelect()
		mockSok = Sok()
		self.assertTrue(mockSok not in selector._readers)
		selector.addReader(mockSok)
		try:
			self.assertTrue(mockSok in selector._readers)
		finally:
			selector.removeReader(mockSok)

	def testAddSocketRaisesException(self):
		class Sok: # raise exception when put into set
			def __hash__(self): raise Exception('aap')
		selector = WlSelect()
		try:
			selector.addReader(Sok())
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
		wait = Event()
		selector = WlSelect()
		with self.mktemp('aap noot mies') as f:
			wlsok = WlFileSocket(f.name)
			def sink():
				data = yield None  # i.e. read
				wait.set()
			wlsok.sink(sink(), selector)
		wait.wait()
		self.assertTrue(wlsok not in selector._writers)
		self.assertTrue(wlsok not in selector._readers)

	def testRemoveFromWRITERSWhenExceptionIsRaised(self):
		def mockSelect(r, w, o):
			sleep(0.00001) # yield CPU, that's what select does normally !!
			return set(r), set(w), set(o)
		selector = WlSelect(select_func = mockSelect)
		wlsok = WlBaseSocket(CallTrace(returnValues = {'fileno': 999, 'send': 999, 'getsockopt': 999}))
		def sink():
			yield 'data to send'
			raise Exception('oops')
		wlsok.sink(sink(), selector)
		#wlsok.writable()
		sleep(0.01)
		self.assertTrue(wlsok not in selector._writers)
		self.assertTrue(wlsok not in selector._readers)

