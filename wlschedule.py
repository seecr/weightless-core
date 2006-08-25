#!/usr/bin/env python

import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

class WlSchedule:
	"""
This class accepts a list of `WlThread`s and runs them until all threads are completed. Values yielded by a thread are passed to a response handler.  The return value of the response handler is passed to the thread when it continues.
Performance sensitive code.
	"""
	def __init__(self, responseHandler, schedule = []):
		self._responseHandler = responseHandler
		self._wlschedule = schedule

	def addWlThread(self, wlThread):
		self._wlschedule.append(wlThread)

	def removeWlThread(self, wlThread):
		self._wlschedule.remove(wlThread)

	def schedule(self):
		argument = None
		while self._wlschedule:
			for wlThread in self._wlschedule:
				try:
					response = wlThread.run(argument)
					argument = self._responseHandler(wlThread, response)
				except StopIteration:
					self._wlschedule.remove(wlThread)