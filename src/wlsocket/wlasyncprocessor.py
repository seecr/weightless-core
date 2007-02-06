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