from unittest import TestCase

from weightless.wlhttp import parseHTTPResponse
from weightless.wlgenerator import WlGenerator, RETURN
from weightless.wldict import WlDict

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6
#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF

class WlHttpResponseTest(TestCase):

	def testCreate(self):
		args = {}
		response = parseHTTPResponse(args)
		r = response.next()
		self.assertEquals(None, r)

	def testParseOkStatusLine(self):
		args = WlDict()
		response = parseHTTPResponse(args)
		response.next()
		response.send('HTTP/1.1 200 Ok\r\n')
		response.send('\r\n')
		self.assertEquals('200', args.StatusCode)
		self.assertEquals('1.1', args.HTTPVersion)
		self.assertEquals('Ok', args.ReasonPhrase)

	def testReturnValueAndRemainingData(self):
		args = WlDict()
		response = parseHTTPResponse(args)
		response.next()
		retval = response.send('HTTP/1.0 503 Kannie effe nie\r\n\r\ntrailing data, e.g. body')
		self.assertEquals((RETURN, args, 'trailing data, e.g. body'), retval)

	def testAsItIsMeantToBeUsedInRealApplications(self):
		def handler():
			requestData = yield parseHTTPResponse()
			self.assertEquals('503', requestData.StatusCode)
			body = yield None
			self.assertEquals('this is ze body', body)
		g = WlGenerator(handler())
		g.next()
		g.send('HTTP/1.0 503 Kannie effe nie\r\n\r\nthis is ze body')

	def testDoNotShareArgs(self):
		w1 = parseHTTPResponse()
		w2 = parseHTTPResponse()
		w1.next()
		w2.next()
		r1 = w1.send('HTTP/1.0 200 Ok\r\n\r\n')[1]
		r2 = w2.send('HTTP/1.1 300 Ko\r\n\r\n')[1]
		self.assertEquals('200', r1.StatusCode)
		self.assertEquals('300', r2.StatusCode)

	def testParseOtherStatusLine(self):
		args = WlDict()
		response = parseHTTPResponse(args)
		response.next()
		response.send('HTTP/1.0 503 Kannie effe nie\r\n')
		response.send('\r\n')
		self.assertEquals('503', args.StatusCode)
		self.assertEquals('1.0', args.HTTPVersion)
		self.assertEquals('Kannie effe nie', args.ReasonPhrase)

	def testParseHeaderLines(self):
		args = WlDict()
		response = parseHTTPResponse(args)
		response.next()
		response.send('HTTP/1.1 302 Redirect\r\n')
		response.send('lOcatiOn: http:///www.somewhere.else\r\n')
		response.send('Date: Fri, 08 Dec 2006 13:55:48 GMT\r\n')
		response.send('\r\n')

		# directly into the WLDict or make the WLDict have a 'headers'-WLDict ?
		self.assertEquals('Fri, 08 Dec 2006 13:55:48 GMT', args.Date)
		self.assertEquals('http:///www.somewhere.else', args.Location)
