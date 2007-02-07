from types import GeneratorType
from socket import SOL_SOCKET, SO_RCVBUF
from functools import partial as curry
from wlselect import WriteIteration, ReadIteration, SuspendIteration
from wlasyncprocessor import WlAsyncProcessor


WRITE_ITERATION = WriteIteration()
READ_ITERATION = ReadIteration()
STOP_ITERATION = StopIteration()
SUSPEND_ITERATION = SuspendIteration()

class WlBaseSocket:

	def __init__(self, sok):
		self._sok = sok
		self.fileno = sok.fileno
		self.close = sok.close
		self._recv = curry(sok.recv, sok.getsockopt(SOL_SOCKET, SO_RCVBUF) / 2)
		self._write_queue = []

	def sink(self, generator, selector):
		if not type(generator) == GeneratorType:
			raise TypeError('need generator')
		self._sink = generator
		self._selector = selector
		try:
			response = generator.next()
		except (StopIteration, GeneratorExit):
			raise ValueError('useless generator: exhausted at first next()')
		if isinstance(response, WlAsyncProcessor):
			response.start(self)
		elif response:
			self._write_queue.append(response)
			self._selector.add(self, 'w')
		else:
			self._selector.add(self, 'r')

	def readable(self):
		data = self._recv()
		if not data: # orderly socket shutdown
			self._sink.close()
		else:
			response = self._sink.send(data)
			if isinstance(response, WlAsyncProcessor):
				response.start(self)
				raise SUSPEND_ITERATION
			if response:
				self._write_queue.append(response)
				raise WRITE_ITERATION

	def writable(self):
		bytesSend = self._sok.send(self._write_queue[0])
		if bytesSend < len(self._write_queue[0]):
			self._write_queue[0] = buffer(self._write_queue[0], bytesSend)
		else:
			self._write_queue.pop(0)
		if not self._write_queue:
			response = self._sink.next()
			if isinstance(response, WlAsyncProcessor):
				response.start(self)
				raise SUSPEND_ITERATION
			if not response:
				raise READ_ITERATION
			self._write_queue.append(response)

	def async_completed(self, retval):
		try:
			response = self._sink.next()
		except (StopIteration, GeneratorExit):
			return
		if isinstance(response, WlAsyncProcessor):
			response.start(self)
		elif response:
			self._write_queue.append(response)
			self._selector.add(self, 'w')
		else:
			self._selector.add(self, 'r')

	def send(self, data):
		self._write_queue.append(data)