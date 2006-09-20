#!/usr/bin/python2.5
from __future__ import with_statement

from unittest import main
from wltestcase import TestCase
from wlselect import WlSelect
#from wlthreadpool import yield_cpu
import wlfile

class WlSelectTest(TestCase):

	def setUp(self):
		self.selector = WlSelect()

	def testAddSocket(self):
		sok = wlfile.open('wlselecttest.py')
		self.selector.addReader(sok)
		self.assertTrue(sok in self.selector._readers)

	def testAddSocketRaisesException(self):
		class Sok: # raise exception when put into set
			def __hash__(self): raise Exception('aap')
		try:
			self.selector.addReader(Sok())
			self.fail()
		except Exception, e:
			self.assertEquals('aap', str(e))

	def testReadFile(self):
		data = [None]
		with self.mktemp('aap noot mies') as f:
			wlsok = wlfile.open(f.name)
			self.selector.register(wlsok)
			self.assertTrue(wlsok not in self.selector._readers)
			def sink(): data[0] = yield None
			wlsok.sink(sink())
			self.assertTrue(wlsok in self.selector._readers)
			self.selector.select()
		self.assertEquals('aap noot mies', data[0])

	def testRemoveFromReadersWhenGeneratorIsExhausted(self):
		with self.mktemp('aap noot mies') as f:
			wlsok = wlfile.open(f.name)
			self.selector.register(wlsok)
			wlsok.sink(i for i in [])
			self.selector.select()
		self.assertTrue(wlsok not in self.selector._readers)

if __name__ == '__main__': main()