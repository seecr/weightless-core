from re import compile

#Status-Line = HTTP-Version SP Status-Code SP Reason-Phrase CRLF
HTTP_Version = r'HTTP/(?P<version>\d\.\d)'
Status_Code = r'(?P<statuscode>[0-9]{3})'
Reason_Phrase = r'(?P<reasonphrase>[^\r\n].+)'
SP = ' '
CRLF = '\r\n'
Status_Line = HTTP_Version + SP + Status_Code + SP + Reason_Phrase + CRLF 

Status_LineRE = compile(Status_Line)

def WlHttpResponse(args):
	statusLine = yield None
	match = Status_LineRE.match(statusLine)
	if match:
		args.StatusCode = match.groupdict()['statuscode']
		args.HTTPVersion = match.groupdict()['version']
		args.ReasonPhrase = match.groupdict()['reasonphrase']
	yield None