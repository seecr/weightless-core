from __future__ import with_statement

from threading import Thread, Lock
from select import select as original_select_func
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

	def __init__(self, select_func = original_select_func):
		self._select_func = select_func
		self._readers = set()
		self._writers = set()
		self._lock = Lock()
		self._signaller = Signaller()
		self._thread = Thread(None, self._loop)
		self._thread.setDaemon(True)
		self._thread.start()
		self.addReader(self._signaller)

	def __del__(self):
		print 'Tear down wlselect'
		self._pool.shutdown()

	def _loop(self):
		while True:
			self._select()

	def _select(self):
		r, w, e = self._select_func(self._readers, self._writers, [])
		for readable in r:
			try:
				readable.readable()
			except Exception:
				self._readers.remove(readable)
		for writable in w:
			try:
				writable.writable()
			except Exception:
				self._writers.remove(writable)

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