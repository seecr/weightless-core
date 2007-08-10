from types import GeneratorType

builtins = {'__builtins__': {
	'str': str,
	'range': range,
	'max': max,
	'min': min
	}
}

def Template(template, symbols = {}, cache = {}):
	if template in cache:
		compiledlines, lastline = cache[template]
	else:
		lines = template.split('%>')
		lastline = lines[-1]
		compiledlines = []
		for line in lines[:-1]:
			text, expression = line.split('<%')
			if expression.startswith('='):
				symbol = None
				code = compile(expression[1:], '<template>', 'eval')
			else:
				symbol, expression = expression.split('=', 2)
				code = compile(expression, '<template>', 'eval')
			compiledlines.append((text, code, symbol))
		cache[template] = compiledlines, lastline

	for text, code, symbol in compiledlines:
		yield text
		if symbol: # then is is an assigment: <%symbol=<expression>%>
			symbols[symbol] = eval(code, builtins, symbols)
		else:
			result = eval(code, builtins, symbols)
			if type(result) != GeneratorType:  # I don't like this magic, it works only on one level
				result = str(result)
			yield result
	yield lastline