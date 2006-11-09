from unittest import TestCase
from wlhttp import WlHttp

"""
       Response      = Status-Line               ; Section 6.1
                       *(( general-header        ; Section 4.5
                        | response-header        ; Section 6.2
                        | entity-header ) CRLF)  ; Section 7.1
                       CRLF
                       [ message-body ]          ; Section 7.2
"""



class WlHttpTest(TestCase):

	def testA(self):
		g = WlHttp((x for x in [''] * 10))
		x = g.next()
		self.assertFalse(x)
		x = g.send('GET /path/file1 HTTP/1.0\r\n')
		#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF
		self.assertEquals('HTTP/1.0 200 OK\r\n/path/file1', x)

	def testB(self):
		g = WlHttp((x for x in [''] * 10))
		x = g.next()
		x = g.send('GET /path/file2 HTTP/1.0\r\n')
		self.assertEquals('HTTP/1.0 200 OK\r\n/path/file2', x)

	def testC(self):
		g = WlHttp((x for x in [''] * 10))
		x = g.next()
		x = g.send('GET /path/file2 ')
		self.assertFalse(x)
		x = g.send('HTTP/1.1\r\n')
		self.assertEquals('HTTP/1.1 200 OK\r\n/path/file2', x)

	def testD(self):
		def Handler():
			request = yield None
			yield request.path
		g = WlHttp(Handler())
		x = g.next()
		x = g.send('GET /method HTTP/1.1\r\n')
		self.assertEquals('HTTP/1.1 200 OK\r\n/method', x)