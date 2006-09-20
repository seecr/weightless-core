import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

from select import select

class WlSelect:

	def __init__(self):
		self._readers = set()

	def select(self):
		r, w, e = select(self._readers, [], [])
		for readable in r:
			readable.readable()

	def register(self, sok):
		sok.register(self)

	def addReader(self, sok):
		self._readers.add(sok)

	def removeReader(self, sok):
		self._readers.remove(sok)