import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

import select
import threading
import time
import socket
import sys

PORT = 9876

class Signaller:

	def __init__(self, callback):
		listener = socket.socket()
		listener.bind(('127.0.0.1', PORT))
		listener.listen(0)
		self._sender = socket.socket()
		self._sender.connect(('127.0.0.1', PORT))
		self._receiver = listener.accept()[0]
		self.fileno = self._receiver.fileno
		self._callback = callback
		self._exception = None

	def read(self):
		try:
			if self._value:
				self._callback(self._value)
			self._value = None
		except Exception, e:
			self._exception = e
		self._receiver.recv(4096)

	def signal(self, value = None):
		self._exception = None
		self._value = value
		self._sender.send('**')
		time.sleep(0.001)
		if self._exception:
			raise self._exception

class Loop:
	def __init__(self):
		self._go = threading.Event(1)
		self._thread = None
		self._signaller = Signaller(self._addSocket)
		self._readers = set([self._signaller])

	def loop(self):
		while self._go.isSet():
			r, w, e = select.select(self._readers, [], [])
			for readable in r:
				readable.read()

	def _addSocket(self, sok):
		self._readers.add(sok)

	def addSocket(self, sok):
		self._signaller.signal(sok)

	def start(self):
		self._go.set()
		if not self._thread:
			self._thread = threading.Thread(None, self.loop)
			self._thread.setDaemon(True)
			self._thread.start()
		time.sleep(0.001)

	def isRunning(self):
		return self._thread and self._thread.isAlive()

	def stop(self):
		self._go.clear()
		if self._thread:
			self._signaller.signal()
			self._thread.join()
			self._thread = None

_loop = Loop()
start = _loop.start
stop = _loop.stop
addSocket = _loop.addSocket
isRunning = _loop.isRunning
