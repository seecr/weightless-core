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

import weightless.wlcompose
from weightless.wlcompose import compose, RETURN

class WlComposeTest(unittest.TestCase):

	def testCreateSinglecompose(self):
		def multplyBy2(number): yield number * 2
		wlt = compose(multplyBy2(2))
		response = wlt.next()
		self.assertEquals(4, response)

	def testRunCompletely(self):
		wlt = compose(x for x in range(3))
		results = list(wlt)
		self.assertEquals([0,1,2], results)

	def testCreateNestedcompose(self):
		def multplyBy2(number): yield number * 2
		def delegate(number): yield multplyBy2(number * 2)
		wlt = compose(delegate(2))
		response = wlt.next()
		self.assertEquals(8, response)

	def testCreateTripleNextedcompose(self):
		def multplyBy2(number): yield number * 2
		def delegate(number): yield multplyBy2(number * 2)
		def master(number): yield delegate(number * 2)
		wlt = compose(master(2))
		response = wlt.next()
		self.assertEquals(16, response)

	def testResumecompose(self):
		def thread():
			yield 'A'
			yield 'B'
		wlt = compose(thread())
		response = wlt.next()
		self.assertEquals('A', response)
		response = wlt.next()
		self.assertEquals('B', response)

	def testResumeNestedcompose(self):
		def threadA():
			yield 'A'
			yield 'B'
		def threadB():
			yield 'C'
			yield threadA()
			yield 'D'
		wlt = compose(threadB())
		results = list(wlt)
		self.assertEquals(['C','A','B','D'], results)


	def testPassValue(self):
		def thread(first):
			response = yield first
			response = yield response
			response = yield response
		t = compose(thread('first'))
		response = t.next()
		self.assertEquals('first', response)
		response = t.send('second')
		self.assertEquals('second', response)
		response = t.send('third')
		self.assertEquals('third', response)


	def testPassValueToRecursivecompose(self):
		def threadA():
			r = yield threadB()		# <= C
			yield r * 3 					# <= D
		def threadB():
			r = yield 7 					# <= A
			yield RETURN, r * 2 	# <= B
		t = compose(threadA())
		self.assertEquals(7, t.next())				# 7 yielded at A
		self.assertEquals(18, t.send(3))		# 3 send to A, 6 yielded at B, as return value to C, then yielded at D

	def testGlobalScope(self):
		def threadA():
			g.name = 'john'
			yield None
		def threadB():
			yield g.name
		ta = compose(threadA())
		tb = compose(threadB())
		list(ta)
		john = list(tb)
		self.assertEquals('john', john[0])

	def testReturnOne(self):
		data = []
		def child():
			yield RETURN, 'result'
		def parent():
			result = yield child()
			data.append(result)
		g = compose(parent())
		list(g)
		self.assertEquals('result', data[0])

	def testReturnThree(self):
		data = []
		def child():
			yield RETURN, 'result', 'remainingData1', 'other2'
		def parent():
			result = yield child()
			data.append(result)
			remainingData = yield None
			data.append(remainingData)
			other2 = yield None
			data.append(other2)
		g = compose(parent())
		list(g)
		self.assertEquals('result', data[0])
		self.assertEquals('remainingData1', data[1])
		self.assertEquals('other2', data[2])

	def testReturnAndCatchRemainingDataInNextGenerator(self):
		messages = []
		responses = []
		def child1():
			messages.append((yield RETURN, 'result', 'remainingData0', 'remainingData1'))
		def child2():
			messages.append((yield 'A'))				# append 'remainingData0'
			messages.append((yield 'B'))				# append 'remainingData1'
			messages.append((yield 'C'))				# append None
		def parent():
			messages.append((yield child1()))	# append 'result'
			messages.append((yield child2()))	# what does 'yield child2()' return???
		g = compose(parent())
		responses.append(g.next())
		responses.append(g.send('1'))
		responses.append(g.send('2'))
		try:
			responses.append(g.send('3'))
			self.fail('should raise stopiteration')
		except StopIteration: pass
		self.assertEquals([RETURN, 'result', 'remainingData0', 'remainingData1', '1', '2'], messages)
		self.assertEquals(['A', 'B', 'C'], responses)
