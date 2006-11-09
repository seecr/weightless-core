from re import compile


#Request-URI    = "*" | absoluteURI | abs_path | authority

# http://www.ietf.org/rfc/rfc2396.txt
#absoluteURI   = scheme ":" ( hier_part | opaque_part )
#     hier_part     = ( net_path | abs_path ) [ "?" query ]
#     net_path      = "//" authority [ abs_path ]
#      abs_path      = "/"  path_segments

HTTP_REQUEST = compile("GET (?P<path>.+) HTTP/(?P<version>.+)\r\n")

class Container: pass

def WlHttp(bodyHandler):
	match = None
	request = ''
	while not match:
		request = request + (yield None)
		match = HTTP_REQUEST.match(request)
	request = Container()
	request.__dict__ = match.groupdict()
	yield 'HTTP/%s 200 OK\r\n' % request.version

	yield bodyHandler(request)

	yield '\r\n'