from unittest import TestCase
from sys import stderr

from weightless.wlhttp import recvResponse, recvBody, HTTP, WlHttpException
from weightless.wlcompose import compose, RETURN
from weightless.wldict import WlDict

CRLF = HTTP.CRLF
#http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6
#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF

class WlHttpResponseTest(TestCase):

	def setUp(self):
		self.exception = None

	def testCreate(self):
		message = {}
		response = recvResponse(message)
		r = response.next()
		self.assertEquals(None, r)
		try: response.close()
		except: pass

	def testParseHeaderLines(self):
		generator = recvResponse()
		generator.next()
		generator.send('HTTP/1.1 302 Redirect\r\n')
		generator.send('lOcatiOn: http:///www.somewhere.else\r\n')
		generator.send('Date: Fri, 08 Dec 2006 13:55:48 GMT\r\n')
		generator.send('ConteNT-TyPE: text/plain\r\n')
		response = generator.send('\r\n')[1]

		self.assertEquals('Fri, 08 Dec 2006 13:55:48 GMT', response.headers.Date)
		self.assertEquals('http:///www.somewhere.else', response.headers.Location)
		self.assertEquals('text/plain', response.headers.ContentType)

	def testParseOkStatusLine(self):
		message = WlDict()
		response = recvResponse(message)
		response.next()
		response.send('HTTP/1.1 200 Ok\r\n')
		response.send('\r\n')
		self.assertEquals('200', message.StatusCode)
		self.assertEquals('1.1', message.HTTPVersion)
		self.assertEquals('Ok', message.ReasonPhrase)

	def testReturnValueAndRemainingData(self):
		message = WlDict()
		response = recvResponse(message)
		response.next()
		retval = response.send('HTTP/1.0 503 Kannie effe nie\r\n\r\ntrailing data, e.g. body')
		self.assertEquals((RETURN, message, 'trailing data, e.g. body'), (retval[0], retval[1], str(retval[2])))

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
		try:
			g.send('HTTP/1.0 503 Kannie effe nie\r\n\r\nthis is ze body')
			self.fail()
		except StopIteration:
			pass
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
		message = WlDict()
		generator = recvResponse(message)
		generator.next()
		generator.send('HTTP/1.0 503 Sorry not now\r\n')
		generator.send('\r\n')
		self.assertEquals('503', message.StatusCode)
		self.assertEquals('1.0', message.HTTPVersion)
		self.assertEquals('Sorry not now', message.ReasonPhrase)



	def _createResponse(self):
		response = WlDict()
		response.headers = WlDict()
		return response

	def testReadBodyImplicitIdentity(self):
		response = self._createResponse()
		data = []
		def sink():
			data.append((yield None))
			data.append((yield None))
			data.append((yield None))
		generator = compose(recvBody(response, sink()))
		generator.next() # init
		generator.send('part 1')
		generator.send('part 2')
		self.assertEquals(2, len(data))
		self.assertEquals('part 1', data[0])
		self.assertEquals('part 2', data[1])

	def testReadEmptyBodyWithChunkedEncoding(self):
		generator, data = self._prepareChunkedGenerator()
		try:
			generator.send('0' + CRLF + CRLF)
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(0, len(data))

	def testSimplestThing(self):
		generator, data = self._prepareChunkedGenerator()
		try:
			generator.send('A' + CRLF + 'abcdefghij' + CRLF + '0' + CRLF + CRLF)
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(1, len(data))
		self.assertEquals('abcdefghij', str(data[0]))
		generator.close()

	def testCloseCatchesStopIterationAndGeneratorExitButNotOtherExceptions(self):
		def f():
			yield None
		g = f()
		g.next()
		g.close()
		def f():
			try: yield None
			except: raise StopIteration()
		g = f()
		g.next()
		g.close()
		def f():
			try: yield None
			except: raise Exception('X')
		g = f()
		g.next()
		try: g.close()
		except Exception, e: self.assertEquals('X', str(e))

	def testPrematureCloseDoesNotMaskException(self):
		generator, data = self._prepareChunkedGenerator()
		self.exception = WlHttpException('No good')
		try:
			generator.close()
			self.fail()
		except WlHttpException, e: # some sort of error, depending on the implementation
			self.assertEquals(self.exception, e)

	def testReadBodyWithChunkedEncoding(self):
		generator, data = self._prepareChunkedGenerator()
		generator.send('A' + CRLF + 'abcdefghij' + CRLF)
		try:
			generator.send('0' + CRLF + CRLF)
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(1, len(data))
		self.assertEquals('abcdefghij', str(data[0]))

	def testReadBodyWithMultipleChunksEncoding(self):
		generator, data = self._prepareChunkedGenerator()
		generator.send('A' + CRLF + 'abcdefghij' + CRLF)
		generator.send('B' + CRLF + 'bcdefghijkl' + CRLF)
		self.assertEquals('abcdefghij', str(data[0]))
		generator.send('0' + CRLF) # last chunked
		try:
			generator.send(CRLF) # no trailer, end of chunked body
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(2, len(data), ''.join(str(data)))
		self.assertEquals('bcdefghijkl', str(data[1]))

	def testReadBodyWithMultipleSplitUpChunks(self):
		generator, data = self._prepareChunkedGenerator()
		generator.send('5')
		generator.send(CRLF)
		generator.send('ABCD')
		generator.send('E' + CRLF)
		generator.send('0')
		generator.send(CRLF)
		try:
			generator.send(CRLF)
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(2, len(data))
		self.assertEquals('ABCD', str(data[0]))
		self.assertEquals('E', str(data[1]))

	def testReadBodyWithMultipleChunksEncoding2(self):
		generator, data = self._prepareChunkedGenerator()
		generator.send('A' + CRLF + 'abcdefg')
		generator.send('hij' + CRLF+ 'B' + CRLF)
		generator.send('bcdefghijkl' + '\r')
		generator.send('\n0' + CRLF) # last chunk
		try:
			generator.send(CRLF) # end of body
			self.fail()
		except StopIteration:
			pass
		self.assertEquals(3, len(data), [str(d) for d in data])

	def testTerminate(self):
		generator = recvBody(None, (x for x in []))
		try:
  			generator.next()
			self.fail()
		except StopIteration:
			pass

		generator = compose(recvBody(WlDict({'headers': {}}), (None for x in range(99))))
		generator.next()
		generator.send('the body')
		generator.close() # terminate body

	def _prepareChunkedGenerator(self):
		response = self._createResponse()
		response.headers.TransferEncoding = 'chunked'
		data = []
		def sink():
			while True:
				try:
					appendThis = yield None
				except GeneratorExit:
					if self.exception:
						raise self.exception
					raise
				data.append(appendThis)
		generator = compose(recvBody(response, sink()))
		generator.next() # init
		return generator, data

	def testReadContentLength(self):
		testData = 'this string is xx bytes long'
		args = self._createResponse()
		args.headers.ContentLength = len(testData)
		data = []
		def sink():
			while True: data.append((yield None))
		g = compose(recvBody(args, sink()))
		g.next()
		try:
			g.send(testData)
			self.fail()
		except StopIteration:
			pass
		self.assertEquals('this string is xx bytes long', str(data[0]))

		data = []
		g = compose(recvBody(args, sink()))
		g.next()
		g.send(testData[:1])
		g.send(testData[1:-1])
		try:
			g.send(testData[-1])
			self.fail()
		except StopIteration:
			pass
		self.assertEquals('this string is xx bytes long', ''.join(str(d) for d in data))


