from sendfile import sendfile
from weightless.wlthread import WlPool
from socket import socketpair, SHUT_RDWR
from sys import maxint
from wlbasesocket import WlBaseSocket

_pool = WlPool()

def _sendfile(targetSocket, sourceFilename):
	sourceFile = open(sourceFilename)
	try:
		sendfile(targetSocket.fileno(), sourceFile.fileno(), 0, maxint)
	finally:
		sourceFile.close()
		targetSocket.shutdown(SHUT_RDWR)
		targetSocket.close()
	yield None


class WlFileSocket(WlBaseSocket):

	def __init__(self, filename):
		self._filename = filename
		sok_read, self._sok_write = socketpair()
		WlBaseSocket.__init__(self, sok_read)

	def sink(self, generator, selector):
		WlBaseSocket.sink(self, generator, selector)
		_pool.execute(_sendfile(self._sok_write, self._filename))
