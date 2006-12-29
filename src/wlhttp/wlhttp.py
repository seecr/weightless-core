

from urlparse import urlsplit
from weightless.wlcompose import RETURN
from weightless.wldict import WlDict
from httpspec import HTTP, REGEXP, FORMAT
from functools import partial as curry

SupportedMethods = ['GET']
InvalidMethodMsg = 'Method "%s" not supported.  Supported are: ' + ', '.join(SupportedMethods) + '.'
SupportedSchemes = ['http']
InvalidSchemeMsg = 'Scheme "%s" not supported.  Supported are: ' + ', '.join(SupportedSchemes) + '.'

class WlHttpException(Exception):
	pass

MAX_REQUESTLENGTH = 10 * 1024

def sendRequest(Method, RequestUri):
	assert Method in SupportedMethods, InvalidMethodMsg % Method
	Scheme, Host, Path, query, fragment = urlsplit(RequestUri)
	assert Scheme in SupportedSchemes, InvalidSchemeMsg % Scheme
	yield (FORMAT.RequestLine + FORMAT.HostHeader) % locals() + FORMAT.UserAgentHeader + HTTP.CRLF

def _recvRegexp(regexp, message=None):
	try:
		message = message or WlDict()
		fragment = yield None
		match = regexp.match(fragment)
		while not match:
			if len(fragment) > MAX_REQUESTLENGTH:
				raise WlHttpException('Maximum request length exceeded.')
			fragment = fragment + (yield None)
			match = regexp.match(fragment)
		message.__dict__.update(match.groupdict())
		
		message.headers = WlDict()
		for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(message._headers):
			message.headers.__dict__[fieldname.title().replace('-','')] = fieldvalue.strip()
		
		if match.end() < len(fragment):
			restData = buffer(fragment, match.end())
			yield RETURN, message, restData
		else:
			yield RETURN, message
	except WlHttpException, e:
		message.Error = str(e)
		yield RETURN, message 


recvRequest = curry(_recvRegexp, REGEXP.REQUEST)
recvResponse = curry(_recvRegexp, REGEXP.RESPONSE)
