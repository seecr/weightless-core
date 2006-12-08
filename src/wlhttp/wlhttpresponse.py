
def WlHttpResponse(args):
	statusLine = yield None
	args.StatusCode = '200'
	args.HTTPVersion = '1.1'
	args.ReasonPhrase = 'Ok'
	yield None