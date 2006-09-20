import socket, select

BUFFSIZE = 1024 * 8

def create(host = 'localhost', port = 80, name = 'wlservice'):
	return WlService(host, port, name)

class WlService:
	def __init__(self, host, port, name):
		self._host = host
		self._port = port
		self._name = name
		self._handlers = {}

	def __str__(self):
		return self._name + ':' + self._host + ':' + str(self._port)

	def _acceptor(self, acceptor):
		while True:
			sok, host = self._sokket.accept()
			handler = acceptor(sok, host)
			handler.next()
			self._readers.add(sok)
			self._handlers[sok] = self._handler(sok, handler)
			yield -1

	def _handler(self, sokket, handler):
		while True:
			handler.send(sokket.recv(BUFFSIZE))
			yield -1

	def listen(self, acceptor):
		self._sokket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sokket.bind((self._host, self._port))
		self._sokket.listen(5)
		self._readers = set([self._sokket])
		self._handlers[self._sokket] = self._acceptor(acceptor)

	def select(self):
		r, w, e = select.select(self._readers, [], [])
		for sok in r:
			try:
				self._handlers[sok].next()
			except StopIteration:
				pass # remove from reades/writers

	def __del__(self):
		if hasattr(self, '_sokket'):
			self._sokket.shutdown(socket.SHUT_RDWR)
			self._sokket.close()
			# close other sockets as well