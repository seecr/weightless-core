from re import compile
from weightless.wlgenerator import RETURN
from weightless import WlDict

#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF
HTTP_Version = r'HTTP/(?P<HTTPVersion>\d\.\d)'
Status_Code = r'(?P<StatusCode>[0-9]{3})'
Reason_Phrase = r'(?P<ReasonPhrase>[^\r\n].+)'
SP = ' '
CRLF = '\r\n'
Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF

token =  """([!#$%&'*+-./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~]+){1}"""
field_name = token
field_value =  '.*'
message_header = field_name + ":" + field_value + CRLF
Response = Status_Line + "(?P<headers>(" + message_header + ')*)' + CRLF
HTTP_RESPONSE = compile(Response)

named_message_header = '(?P<fieldname>'+field_name+'):(?P<fieldvalue>'+field_value+")" + CRLF
named_message_headerRE = compile(named_message_header)

def parseHTTPResponse(args = None):
	args = args or WlDict()
	data = ''
	match = None
	while not match:
		data = data + (yield None)
		match = HTTP_RESPONSE.match(data)
	end = match.end()
	restData = data[end:]
	args.__dict__.update(match.groupdict())
	for (groupname, fieldname, fieldvalue) in named_message_headerRE.findall(args.headers):
		args.__dict__[fieldname.capitalize()] = fieldvalue.strip()
	yield RETURN, args, restData