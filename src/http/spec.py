from re import compile

"""
	HTTP specifications.
	http://www.w3.org/Protocols/rfc2616/rfc2616.html
"""

def parseHeaders(headerString):
    headers = {}
    for (groupname, fieldname, fieldvalue) in REGEXP.HEADER.findall(headerString):
        headers[fieldname.title()] = fieldvalue.strip()
    return headers


class HTTP:
    #class Response:
        #StatusLine = 'HTTP/%(version)s %(status)s %(reason)s' + CRLF
    #class Message:
        #MessageHeader = '%(name)s: %(value)s' + CRLF
        #def _Headers(klas, headers = {}):
            #for name, value in headers.items():
                #yield HTTP.Message.MessageHeader % locals()
            #yield CRLF
        #Headers = classmethod(_Headers)

	SP = ' '
	CRLF = '\r\n'
	# http://www.w3.org/Protocols/rfc2616/rfc2616-sec2.html#sec2.2
	token =  r"([!#$%&'*+\-.0-9A-Z^_`a-z|~]+){1}"
	field_name = token
	field_value = '.*'
	named_field_name = '(?P<fieldname>' + field_name + ')'
	named_field_value = '(?P<fieldvalue>' + field_value + ")"

	message_header = field_name + ":" + field_value + CRLF
	named_message_header = named_field_name + ':' + named_field_value + CRLF

	Headers = "(?P<_headers>(" + message_header + ')*)'

	Method = r'(?P<Method>' + token + ')'
	Request_URI = r'(?P<RequestURI>.+)'
	HTTP_Version = r'HTTP/(?P<HTTPVersion>\d\.\d)'
	ignoredCRLFs = '(' + CRLF + ')*'
	Request_Line = ignoredCRLFs + Method + SP + Request_URI + SP + HTTP_Version + CRLF

	Chunk_Size = '(?P<ChunkSize>[0-9a-fA-F]+)'
	Chunk_Size_Line = Chunk_Size + CRLF

	Status_Code = r'(?P<StatusCode>[0-9]{3})'
	Reason_Phrase = r'(?P<ReasonPhrase>[^\r\n].+)'
	Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

	Request = Request_Line + Headers + CRLF
	Response = Status_Line + Headers + CRLF



class REGEXP:
	RESPONSE = compile(HTTP.Response)
	REQUEST = compile(HTTP.Request)
	REQUESTLINE = compile(HTTP.Request_Line)
	HEADER = compile(HTTP.named_message_header)
	CHUNK_SIZE_LINE = compile(HTTP.Chunk_Size_Line)
	CRLF = compile(HTTP.CRLF)

class FORMAT:
	RequestLine = '%(Method)s %(Request_URI)s HTTP/1.0' + HTTP.CRLF
	HostHeader = 'Host: %(Host)s' + HTTP.CRLF
	UserAgentHeader = 'User-Agent: Weightless/v1.9' + HTTP.CRLF

