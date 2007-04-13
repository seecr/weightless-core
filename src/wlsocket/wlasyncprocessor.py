from weightless.wlthread import WlPool

_pool = WlPool()

class WlAsyncProcessor(object):

	def start(self, wlsok):
		self.wlsok = wlsok
		_pool.execute(self._process)

	def _process(self):
		retval = self.process()
		self.wlsok.async_completed(retval)

	def process(self):
		pass

class asynchronously(WlAsyncProcessor):
	def __init__(self, function):
		self.process = function