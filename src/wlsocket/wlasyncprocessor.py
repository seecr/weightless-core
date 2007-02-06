from weightless.wlthread import WlPool

_pool = WlPool()

class WlAsyncProcessor(object):

	def start(self, wlsok):
		self.wlsok = wlsok
		_pool.execute(self._process)

	def _process(self):
		self.process()
		self.wlsok.async_completed()

	def process(self):
		pass


class sendFile(WlAsyncProcessor):

	def __init__(self, filename):
		self.filename = filename

	def process(self):
		f = open(self.filename)
		sendfile(f, self.wlsok.fileno())