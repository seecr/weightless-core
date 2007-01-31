from weightless.wlservice import WlService
from weightless.wlhttp import recvResponse, sendRequest, recvBody
from time import sleep
from threading import Event
from sys import argv

if len(argv) < 2:
	print 'Usage:', argv[0], '<url> [--verbose]'
	print 'This tool downloads a url without interpreting status codes.'
	exit(1)

verbose = len(argv) > 2 and argv[2] == '--verbose'
url = argv[1]
flag = Event()
service = WlService()

def body():
	while True:
		try:
			data = yield None
		except Exception, e:
			print 'DONE', type(e)
			raise
		print ' * received', len(data), 'bytes'
		if verbose:
			print data

def get(url):
	yield sendRequest('GET', url)
	response = yield recvResponse()
	print ' * Status and headers'
	print response.__dict__
	yield recvBody(response, body())
	flag.set()

s = service.open('http://www.darenet.nl', get(url))

flag.wait()

