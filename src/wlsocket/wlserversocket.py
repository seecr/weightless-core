from wlbasesocket import WlBaseSocket
from socket import socket

class WlServerSocket(WlBaseSocket):

	def __init__(self, hostname, port, sokket):
		WlBaseSocket.__init__(self, sokket)
		self.host = hostname
		self.port = port