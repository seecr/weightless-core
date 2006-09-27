from threading import Event
from inspect import currentframe
from traceback import extract_stack, format_list
from StringIO import StringIO
from sys import stdout, exc_info

class WlMockStatus:
	"""Complete fake replacement for WlStatus.  Meant to avoid performance bottlenecks involved in WlStatus in production systems."""
	def __enter__(self): pass
	def __exit__(self, a, b, c): pass
	def capture(self, f): pass
	def join(self): pass
	def print_context(self, file=None): pass


class WlStatus:
	""" This class means to communicate the termination state of a thread to another thread during testing or debugging. Use WlMockStatus for deployed systems."""

	def __init__(self):
		self._event = Event()
		self.isSet = self._event.isSet
		self._exception = None
		self._context = [f for f in extract_stack(currentframe().f_back) if 'unittest.py' not in f]

	def __enter__(self):
		pass

	def __exit__(self, etype, evalue, etraceback):
		if etype:
			self._exception = etype, evalue, etraceback
		self._event.set()
		return True

	def capture(self, function):
		try:
			function()
		except:
			self._exception = exc_info()
		self._event.set()

	def join(self):
		self._event.wait()
		if self._exception:
			etype, evalue, etraceback = self._exception
			raise etype, evalue, etraceback.tb_next

	def print_context(self, file = stdout):
  		for line in format_list(self._context): file.write(line)