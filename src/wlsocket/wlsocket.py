from wlbasesocket import WlBaseSocket
from socket import socket
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode


class WlSocket(WlBaseSocket):

	def __init__(self, hostname, port):
		sok = socket()
		sok.connect((hostname, port))
		WlBaseSocket.__init__(self, sok)