from sys import stderr

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

def sendRequest(Method, Request_URI):
	assert Method in SupportedMethods, InvalidMethodMsg % Method
	Scheme, Host, Path, query, fragment = urlsplit(Request_URI)
	assert Scheme in SupportedSchemes, InvalidSchemeMsg % Scheme
	yield (FORMAT.RequestLine + FORMAT.HostHeader) % locals() + FORMAT.UserAgentHeader + HTTP.CRLF

def copyBody(sink):
	while True:
		data = yield None
		sink.send(data)


def recvRegExp(regexp):
	fragment = yield None
	match = regexp.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		match = regexp.match(fragment)
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, match.groupdict(), restData
	else:
		yield RETURN, match.groupdict()


def recvBytes(bytes, sink):
	sentBytes = 0
	while sentBytes < bytes:
		fragment = yield None
		length = min(bytes - sentBytes, len(fragment))
		sink.send(buffer(fragment, 0, length))
		sentBytes += length
	fragment = buffer(fragment, length)
	if len(fragment) > 0:
		yield RETURN, None, fragment
	else:
		yield RETURN, None


def recvBody(response, sink):
	sink.next()
	try:
		if hasattr(response.headers, 'TransferEncoding'):
			if response.headers.TransferEncoding != 'chunked':
				raise WlHttpException('Transfer-Encoding: %s not supported' % response.headers.TransferEncoding)
			chunkHeader = yield recvRegExp(REGEXP.CHUNK_SIZE_LINE)
			size = int(chunkHeader['ChunkSize'], 16)
			while size > 0:
				yield recvBytes(size, sink)
				yield recvRegExp(REGEXP.CRLF)
				chunkHeader = yield recvRegExp(REGEXP.CHUNK_SIZE_LINE)
				size = int(chunkHeader['ChunkSize'], 16)
			yield recvRegExp(REGEXP.CRLF)
		elif hasattr(response.headers, 'ContentLength'):
			yield recvBytes(int(response.headers.ContentLength), sink)
		else:
			yield copyBody(sink) # connection close terminates body (HTTP 1.0)
	except Exception, e:
		sink.throw(e)

def _recvRegexp(regexp, message=None):
	fragment = ''
	message = message or WlDict()
	try:
		fragment = yield None
		match = regexp.match(fragment)
		while not match:
			if len(fragment) > MAX_REQUESTLENGTH:
				raise WlHttpException('Maximum request length exceeded but no sensible headers found.')
			fragment = fragment + (yield None)
			match = regexp.match(fragment)
	except GeneratorExit:
		raise WlHttpException('Connection closed but no sensible headers found. Response was: \n' + fragment)
	message.__dict__.update(match.groupdict())
	message.headers = WlDict()
	for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(message._headers):
		message.headers.__dict__[fieldname.title().replace('-','')] = fieldvalue.strip()
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, message, restData
	else:
		yield RETURN, message


recvRequest = curry(_recvRegexp, REGEXP.REQUEST)
recvResponse = curry(_recvRegexp, REGEXP.RESPONSE)
