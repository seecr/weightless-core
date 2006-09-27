#!/usr/bin/python2.5
from __future__ import with_statement

from unittest import main
from wltestcase import TestCase
from wlselect import WlSelect
from threading import Event
from time import sleep
import wlfile

class WlSelectTest(TestCase):

	def fileno(self): return 9999

	def testAddSocket(self):
		selector = WlSelect()
		mockSok = self
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
			wlsok = wlfile.open(f.name)
			selector.register(wlsok)
			self.assertFalse(wlsok in selector._readers)
			def sink():
				data[0] = yield None
				wait.set()
			status = wlsok.sink(sink())
			self.assertTrue(wlsok in selector._readers)
		wait.wait()
		self.assertFalse(wlsok in selector._readers)
		self.assertEquals('boom vuur vis', data[0])

	def testAddingExhaustedGeneratorRaisesException(self):
		with self.mktemp('aap noot mies') as f:
			sok = wlfile.open(f.name)
			try:
				sok.sink(i for i in [])
				self.fail()
			except ValueError, e:
				self.assertEquals('useless generator: exhausted at first next()', str(e))

	def testRemoveFromReadersWhenGeneratorIsExhausted(self):
		wait = Event()
		selector = WlSelect()
		with self.mktemp('aap noot mies') as f:
			wlsok = wlfile.open(f.name)
			selector.register(wlsok)
			def sink():
				data = yield None  # i.e. read
				wait.set()
			wlsok.sink(sink())
		wait.wait()
		self.assertTrue(wlsok not in selector._writers)
		self.assertTrue(wlsok not in selector._readers)

	def testCreateMultipleSelects(self):
		s1 = WlSelect()
		s2 = WlSelect()
		s3 = WlSelect()
		s4 = WlSelect()
		s5 = WlSelect()
		#s6 = WlSelect()
		#s7 = WlSelect()
		#s8 = WlSelect()
		#s9 = WlSelect()
		#s10 = WlSelect()


if __name__ == '__main__': main()