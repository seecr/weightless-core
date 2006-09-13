#!/usr/bin/python2.5

import unittest
import wlselect
import socket

class WlSelectTest(unittest.TestCase):
	"""WlSelect runs a select loop in a separate thread"""
	def tearDown(self):
		wlselect.stop()

	def testStartStop(self):
		self.assertFalse(wlselect.isRunning())
		wlselect.start()
		self.assertTrue(wlselect.isRunning())
		wlselect.stop()
		self.assertFalse(wlselect.isRunning())
		wlselect.start()
		self.assertTrue(wlselect.isRunning())
		wlselect.stop()
		self.assertFalse(wlselect.isRunning())

	def testStartRepeatedly(self):
		self.assertFalse(wlselect.isRunning())
		wlselect.start()
		self.assertTrue(wlselect.isRunning())
		wlselect.start()
		self.assertTrue(wlselect.isRunning())

	def testStopRepeatedly(self):
		wlselect.start()
		self.assertTrue(wlselect.isRunning())
		wlselect.start()
		self.assertTrue(wlselect.isRunning())

	def testAddSocket(self):
		wlselect.start()
		sok = open('/home/erik/skype_1.2.0.18-2_i386.deb')
		wlselect.addSocket(sok)
		self.assertTrue(sok in wlselect._loop._readers)

	def testAddSocketRaisesException(self):
		wlselect.start()
		class Sok: # raise exception when put into set
			def __hash__(self): raise Exception('aap')
		try:
			wlselect.addSocket(Sok())
			self.fail()
		except Exception, e:
			self.assertEquals('aap', str(e))



if __name__ == '__main__': unittest.main()