from __future__ import with_statement

from threading import Thread, Lock
from select import select as original_select_func
from os import pipe, write, read, close
from traceback import print_exc
from time import sleep
from sys import getcheckinterval, maxint

SIGWAKEUP = 'sigwakeup'

fds = lambda soklist: map(lambda sok: sok.fileno(), soklist)

class Signaller:

	def __init__(self):
		self._signal_recv_fd, self._signal_send_fd = pipe()
		self.fileno = lambda: self._signal_recv_fd
		self._signalled = False

	def close(self):
		close(self._signal_recv_fd)
		close(self._signal_send_fd)

	def signal(self):
		if not self._signalled:
			self._signalled = True
			write(self._signal_send_fd, SIGWAKEUP)

	def readable(self):
		if self._signalled:
			self._signalled = False
			buff = read(self._signal_recv_fd, 128*1024)
			backLog = len(buff)/len(SIGWAKEUP)
			if backLog > 1:
				print '> Backlog:', backLog

class WlSelect:

	def __init__(self, select_func = original_select_func):
		assert(getcheckinterval() == maxint)
		self._inSelect = False
		self._select_func = select_func
		self._readers = set()
		self._writers = set()
		self._signaller = Signaller()
		self.addReader(self._signaller)
		self._thread = Thread(None, self._loop)
		self._thread.setDaemon(True)
		self._thread.start()

	def _loop(self):
		while True:
			self._select()

	def _select(self):
		self._inSelect = True
		r, w, e = self._select_func(self._readers, self._writers, [])
		self._inSelect = False
		for readable in r:
			try:
				readable.readable()
			except Exception, e:
				self._readers.remove(readable)
				#readable.close()
		for writable in w:
			try:
				writable.writable()
			except StopIteration:
				self._writers.remove(writable)
				writable.close()

			#except ReadIteration:
			#	self._writers.remove(writable)
			#	self._readers.add(sok)

			except Exception:
				self._writers.remove(writable)
				writable.close()
				print_exc()

	def addReader(self, sok):
		self._readers.add(sok)
		if self._inSelect:
			self._signaller.signal()

	def addWriter(self, sok):
		self._writers.add(sok)
		if self._inSelect:
			self._signaller.signal()

	def removeReader(self, sok):
		self._readers.remove(sok)

	def removeWriter(self, sok):
		self._writers.remove(sok)