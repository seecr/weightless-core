from unittest import TestCase

from weightless.wlhttp import WlHttpResponse

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6
#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF

class WlDict:
	pass

class WlHttpResponseTest(TestCase):

	def testCreate(self):
		args = {}
		response = WlHttpResponse(args)
		r = response.next()
		self.assertEquals(None, r)

	def testParseOkStatusLine(self):
		args = WlDict()
		response = WlHttpResponse(args)
		response.next()
		response.send('HTTP/1.1 200 Ok\r\n')
		response.send('\r\n')
		self.assertEquals('200', args.StatusCode)
		self.assertEquals('1.1', args.HTTPVersion)
		self.assertEquals('Ok', args.ReasonPhrase)

	def testParseOtherStatusLine(self):
		args = WlDict()
		response = WlHttpResponse(args)
		response.next()
		response.send('HTTP/1.0 503 Kannie effe nie\r\n')
		response.send('\r\n')
		self.assertEquals('503', args.StatusCode)
		self.assertEquals('1.0', args.HTTPVersion)
		self.assertEquals('Kannie effe nie', args.ReasonPhrase)
		
	def testParseHeaderLines(self):
		args = WlDict()
		response = WlHttpResponse(args)
		response.next()
		response.send('HTTP/1.1 302 Redirect\r\n')
		response.send('lOcatiOn: http:///www.somewhere.else\r\n')
		response.send('Date: Fri, 08 Dec 2006 13:55:48 GMT\r\n')
		response.send('\r\n')
		
		# directly into the WLDict or make the WLDict have a 'headers'-WLDict ?
		self.assertEquals('Fri, 08 Dec 2006 13:55:48 GMT', args.Date)
		self.assertEquals('http:///www.somewhere.else', args.Location)
