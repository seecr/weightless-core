from wlbasesocket import WlBaseSocket
from socket import socket

class WlSocket(WlBaseSocket):

	def __init__(self, hostname, port = 80):
		sok = socket()
		sok.connect((hostname, port))
		WlBaseSocket.__init__(self, sok)
