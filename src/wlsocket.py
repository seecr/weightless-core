from types import GeneratorType

class WlSocket:

	def __init__(self, sok):
		self.fileno = sok.fileno
		self.recv = sok.recv
		self.close = sok.close

	def sink(self, generator):
		if not type(generator) == GeneratorType:
			raise TypeError('need generator')
		generator.next()
		self._sink = generator
		self._selector.addReader(self)

	def register(self, selector):
		self._selector = selector

	def readable(self):
		data = self.recv(4096)
		try:
			if not data: # orderly socket shutdown
				self._sink.throw(StopIteration())
			else:
				self._sink.send(data)
		except StopIteration:
			self._selector.removeReader(self)

