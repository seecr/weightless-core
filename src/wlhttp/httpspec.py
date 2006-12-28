from re import compile

"""
	HTTP specifications.
	http://www.w3.org/Protocols/rfc2616/rfc2616.html
"""

class HTTP:
	SP = ' '
	CRLF = '\r\n'
	
	Method = r'GET'
	Request_URI = r'(?P<RequestURI>.+)'
	HTTP_Version = r'HTTP/(?P<HTTPVersion>\d\.\d)'
	token =  """([!#$%&'*+-./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~]+){1}"""
	field_name = token
	field_value = '.*'
	message_header = field_name + ":" + field_value + CRLF
	Request_Line   = Method + SP + Request_URI + SP + HTTP_Version + CRLF
	Request = Request_Line + "(?P<headers>(" + message_header + ')*)' + CRLF
	Status_Code = r'(?P<StatusCode>[0-9]{3})'
	Reason_Phrase = r'(?P<ReasonPhrase>[^\r\n].+)'
	Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

	Response = Status_Line + "(?P<headers>(" + message_header + ')*)' + CRLF
	named_message_header = '(?P<fieldname>'+field_name+'):(?P<fieldvalue>'+field_value+")" + CRLF


class REGEXP:
	RESPONSE = compile(HTTP.Response)
	REQUEST = compile(HTTP.Request)
	HEADER = compile(HTTP.named_message_header)

class FORMAT:
	RequestLine = '%(Method)s %(Path)s HTTP/1.1' + HTTP.CRLF
	HostHeader = 'Host: %(Host)s' + HTTP.CRLF
	UserAgentHeader = 'User-Agent: Weightless/0.1' + HTTP.CRLF

