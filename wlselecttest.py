#!/usr/bin/env python

import unittest
import wlschedule
import wlthread
import wlselect

class WlSelectTest(unittest.TestCase):

	def setUp(self):
		self.selectArgs = None
		self.selectReturn = None

	def select(self, r, w, e):
		self.selectArgs = (list(r), list(w), list(e))
		return self.selectReturn or self.selectArgs

	def testRegisterFds(self):
		s = wlselect.WlSelect(self.select)
		s.scheduleWlThread(3, wlselect.READ, wlthread.WlThread(None))
		s.scheduleWlThread(4, wlselect.WRITE, wlthread.WlThread(None))
		s.scheduleWlThread(5, wlselect.READ, wlthread.WlThread(None))
		s.schedule()
		self.assertEquals(([3,5], [4], []), self.selectArgs)

	def testRegisterReadAndWriteIndependently(self):
		s = wlselect.WlSelect(self.select)
		s.scheduleWlThread(3, wlselect.READ, wlthread.WlThread(None))
		s.scheduleWlThread(3, wlselect.WRITE, wlthread.WlThread(None))
		s.schedule()
		self.assertEquals(([3], [3], []), self.selectArgs)

	def testRunThread(self):
		s = wlselect.WlSelect(self.select)
		s.scheduleWlThread(3, wlselect.READ, wlthread.WlThread(self.thread0()))
		s.schedule()
		self.assertEquals(([3], [], []), self.selectArgs)
		s.schedule()
		self.assertEquals(([9], [], []), self.selectArgs)
		s.schedule()
		self.assertEquals(([], [4], []), self.selectArgs)
		s.schedule()
		self.assertEquals(([5], [], []), self.selectArgs)

	def thread0(self):
		yield wlselect.READ, 9
		yield wlselect.WRITE, 4
		yield wlselect.READ, 5


if __name__ == '__main__': unittest.main()