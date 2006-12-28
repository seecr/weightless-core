from wlsocket import WlFileSocket, WlSelect, WlListen, WlSocket
from urlparse import urlsplit
from weightless.wlcompose import compose

class WlService:
	def __init__(self, selector = None):
		self._selector = selector or WlSelect()

	def open(self, url, sink = None):
		addressing_scheme, network_location, path, query, fragment_identifier = urlsplit(url)
		if addressing_scheme == 'file':
			wlsok = WlFileSocket(path)
		else:
			hostPort = network_location.split(':')
			host = hostPort[0]
			port = 80
			if len(hostPort) > 1:
				port = int(hostPort[1])
			wlsok = WlSocket(host, port)
		if sink:
			wlsok.sink(sink, self._selector)
		else:
			return wlsok

	def listen(self, host, port, sinkFactory = None):
		def acceptor(wlsok):
			wlsok.sink(compose(sinkFactory()), self._selector)
		wlistener =  WlListen(host, port, acceptor)
		self._selector.add(wlistener, 'r')
		return wlistener

	def stop(self):
		self._selector.stop()
