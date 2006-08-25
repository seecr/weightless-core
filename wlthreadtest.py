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

def timeReference():
	a = []
	a.append('a')
	a.pop()
	yield None

def timeit(methodName):
	timer = Timer(
		stmt = methodName + "()",
		setup = "from wlthreadtest import " + methodName)
	return timer.timeit(100000)

def wrapThread1():
	WlThread(timeReference()).next()

def wrapThread2():
	t = wlthread.create(timeReference())
	wlthread.next(t)

def testSpeed():
	tRef = timeit("timeReference")
	t = timeit("wrapThread1")
	print tRef, t, t/tRef
	t = timeit("wrapThread2")
	print tRef, t, t/tRef


class WlThreadTest(unittest.TestCase):

	def testCreateSingleThread(self):
		wlt = WlThread(self.thread1(2))
		response = wlt.next()
		self.assertEquals(4, response)

	def thread1(self, number):
		yield number * 2

	def testRestartThreadFails(self):
		wlt = WlThread(self.thread1(2))
		response = wlt.next() # upto first yield
		try:
			response = wlt.next() # from yield to end
			self.fail()
		except StopIteration, e:
			self.assertEquals('Nothing left to run', str(e))
		try:
			response = wlt.next()
			self.fail()
		except StopIteration, e:
			self.assertEquals('', str(e))

	def testCreateNestedThread(self):
		wlt = WlThread(self.thread2(2))
		response = wlt.next()
		self.assertEquals(8, response)

	def thread2(self, number):
		yield self.thread1(number * 2)

	def testCreateTripleNextedThread(self):
		wlt = WlThread(self.thread3(2))
		response = wlt.next()
		self.assertEquals(16, response)

	def thread3(self, number):
		yield self.thread2(number * 2)

	def testResumeThhread(self):
		wlt = WlThread(self.thread4())
		response = wlt.next()
		self.assertEquals('A', response)
		response = wlt.next()
		self.assertEquals('B', response)

	def thread4(self):
		yield 'A'
		yield 'B'

	def testResumeNestedThread(self):
		wlt = WlThread(self.thread5())
		response = wlt.next()
		self.assertEquals('C', response)
		response = wlt.next()
		self.assertEquals('A', response)
		response = wlt.next()
		self.assertEquals('B', response)
		response = wlt.next()							# Actually sends None
		self.assertEquals(None, response)
		response = wlt.next()
		self.assertEquals('D', response)
		try:
			wlt.next()
			self.fail()
		except StopIteration, e:
			pass

	def thread5(self):
		yield 'C'
		yield self.thread4()
		yield 'D'

	#def testNoneThread(self):
	#	wlt = WlThread(None)
	#	wlt.next()

	def testPassValue(self):
		t = WlThread(self.thread6('first'))
		response = t.next()
		self.assertEquals('first', response)
		response = t.send('second')
		self.assertEquals('second', response)
		response = t.send('third')
		self.assertEquals('third', response)

	def thread6(self, first):
		response = yield first
		response = yield response
		response = yield response

	def testPassValueToRecursiveThread(self):
		t = WlThread(self.thread7())
		self.assertEquals(7, t.next())		# 7 yielded at A
		self.assertEquals(6, t.send(3))		# 3 send to A, 6 yielded at B
		self.assertEquals(5, t.send(5))		# 5 send to B, immediately yielded at C
		self.assertEquals(15, t.send(5))	# 5 send to C, 15 yielded at D

	def thread7(self):
		r = yield self.thread8()	# <= C
		yield r * 3 							# <= D

	def thread8(self):
		r = yield 7 							# <= A
		yield r * 2 							# <= B

	def testPassYieldedValueToCallingThread(self):
		t = WlThread(self.thread9())
		r1 = t.next()
		r2 = t.next()
		self.assertEquals(7, r1)
		self.assertEquals(7, r2)  # This is still a subject of research 1/8/06 ???

	def thread9(self):
		yield (yield self.thread10())


	def thread10(self):
		yield 7

	def testException(self):
		pass

if __name__ == '__main__': unittest.main()