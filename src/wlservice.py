from wlsocket import WlFileSocket, WlSelect
from urlparse import urlsplit

class WlService:
	def __init__(self, selector = None):
		self._selector = selector or WlSelect()

	def open(self, url, sink):
		addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
		WlFileSocket(path).sink(sink, self._selector)