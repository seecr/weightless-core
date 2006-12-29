from re import compile

"""
	HTTP specifications.
	http://www.w3.org/Protocols/rfc2616/rfc2616.html
"""

class HTTP:
	SP = ' '
	CRLF = '\r\n'
	
	token =  """([!#$%&'*+-./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~]+){1}"""
	field_name = token
	field_value = '.*'
	named_field_name = '(?P<fieldname>' + field_name + ')'
	named_field_value = '(?P<fieldvalue>' + field_value + ")"
	
	message_header = field_name + ":" + field_value + CRLF
	named_message_header = named_field_name + ':' + named_field_value + CRLF
	
	Headers = "(?P<_headers>(" + message_header + ')*)'
	
	Method = r'(?P<Method>GET)'
	Request_URI = r'(?P<RequestURI>.+)'
	HTTP_Version = r'HTTP/(?P<HTTPVersion>\d\.\d)'
	Request_Line   = Method + SP + Request_URI + SP + HTTP_Version + CRLF
	
	Status_Code = r'(?P<StatusCode>[0-9]{3})'
	Reason_Phrase = r'(?P<ReasonPhrase>[^\r\n].+)'
	Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

	Request = Request_Line + Headers + CRLF
	Response = Status_Line + Headers + CRLF
	


class REGEXP:
	RESPONSE = compile(HTTP.Response)
	REQUEST = compile(HTTP.Request)
	HEADER = compile(HTTP.named_message_header)

class FORMAT:
	RequestLine = '%(Method)s %(Path)s HTTP/1.1' + HTTP.CRLF
	HostHeader = 'Host: %(Host)s' + HTTP.CRLF
	UserAgentHeader = 'User-Agent: Weightless/0.1' + HTTP.CRLF

