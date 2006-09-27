from __future__ import with_statement

import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

from threading import Lock
from select import select as original_select_func
from wlthreadpool import Pool
from os import pipe, write, read, close

SIGWAKEUP = 'sigwakeup'

fds = lambda soklist: map(lambda sok: sok.fileno(), soklist)

class Signaller:

	def __init__(self):
		self._signal_recv_fd, self._signal_send_fd = pipe()
		self.fileno = lambda: self._signal_recv_fd

	def __del__(self):
		print 'Tear down Signaller'
		close(self._signal_recv_fd)
		close(self._signal_send_fd)

	def signal(self):
		write(self._signal_send_fd, SIGWAKEUP)

	def readable(self):
		read(self._signal_recv_fd, len(SIGWAKEUP))

class WlSelect:

	def __init__(self, pool = Pool(), select_func = original_select_func):
		self._select_func = select_func
		self._readers = set()
		self._writers = set()
		self._lock = Lock()
		self._signaller = Signaller()
		self.addReader(self._signaller)
		self._pool = pool
		self._pool.execute(self._loop())

	def __del__(self):
		print 'Tear down wlselect'
		self._pool.shutdown()

	def _loop(self):
		while True:
			self._select()
		yield None

	def _select(self):
		r, w, e = self._select_func(self._readers, self._writers, [])
		for readable in r:
			readable.readable()
		for writable in w:
			writable.writable()

	def register(self, sok):
		sok.register(self)

	def addReader(self, sok):
		with self._lock:
			self._readers.add(sok)
			self._signaller.signal()

	def addWriter(self, sok):
		with self._lock:
			self._writers.add(sok)
			self._signaller.signal()

	def removeReader(self, sok):
		self._readers.remove(sok)

	def removeWriter(self, sok):
		self._writers.remove(sok)