

from urlparse import urlsplit
from weightless.wlcompose import RETURN
from weightless.wldict import WlDict
from httpspec import HTTP, REGEXP, FORMAT


SupportedMethods = ['GET']
InvalidMethodMsg = 'Method "%s" not supported.  Supported are: ' + ', '.join(SupportedMethods) + '.'
SupportedSchemes = ['http']
InvalidSchemeMsg = 'Scheme "%s" not supported.  Supported are: ' + ', '.join(SupportedSchemes) + '.'


def sendRequest(Method, RequestUri):
	assert Method in SupportedMethods, InvalidMethodMsg % Method
	Scheme, Host, Path, query, fragment = urlsplit(RequestUri)
	assert Scheme in SupportedSchemes, InvalidSchemeMsg % Scheme
	yield (FORMAT.RequestLine + FORMAT.HostHeader) % locals() + FORMAT.UserAgentHeader + HTTP.CRLF

def _recvRegexp(regexp, args):
	args = args or WlDict()
	fragment = yield None
	match = regexp.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		match = regexp.match(fragment)
	args.__dict__.update(match.groupdict())
	
	args.headers = WlDict()
	for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(args._headers):
		args.headers.__dict__[fieldname.title().replace('-','')] = fieldvalue.strip()
	
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, args, restData
	else:
		yield RETURN, args


recvRequest = lambda args = None: _recvRegexp(REGEXP.REQUEST, args)
recvResponse = lambda args = None: _recvRegexp(REGEXP.RESPONSE, args)
