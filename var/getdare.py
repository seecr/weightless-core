from weightless.wlservice import WlService
from weightless.wlhttp import recvResponse, sendRequest
from time import sleep
from threading import Event

flag = Event()

service = WlService()

def get(url):
	yield sendRequest('GET', url)
	response = yield recvResponse()
	print str(response.__dict__)
	try:
		body = ''
		for i in range(99):
			data = yield None
			body += str(data)
			print ' ** buffer received:', type(data), len(data), '<<<'
	finally:
		print 'Get stopping'
		flag.set()

s = service.open('http://www.darenet.nl', get('http://www.darenet.nl/nl/page/language.view/search.page'))

flag.wait()

