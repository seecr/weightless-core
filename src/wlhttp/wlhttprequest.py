from urlparse import urlsplit
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
