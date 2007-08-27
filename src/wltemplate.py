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
				code = compile(expression[1:].strip(), '<template>', 'eval')
			else:
				code = compile(expression.strip(), '<template>', 'exec')
			compiledlines.append((text, code))
		cache[template] = compiledlines, lastline

	for text, code in compiledlines:
		yield text
		result = eval(code, builtins, symbols)
		if result:
			yield result
	yield lastline