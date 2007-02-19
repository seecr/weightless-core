

def wlTee(generatorList):
	gens = list(generatorList)
	response = ''.join(generator.next() for generator in gens)
	while gens:
		try:
			message = yield response
		except Exception, e:
			message = e
		responses = []
		for generator in gens[:]:
			try:
				send = generator.throw if isinstance(message, Exception) else generator.send
				responses.append(send(message))
			except:
				gens.remove(generator)
		response = ''.join(responses)

