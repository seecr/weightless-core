from __future__ import with_statement

from threading import Thread, Lock
from select import select as original_select_func
from os import pipe, write, read, close
from traceback import print_exc
from time import sleep
from sys import getcheckinterval, setcheckinterval, stderr

max32bitint = 2147483647
setcheckinterval(max32bitint) # 32bit maxint

SIGWAKEUP = 'sigwakeup'

fds = lambda soklist: map(lambda sok: sok.fileno(), soklist)

class ReadIteration(Exception): pass
class WriteIteration(Exception): pass
class SuspendIteration(Exception): pass

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
				print >> stderr, 'WlSelect Signaller: Backlog:', backLog

class WlSelect:

	def __init__(self, select_func = original_select_func):
		assert(getcheckinterval() == max32bitint, 'Please disable pre-emptive scheduling if you want to use Weightless.  To do so, call sys.setcheckinterval(sys.maxint)')
		self._inSelect = False
		self._select_func = select_func
		self._readers = set()
		self._writers = set()
		self._signaller = Signaller()
		self._readers.add(self._signaller)
		self._go = True
		self._thread = Thread(None, self._loop)
		self._thread.setDaemon(True)
		self._thread.start()

	def stop(self):
		self._go = False
		self._signaller.signal()
		self._thread.join()
		for sock in self._readers: sock.close()
		for sock in self._writers: sock.close()
		self._readers = None
		self._writers = None

	def add(self, sok, mode = 'r'):
		if mode == 'r':
			self._readers.add(sok)
		else:
			self._writers.add(sok)
		if self._inSelect:
			self._signaller.signal()

	def _loop(self):
		while self._go:
			self._select()

	def _select(self):
		self._inSelect = True
		r, w, e = self._select_func(self._readers, self._writers, [])
		self._inSelect = False

		for readable in r:
			try:
				readable.readable()
			except StopIteration:
				self._readers.remove(readable)
				readable.close()
			except WriteIteration:
				self._readers.remove(readable)
				self._writers.add(readable)
			except Exception:
				self._readers.remove(readable)
				readable.close()
				print_exc()

		for writable in w:
			try:
				writable.writable()
			except StopIteration:
				self._writers.remove(writable)
				writable.close()
			except ReadIteration:
				self._writers.remove(writable)
				self._readers.add(writable)
			except Exception:
				self._writers.remove(writable)
				writable.close()
				print_exc()
