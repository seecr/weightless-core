from socket import socket, SOL_SOCKET, SO_REUSEADDR, SHUT_RDWR
from wlserversocket import WlServerSocket
from traceback import print_exc


BACKLOG = 1

class WlListen:

	def __init__(self, hostname, port, acceptor):
		self._sok = socket()
		self._sok.bind((hostname, port))
		self._sok.listen(BACKLOG)
		self._sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self._acceptor = acceptor
		self.fileno = self._sok.fileno

	def readable(self):
		try:
			sok, (host, port) = self._sok.accept()
			sok.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
			wlsok = WlServerSocket(host, port, sok)
			self._acceptor(wlsok)
		except Exception, e:
			print_exc()

	def close(self):
		print 'Closing ACCEPTOR.  This is an ERROR.', self.fileno()
		self._sok.shutdown(SHUT_RDWR)
		self._sok.close()