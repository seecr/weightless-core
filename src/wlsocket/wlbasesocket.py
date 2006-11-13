from types import GeneratorType
from socket import SOL_SOCKET, SO_RCVBUF
from functools import partial as curry
from wlselect import WriteIteration, ReadIteration

WRITE_ITERATION = WriteIteration()
READ_ITERATION = ReadIteration()
STOP_ITERATION = StopIteration()

class WlBaseSocket:

	def __init__(self, sok):
		self._sok = sok
		self.fileno = sok.fileno
		self.close = sok.close
		self._recv = curry(sok.recv, sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2)

	def sink(self, generator, selector):
		if not type(generator) == GeneratorType:
			raise TypeError('need generator')
		try:
			self._to_write = generator.next()
		except StopIteration:
			raise ValueError('useless generator: exhausted at first next()')
		self._sink = generator
		self._selector = selector
		self._selector.add(self, 'w' if self._to_write else 'r')

	def readable(self):
		data = self._recv()
		if not data: # orderly socket shutdown
			self._sink.throw(STOP_ITERATION)
		else:
			self._to_write = self._sink.send(data)
			if self._to_write:
				raise WRITE_ITERATION

	def writable(self):
		bytesSend = self._sok.send(self._to_write)
		if bytesSend < len(self._to_write):
			self._to_write = self._to_write[bytesSend:]
		else:
			self._to_write = self._sink.next()
			if not self._to_write:
				raise READ_ITERATION
