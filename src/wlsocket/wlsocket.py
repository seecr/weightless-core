from wlbasesocket import WlBaseSocket
from socket import socket
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode


class WlSocket(WlBaseSocket):

	def __init__(self, hostname, port):
		sok = socket()
		sok.setblocking(0)
		err = sok.connect_ex((hostname, port))
		if not err in (EINPROGRESS, EALREADY, EWOULDBLOCK, EISCONN, 0):
			raise socket.error, (err, errorcode[err])
		# just let it go, the async operation will catch up on read/write
		WlBaseSocket.__init__(self, sok)