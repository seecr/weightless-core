from __future__ import with_statement

from Queue import Queue
from cq2utils.cq2thread import CQ2Thread as Thread
from types import GeneratorType
from wlstatus import WlStatus, WlMockStatus
from sys import stderr

__author__ = "Erik Groeneveld"
__email__ = "erik@cq2.org"


class WlPool:

	def __init__(self, workers = 10, with_status_and_bad_performance = False, logger = stderr):
		"""Create a pool of 'workers' threads.  The threads are started immediatly.  The threads are daemons, meaning they will disappear when the main program exits."""
		self._createStatus = WlStatus if with_status_and_bad_performance else WlMockStatus
		self._jobs = Queue()
		pool = [Thread(None, self._worker) for i in range(workers)]
		map(lambda thread: thread.setDaemon(True), pool)
		map(Thread.start, pool)
		self._pool = pool

	def _worker(self):
		while True:
			cmd, status, callback = self._jobs.get()
			if cmd == 'stop': return
			with status:
				try:
					retval = cmd()
					callback(retval)
				except Exception, e:
					callback(e)
					raise

	def shutdown(self):
		"""Shutdown the pool.  Issues stop commands and waits until ook threads are terminated.  Current jobs are finische normally, remaining work is discarded."""
		for t in self._pool: self._jobs.put(('stop', None, None))
		map(Thread.join, self._pool)

	def execute(self, function, callback = lambda x: None):
		"""Adds a piece of work.  The first available thread wil pick it up.  Returns an WlStatus object that becomes set when on termination of the piece of work."""
		assert callable(function), 'execute() expects a callable'
		status = self._createStatus()
		self._jobs.put((function, status, callback))
		return status
