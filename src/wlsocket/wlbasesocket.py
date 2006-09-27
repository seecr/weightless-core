from types import GeneratorType
from wlthread import WlStatus, WlMockStatus

class WlBaseSocket:

	def __init__(self, sok, with_status_and_bad_performance = False):
		self.createStatus = WlStatus if with_status_and_bad_performance else WlMockStatus
		self.fileno = sok.fileno
		self.recv = sok.recv
		self.send = sok.send
		self.close = sok.close

	def sink(self, generator):
		if not type(generator) == GeneratorType:
			raise TypeError('need generator')
		try:
			status = self.createStatus()
			self._to_write = generator.next()
			self._sink = (generator, status)
			self._selector.addWriter(self) if self._to_write else self._selector.addReader(self)
		except StopIteration:
			raise ValueError('useless generator: exhausted at first next()')
		return status

	def register(self, selector):
		self._selector = selector

	def readable(self):
		data = self.recv(4096)
		try:
			if not data: # orderly socket shutdown
				self._sink[0].throw(StopIteration())
			else:
				self._to_write = self._sink[0].send(data)
				if self._to_write:
					self._selector.removeReader(self)
					self._selector.addWriter(self)
		except StopIteration:
			self._selector.removeReader(self)
			self._sink[1].setOk()

	def writable(self):
		self.send(self._to_write)
		try:
			self._to_write = self._sink[0].next()
			if not self._to_write:
				self._selector.removeWriter(self)
				self._selector.addReader(self)
		except StopIteration:
			self._selector.removeWriter(self)
			self._sink[1].setOk()