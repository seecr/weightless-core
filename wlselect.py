import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

from wlschedule import WlSchedule

import select

READ, WRITE = range(2)

class WlSelect:
	"""
	This class maintains a `WlSchedule` based on an `select` event loop. It expects the `WlThread`s to `yield` when it needs to read or write a socket. Any thread can read or write any socket by yielding a tuple `READ|WRITE, <fd>`, e.g. `yield READ, 4`. The thread gets rescheduled when the socket is in read c.q. write condition. None is send as return value for yield (python 2.5).

	TODO: other return values must be passed back into the generator
	"""
	def __init__(self, _select = select.select):
		self._threads = {}
		self._fds = [set(), set()]
		self._select = _select
		self._schedule = WlSchedule(self.responseCallBack)

	def scheduleWlThread(self, fd, action, wlThread):
		self._threads[fd] = wlThread
		self._fds[action].add(fd)

	def runWlThread(self, wlThread):
		self._schedule.addWlThread(wlThread)

	def schedule(self):
		self._schedule.schedule()
		r, w, e = self._select(self._fds[READ], self._fds[WRITE], [])
		self._fds[READ].difference_update(r)
		self._fds[WRITE].difference_update(w)
		for fd in r + w:
			self.runWlThread(self._threads[fd])

	def responseCallBack(self, wlThread, response):
		print response
		action, fd = response
		self._schedule.removeWlThread(wlThread)
		self.scheduleWlThread(fd, action, wlThread)
