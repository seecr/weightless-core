from time import sleep
from weightless import WlService
from weightless.wlhttp import recvRequest
from weightless.http import HTTP
from weightless import compose
from weightless.wlhttp import recvRequest
from functools import partial as curry
from urlparse import urlsplit
from types import GeneratorType

#import psyco
#psyco.full()

from cq2utils import cq2thread
cq2thread.profilingEnabled = True

service = WlService()

class AComponent:
	def display(self, x, y):
		return (x for x in ['a'*x*y])

def parseArgs(uri):
	if uri.query:
		args = (arg.split('=') for arg in uri.query.split('&'))
		return dict((name, eval(value, {'__builtins__': {}})) for name, value in args)
	return {}

def handler():
	req = yield recvRequest()
	uri = urlsplit(req.RequestURI)
	try:
		selectors = uri.path[1:].split('/', 2)
		namespace, componentname = selectors[:2]
		methodName = selectors[2] if len(selectors) > 2 else 'display'
		component = AComponent()
	except:
		component = None
	if component is None:
		yield HTTP.Response.StatusLine % {
			'version': 1.0,
			'status': 404,
			'reason': 'Not Found'}
	else:
		args = parseArgs(uri)
		method = getattr(component, methodName)
		data = method(**args)
		mimetype = 'text/plain' if type(data) != GeneratorType else 'image/png'
		yield HTTP.Response.StatusLine % {
			'version': 1.0,
			'status': 200,
			'reason': 'OK'}
		yield HTTP.Message.Headers({'Content-Type': mimetype, 'Connection': 'close'})
		yield repr(data) if type(data) != GeneratorType else data

def sinkFactory():
	return handler()

service.listen('127.0.0.1', 1234, sinkFactory)

try:
	while True:
		print '.'
		sleep(1)
except KeyboardInterrupt:
	pass

service.stop()