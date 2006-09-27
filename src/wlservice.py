from wlfile import WlFileReader
from wlselect import WlSelect
from urlparse import urlsplit

class WlService:
	def __init__(self, selector = WlSelect(), with_status_and_bad_performance = False):
		self._selector = selector
		self._with_status_and_bad_performance = with_status_and_bad_performance

	def open(self, url):
		addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
		sok = WlFileReader(path, self._with_status_and_bad_performance)
		self._selector.register(sok)
		return sok