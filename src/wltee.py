

def wlTee(*generatorList):
	gens = list(generatorList)
	response = ''.join(generator.next() for generator in gens)
	while gens:
		data = yield response
		responses = []
		for generator in gens[:]:
			try:
				responses.append(generator.send(data))
			except StopIteration:
				gens.remove(generator)
		response = ''.join(responses)

