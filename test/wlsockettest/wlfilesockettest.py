#!/usr/bin/python2.5
from __future__ import with_statement
from wltestcase import TestCase

import wlfile
import select

class WlFileTest(TestCase):

	def addReader(self, r):
		pass

	def testOpenAndReadAsyncFile(self):
		with self.mktemp('aap noot mies') as f:
			wlf = wlfile.open(f.name)
			wlf.register(self)
			wlf.sink(i for i in range(999)) # fake stuff
			r, w, e = select.select([wlf], [], [], 1.0)
			self.assertEquals([wlf], r)
			data = wlf.recv(4096)
			self.assertEquals('aap noot mies', data)

	def testReadChuncks(self):
		with self.mktemp('%08d' % n for n in xrange(513)) as f:
			wlf = wlfile.open(f.name)
			wlf.register(self)
			wlf.sink(i for i in range(999)) # fake stuff
			r, w, e = select.select([wlf], [], [], 1.0)
			self.assertEquals([wlf], r)
			data = wlf.recv(24)
			self.assertEquals('000000000000000100000002', data)
			r, w, e = select.select([wlf], [], [], 1.0)
			data = wlf.recv(16)
			self.assertEquals('0000000300000004', data)
			data = wlf.recv(99999)
			self.assertEquals('00000512', data[4056:])
			select.select([wlf], [wlf], [wlf], 1.0)
			data = wlf.recv(99999)
			self.assertEquals('', data) # EOF

if __name__ =='__main__':
	import unittest
	unittest.main()