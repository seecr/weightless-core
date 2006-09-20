class WlStream:
	pass

class WlIStream(WlStream):
	def sink(generator): pass

class WlOStream(WlStream):
	def source(generator): pass

class WlIOStream(WlIStream, WlOStream):

# low level primitives
wlistream1 = storage.open('file1')
wlostream1 = storage.open('file2', 'w')
wliostream1 = wlsocket.connect('123.456.2.34', 80)

def queue(buff):
	ready = lambda: len(buff) > 0
	while True:
		yield buff.pop()

wlsocket1 = wlsocket.bind('127.0.0.1', 80, accept)

def accept(awlsocket):
	wliostream = awlsocket.accept()
	wliostream.sink(handle_http())

def handle_http():
	request_vars = {}
	yield HTTPRequestParser(request_vars)
	if request_vars['method'] == 'PUT':
		yield storage.open(request_vars['path'], 'w')
	else:
		yield storage.open(request_vars['path'])

class Scope(): pass
g = Scope()
s = Scope(cookie) # only with http!? or from same IP?
def template(g, s, r = Scope())
	g.name = 'server' # remember this globally
	s.user = 'john' # remember this for the session
	r.file = file # remember this for the request (statically)
	yield sub_template(g, s, r)

