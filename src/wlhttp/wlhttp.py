

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

def copyBody(sink):
	while True:
		data = yield None
		sink.send(data)

def recvRegExp(regexp):
	fragment = yield None
	print 'recvRegExp >>>>>>>>>>>>>>>>', repr(fragment), '<<<<<<'
	match = regexp.match(fragment)
	while not match:
		fragment = fragment + (yield None)
		print 'recvRegExp 2 >>>>>>>>>>>>>>>>', repr(fragment), '<<<<<<'
		match = REGEXP.CHUNK_SIZE_LINE.match(fragment)
	if match.end() < len(fragment):
		restData = buffer(fragment, match.end())
		yield RETURN, match.groupdict(), restData
	else:
		yield RETURN, match.groupdict()
	
def recvBytes(bytes, sink):
	sentBytes = 0
	while sentBytes < bytes:
		fragment = yield None
		print 'recvBytes 2 >>>>>>>>>>>>>>>>', repr(fragment), '<<<<<<'
		length = min(bytes - sentBytes, len(fragment))
		sink.send(buffer(fragment, 0, length))
		sentBytes += length
	fragment = buffer(fragment, length)
	print '=== restje:', fragment
	if len(fragment) > 0:
		yield RETURN, None, fragment
	else:
		yield RETURN, None
			

def recvBody(response, sink):
	sink.next()
	encoding = getattr(response.headers, 'TransferEncoding', '')
	if encoding == '':
		yield copyBody(sink)
	elif encoding == 'chunked':
		
		chunkHeader = yield recvRegExp(REGEXP.CHUNK_SIZE_LINE)
		size = int(chunkHeader['ChunkSize'], 16)
		while size > 0:

			r = yield recvBytes(size, sink)		
			print '1----', r
			r = yield recvRegExp(REGEXP.CRLF)
			print '2----'	, r

			chunkHeader = yield recvRegExp(REGEXP.CHUNK_SIZE_LINE)
			print '3----', chunkHeader
			size = int(chunkHeader['ChunkSize'], 16)
		
		yield recvRegExp(REGEXP.CRLF)
	else:
		raise WlHttpException('Transfer-Encoding: %s not supported' % encoding)

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
