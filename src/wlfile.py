from sendfile import sendfile
from wlthreadpool import execute
from socket import socketpair, SHUT_RDWR
from sys import maxint
from wlsocket import WlSocket

_open = open

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

class WlFileReader(WlSocket):
	def __init__(self, filename):
		sok_read, sok_write = socketpair()
		WlSocket.__init__(self, sok_read)
		execute(_sendfile(sok_write, filename))