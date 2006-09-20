#!/usr/bin/env python
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

import unittest
from timeit import Timer

import wlthread
from wlthread import WlThread

class WlThreadTest(unittest.TestCase):

	def testCreateSingleThread(self):
		def multplyBy2(number): yield number * 2
		wlt = WlThread(multplyBy2(2))
		response = wlt.next()
		self.assertEquals(4, response)

	def testRunCompletely(self):
		wlt = WlThread(x for x in range(3))
		results = list(wlt)
		self.assertEquals([0,1,2], results)

	def testCreateNestedThread(self):
		def multplyBy2(number): yield number * 2
		def delegate(number): yield multplyBy2(number * 2)
		wlt = WlThread(delegate(2))
		response = wlt.next()
		self.assertEquals(8, response)

	def testCreateTripleNextedThread(self):
		def multplyBy2(number): yield number * 2
		def delegate(number): yield multplyBy2(number * 2)
		def master(number): yield delegate(number * 2)
		wlt = WlThread(master(2))
		response = wlt.next()
		self.assertEquals(16, response)

	def testResumeThread(self):
		def thread():
			yield 'A'
			yield 'B'
		wlt = WlThread(thread())
		response = wlt.next()
		self.assertEquals('A', response)
		response = wlt.next()
		self.assertEquals('B', response)

	def testResumeNestedThread(self):
		def threadA():
			yield 'A'
			yield 'B'
		def threadB():
			yield 'C'
			yield threadA()
			yield 'D'
		wlt = WlThread(threadB())
		results = list(wlt)
		self.assertEquals(['C','A','B','D'], results)


	def testPassValue(self):
		def thread(first):
			response = yield first
			response = yield response
			response = yield response
		t = WlThread(thread('first'))
		response = t.next()
		self.assertEquals('first', response)
		response = t.send('second')
		self.assertEquals('second', response)
		response = t.send('third')
		self.assertEquals('third', response)


	def testPassValueToRecursiveThread(self):
		def threadA():
			r = yield threadB()	# <= C
			yield r * 3 					# <= D
		def threadB():
			r = yield 7 					# <= A
			yield r * 2 					# <= B
		t = WlThread(threadA())
		self.assertEquals(7, t.next())		# 7 yielded at A
		self.assertEquals(6, t.send(3))		# 3 send to A, 6 yielded at B
		self.assertEquals(15, t.send(5))	# 5 send to B, threadB terminates and 15 yielded at D

	def testGlobalScope(self):
		def threadA():
			g.name = 'john'
			yield None
		def threadB():
			yield g.name
		ta = WlThread(threadA())
		tb = WlThread(threadB())
		list(ta)
		john = list(tb)
		self.assertEquals('john', john[0])

	def testThreadScope(self):
		def threadA():
			t.name = 'john'
			john = yield threadB()
			yield john
		def threadB():
			yield t.name
		ta = WlThread(threadA())
		john = list(ta)
		self.assertEquals('john', john[0])
		def threadC():
			yield t.name # raise execption
		try:
			list(WlThread(threadC()))
			self.fail()
		except Exception, e:
			print '>', type(e), '<'

if __name__ == '__main__': unittest.main()