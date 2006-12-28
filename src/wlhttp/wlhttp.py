

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

def recvRequest(args = None):
	args = args or WlDict()
	fragment = yield None
	match = REGEXP.REQUEST.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		match = REGEXP.REQUEST.match(fragment)
	args.__dict__.update(match.groupdict())
	for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(args.headers):
		args.__dict__[fieldname.title().replace('-','')] = fieldvalue.strip()
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, args, restData
	else:
		yield RETURN, args

def recvResponse(args = None):
	args = args or WlDict()
	fragment = yield None
	match = REGEXP.RESPONSE.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		match = REGEXP.RESPONSE.match(fragment)
	restData = buffer(fragment, match.end())
	args.__dict__.update(match.groupdict())
	for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(args.headers):
		args.__dict__[fieldname.capitalize()] = fieldvalue.strip()
	yield RETURN, args, restData
