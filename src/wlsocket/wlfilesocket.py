from sendfile import sendfile
from wlthread import WlPool
from socket import socketpair, SHUT_RDWR
from sys import maxint
from wlsocket import WlBaseSocket

_open = open
_pool = WlPool()

def open(filename, mode = 'r'):
	return WlFileReader(filename)

def _sendfile(targetSocket, sourceFilename):
	sourceFile = _open(sourceFilename)
	try:
		sendfile(targetSocket.fileno(), sourceFile.fileno(), 0, maxint)
	finally:
		sourceFile.close()
		targetSocket.shutdown(SHUT_RDWR)
		targetSocket.close()
	yield None

class WlFileSocket(WlBaseSocket):

	def __init__(self, filename, with_status_and_bad_performance = False):
		self._filename = filename
		sok_read, self._sok_write = socketpair()
		WlBaseSocket.__init__(self, sok_read, with_status_and_bad_performance)

	def sink(self, generator):
		status = WlBaseSocket.sink(self, generator)
		_pool.execute(_sendfile(self._sok_write, self._filename))
		return status
