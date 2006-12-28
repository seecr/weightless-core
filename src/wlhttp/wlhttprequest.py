from urlparse import urlsplit
from re import compile
from weightless.wlcompose import RETURN
from weightless.wldict import WlDict

"""
	http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5
	Request-Line   = Method SP Request-URI SP HTTP-Version CRLF
"""

SupportedMethods = ['GET']
InvalidMethodMsg = 'Method "%s" not supported.  Supported are: ' + ', '.join(SupportedMethods) + '.'
SupportedSchemes = ['http']
InvalidSchemeMsg = 'Scheme "%s" not supported.  Supported are: ' + ', '.join(SupportedSchemes) + '.'

CRLF = '\r\n'
RequestLine = '%(Method)s %(Path)s HTTP/1.1' + CRLF
HostHeader = 'Host: %(Host)s' + CRLF
UserAgentHeader = 'User-Agent: Weightless/0.1' + CRLF

def sendRequest(Method, RequestUri):
	assert Method in SupportedMethods, InvalidMethodMsg % Method
	Scheme, Host, Path, query, fragment = urlsplit(RequestUri)
	assert Scheme in SupportedSchemes, InvalidSchemeMsg % Scheme
	yield (RequestLine + HostHeader) % locals() + UserAgentHeader + CRLF



class HTTP:
	"""
	Request       = Request-Line              ; Section 5.1
		*(( general-header        ; Section 4.5
			| request-header         ; Section 5.3
			| entity-header ) CRLF)  ; Section 7.1
		CRLF
		[ message-body ]          ; Section 4.3
	"""
	SP = ' '
	CRLF = '\r\n'
	Method = r'GET'
	Request_URI = r'(?P<RequestURI>.+)'
	HTTP_Version = r'HTTP/(?P<HTTPVersion>\d\.\d)'
	token =  """([!#$%&'*+-./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~]+){1}"""
	field_name = token
	field_value = '.*'
	message_header = field_name + ":" + field_value + CRLF
	Request_Line   = Method + SP + Request_URI + SP + HTTP_Version + CRLF
	Request = Request_Line + "(?P<headers>(" + message_header + ')*)' + CRLF
	REQUEST = compile(Request)
	
	named_message_header = '(?P<fieldname>'+field_name+'):(?P<fieldvalue>'+field_value+")" + CRLF
	named_message_headerRE = compile(named_message_header)

def recvRequest(args = None):
	args = args or WlDict()
	fragment = yield None
	match = HTTP.REQUEST.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		match = HTTP.REQUEST.match(fragment)
	args.__dict__.update(match.groupdict())
	for (groupname, fieldname, fieldvalue) in HTTP.named_message_headerRE.findall(args.headers):
		args.__dict__[fieldname.title().replace('-','')] = fieldvalue.strip()
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, args, restData
	else:
		yield RETURN, args