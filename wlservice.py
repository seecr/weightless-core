import socket, select

def create(host = 'localhost', port = 80, name = 'wlservice'):
	return WlService(host, port, name)

class WlService:
	def __init__(self, host, port, name):
		self._host = host
		self._port = port
		self._name = name
		self._handlers = [None for x in range(100)]

	def __str__(self):
		return self._name + ':' + self._host + ':' + str(self._port)

	def _acceptor(self, acceptor):
		while True:
			sok, host = self._sokket.accept()
			handler = acceptor(sok, host)
			handler.next()
			fd = sok.fileno()
			self._readers.add(fd)
			self._handlers[fd] = self._handler(sok, handler)
			yield -1

	def _handler(self, sokket, handler):
		while True:
			buff = sokket.recv(4096)
			handler.send(buff)
			yield -1

	def listen(self, acceptor):
		self._sokket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sokket.bind((self._host, self._port))
		self._sokket.listen(5)
		self._readers = set([self._sokket.fileno()])
		self._handlers[self._sokket.fileno()] = self._acceptor(acceptor)

	def select(self):
		r, w, e = select.select(self._readers, [], [])
		for fd in r:
			try:
				self._handlers[fd].next()
			except StopIteration:
				pass # remove from reades/writers

	def __del__(self):
		if hasattr(self, '_sokket'):
			self._sokket.shutdown(socket.SHUT_RDWR)
			self._sokket.close()
			# close other sockets as well