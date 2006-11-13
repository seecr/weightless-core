from wlsocket import WlFileSocket, WlSelect, WlListen
from urlparse import urlsplit

class WlService:
	def __init__(self, selector = None):
		self._selector = selector or WlSelect()

	def open(self, url, sink = None):
		addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
		wlsok = WlFileSocket(path)
		if sink:
			wlsok.sink(sink, self._selector)
		else:
			return wlsok

	def listen(self, host, port, sinkFactory = None):
		def acceptor(wlsok):
			wlsok.sink(sinkFactory(), self._selector)
		wlistener =  WlListen(host, port, acceptor)
		self._selector.add(wlistener, 'r')
		return wlistener
