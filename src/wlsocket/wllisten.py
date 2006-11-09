from socket import socket
from wlserversocket import WlServerSocket

BACKLOG = 1

class WlListen:

	def __init__(self, hostname, port, acceptor):
		self._sok = socket()
		self._sok.bind((hostname, port))
		self._sok.listen(BACKLOG)
		self._acceptor = acceptor
		self.fileno = self._sok.fileno

	def readable(self):
		sok, (host, port) = self._sok.accept()
		wlsok = WlServerSocket(host, port, sok)
		self._acceptor(wlsok)

	def close(self):
		self._sok.close()