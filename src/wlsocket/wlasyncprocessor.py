class WlAsyncProcessor(object):
	def _processStart(self): pass

class sendFile:
	def _process(self):
		f = open(file)
		sendfile(f, self._wlsok.fileno())
		self._wlsok._processDone('some return value')

	def _processStart(self, wlsok):
		self._wlsok = wlsok
		self._thread = Thread(None, self._process)


def exampleHandler():
	args = yield recvRequest()
	yield sendResponse()
	someReturnValue = yield sendFile('filename') # yield an object that does magic
	yield 'Trailing-Header: 123\r\n'

	filesocket = service.open('file')
	while True:
		yield filesocket.read()

	for line in filesocket:
		yield line
