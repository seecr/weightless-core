#!/usr/bin/env python

import unittest
from wlthread import WlThread
import wlthread
from wlschedule import WlSchedule
import wlschedule

class WlScheduleTest(unittest.TestCase):

	def setUp(self):
		self.responses = []
		self.wlthreads = []

	def responseHandler(self, wlThread, response):
		self.wlthreads.append(wlThread)
		self.responses.append(response)

	def testScheduler(self):
		s = WlSchedule(self.responseHandler)
		s.addWlThread(WlThread(self.thread1(3)))
		s.schedule()
		self.assertEquals(6, self.responses[0])

	def thread1(self, number):
		yield number * 2

	def testScheduleTwo(self):
		s = WlSchedule(self.responseHandler)
		s.addWlThread(WlThread(self.thread2(3)))
		s.addWlThread(WlThread(self.thread2(4)))
		s.schedule()
		self.assertEquals(6, self.responses[0])
		self.assertEquals(8, self.responses[1])
		self.assertEquals(9, self.responses[2])
		self.assertEquals(12, self.responses[3])
		self.assertEquals(12, self.responses[4])
		self.assertEquals(16, self.responses[5])
		self.assertEquals(6, len(self.responses))

	def thread2(self, number):
		yield number * 2
		yield number * 3
		yield number * 4

	def testScheduleResponseThreadCorrelation(self):
		s = WlSchedule(self.responseHandler)
		t1 = WlThread(self.thread2(3))
		t2 = WlThread(self.thread2(4))
		s.addWlThread(t1)
		s.addWlThread(t2)
		s.schedule()
		self.assertEquals((t1,  6), (self.wlthreads[0], self.responses[0]))
		self.assertEquals((t1,  9), (self.wlthreads[2], self.responses[2]))
		self.assertEquals((t1, 12), (self.wlthreads[4], self.responses[4]))
		self.assertEquals((t2,  8), (self.wlthreads[1], self.responses[1]))
		self.assertEquals((t2, 12), (self.wlthreads[3], self.responses[3]))
		self.assertEquals((t2, 16), (self.wlthreads[5], self.responses[5]))

	def thread3handler(self, thread, response):
		return response * 3

	def thread3(self):
		result = yield 2
		self.result = result * 2

	def testCommunicationBetweenThreadAndResponseHandler(self):
		s = WlSchedule(self.thread3handler)
		t = WlThread(self.thread3())
		s.addWlThread(t)
		s.schedule()
		self.assertEquals(12, self.result)


if __name__ == '__main__': unittest.main()