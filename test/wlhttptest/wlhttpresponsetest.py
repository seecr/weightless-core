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
		self.assertEquals('200', args.StatusCode)
		self.assertEquals('1.1', args.HTTPVersion)
		self.assertEquals('Ok', args.ReasonPhrase)

	def testParseOtherStatusLine(self):
		args = WlDict()
		response = WlHttpResponse(args)
		response.next()
		response.send('HTTP/1.0 503 Kannie effe nie\r\n')
		self.assertEquals('503', args.StatusCode)
		self.assertEquals('1.0', args.HTTPVersion)
		self.assertEquals('Kannie effe nie', args.ReasonPhrase)
