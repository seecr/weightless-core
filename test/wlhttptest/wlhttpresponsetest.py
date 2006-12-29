from unittest import TestCase

from weightless.wlhttp import recvResponse
from weightless.wlcompose import compose, RETURN
from weightless.wldict import WlDict

#http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6
#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF

class WlHttpResponseTest(TestCase):

	def testCreate(self):
		parameters = {}
		response = recvResponse(parameters)
		r = response.next()
		self.assertEquals(None, r)

	def testParseOkStatusLine(self):
		parameters = WlDict()
		response = recvResponse(parameters)
		response.next()
		response.send('HTTP/1.1 200 Ok\r\n')
		response.send('\r\n')
		self.assertEquals('200', parameters.StatusCode)
		self.assertEquals('1.1', parameters.HTTPVersion)
		self.assertEquals('Ok', parameters.ReasonPhrase)

	def testReturnValueAndRemainingData(self):
		parameters = WlDict()
		response = recvResponse(parameters)
		response.next()
		retval = response.send('HTTP/1.0 503 Kannie effe nie\r\n\r\ntrailing data, e.g. body')
		self.assertEquals((RETURN, parameters, 'trailing data, e.g. body'), (retval[0], retval[1], str(retval[2])))

	def testRestDataIsBufferInsteadOfCopiedString(self):
		response = recvResponse()
		response.next()
		retval = response.send('HTTP/1.0 200 Ok\r\n\r\nthis must not be copied but in a buffer')
		self.assertEquals(buffer, type(retval[2]))
		self.assertEquals('this must not be copied but in a buffer', str(retval[2]))

	def testAsItIsMeantToBeUsedInRealApplications(self):
		done = [0]
		def handler():
			requestData = yield recvResponse()
			self.assertEquals('503', requestData.StatusCode)
			body = yield None
			self.assertEquals('this is ze body', str(body))
			done[0] = 1
		g = compose(handler())
		g.next()
		g.send('HTTP/1.0 503 Kannie effe nie\r\n\r\nthis is ze body')
		list(g)
		self.assertTrue(done[0])

	def testReAcceptsBuffer(self):
		from re import compile
		r = compile('.*(?P<name>[123]{3}).*')
		match = r.match(buffer('pqrabc123xyzklm', 3, 9))
		self.assertEquals('123', match.groupdict()['name'])

	def testDoNotShareArgs(self):
		w1 = recvResponse()
		w2 = recvResponse()
		w1.next()
		w2.next()
		r1 = w1.send('HTTP/1.0 200 Ok\r\n\r\n')[1]
		r2 = w2.send('HTTP/1.1 300 Ko\r\n\r\n')[1]
		self.assertEquals('200', r1.StatusCode)
		self.assertEquals('300', r2.StatusCode)

	def testParseOtherStatusLine(self):
		parameters = WlDict()
		generator = recvResponse(parameters)
		generator.next()
		generator.send('HTTP/1.0 503 Sorry not now\r\n')
		generator.send('\r\n')
		self.assertEquals('503', parameters.StatusCode)
		self.assertEquals('1.0', parameters.HTTPVersion)
		self.assertEquals('Sorry not now', parameters.ReasonPhrase)

	def testParseHeaderLines(self):
		generator = recvResponse()
		generator.next()
		generator.send('HTTP/1.1 302 Redirect\r\n')
		generator.send('lOcatiOn: http:///www.somewhere.else\r\n')
		generator.send('Date: Fri, 08 Dec 2006 13:55:48 GMT\r\n')
		response = generator.send('\r\n')[1]

		self.assertEquals('Fri, 08 Dec 2006 13:55:48 GMT', response.headers.Date)
		self.assertEquals('http:///www.somewhere.else', response.headers.Location)
