from Queue import Queue
from threading import Thread
from types import GeneratorType
from wlstatus import WlStatus, WlMockStatus
import sys

__author__ = "Erik Groeneveld"
__email__ = "erik@cq2.org"
__version__ = "#Revision: 1.63 $"

__all__ = ['Pool', 'execute']

@contextmanager
def running(function):
	t = Thread(None, function)
	t.start()
	yield t
	t.join()

def run(function):
	def wrapper(function, status):
		try
			function()
		except:
			status.setError()
		else:
			status.setOk()
	t = Thread(None, function)
	t.start()


class Pool:

	def __init__(self, workers = 10, with_status_and_bad_performance = False):
		"""Create a pool of 'workers' threads.  The threads are started immediatly.  The threads are daemons, meaning they will disappear when the main program exits."""
		self._createStatus = WlStatus if with_status_and_bad_performance else WlMockStatus
		self._jobs = Queue()
		pool = [Thread(None, self._worker) for i in range(workers)]
		map(lambda thread: thread.setDaemon(True), pool)
		map(Thread.start, pool)
		self._pool = pool

	def _worker(self):
		while True:
			cmd, status = self._jobs.get()
			if cmd == 'stop': return
			try:
				list(cmd)
			except Exception:
				status.printExc()
				status.setError()
			status.setOk()

	def shutdown(self):
		"""Shutdown the pool.  Issues stop commands and waits until ook threads are terminated.  Current jobs are finische normally, remaining work is discarded."""
		for t in self._pool: self._jobs.put(('stop', None))
		map(Thread.join, self._pool)

	def execute(self, generator):
		"""Adds a piece of work.  The first available thread wil pick it up.  Returns an Status object that becomes set when on termination of the piece of work."""
		if not type(generator) == GeneratorType:
			raise TypeError('execute() expects a generator')
		status = self._createStatus()
		self._jobs.put((generator, status))
		return status