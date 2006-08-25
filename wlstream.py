import platform
assert platform.python_version() >= "2.5", "Python 2.5 required"

# This class is a socket wrapper that supports expressing expectations
# about the recv buffer.  Normally when a socket has data ready, this
# can be 5kb of just 3 bytes. You don't know.  This wrapper allow a
# program to use a regular expresssion for setting expectations about
# what is in the recv buffer.  The wrapper keeps yielding until the
# recv buffer matches the regular expression.
# A weak point of this approach is of course detecting the difference
# between incomplete data and garbage data.

import re
import wlselect

RECV_BUF_SIZE = 4*1024
READLINE_RE = re.compile('(.*?\n)')

cache = {}

def getRe(regexp):
	if regexp in cache:
		return cache[regexp]
	else:
		regCompiled = re.compile(regexp, re.DOTALL)
		cache[regexp] = regCompiled
		return regCompiled

class WlStream:
	def __init__(self, socket):
		self._socket = socket
		self._fd = socket.fileno()
		self._buff = ''

	def __getattr__(self, name):
		return getattr(self._socket, name)

	def read(self, regexp):
		regexp = type(regexp) == str and getRe(regexp) or regexp
		self._match = regexp.search(self._buff)
		while not self._match:
			yield wlselect.READ, self._fd
			self._buff += self._socket.recv(RECV_BUF_SIZE)
			self._match = regexp.search(self._buff)
		self._buff = self._buff[self._match.end():]
		yield self._match.group(0)

	def readline(self):
		yield self.read(READLINE_RE)

	def match(self):
		return self._match.groups()