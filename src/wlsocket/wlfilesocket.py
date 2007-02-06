from sendfile import sendfile
from weightless.wlthread import WlPool
from socket import socketpair, SHUT_RDWR
from sys import maxint
from wlbasesocket import WlBaseSocket

_pool = WlPool()

class WlFileSocket(WlBaseSocket):

	def __init__(self, filename):
		self._filename = filename
		sok_read, self._sok_write = socketpair()
		WlBaseSocket.__init__(self, sok_read)

	def sink(self, generator, selector):
		WlBaseSocket.sink(self, generator, selector)
		_pool.execute(self._openAndsendfile_blocking)

	def _open_blocking(self):
		self._file = open(self._filename)

	def _openAndsendfile_blocking(self):
		self._open_blocking()
		self._sendfile_blocking()

	def _sendfile_blocking(self):
		try:
			sendfile(self._sok_write.fileno(), self._file.fileno(), 0, maxint)
		finally:
			self._file.close()
			self._sok_write.shutdown(SHUT_RDWR)
			self._sok_write.close()


