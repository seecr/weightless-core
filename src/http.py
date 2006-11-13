
CRLF = '\r\n'

class HTTP:
	class Response:
		StatusLine = 'HTTP/%(version)s %(status)s %(reason)s' + CRLF
	class Message:
		MessageHeader = '%(name)s: %(value)s' + CRLF
		def _Headers(klas, headers = {}):
			for name, value in headers.items():
				yield HTTP.Message.MessageHeader % locals()
			yield CRLF
		Headers = classmethod(_Headers)
