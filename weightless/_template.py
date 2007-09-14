## begin license ##
#
#    Weightless is a High Performance Asynchronous Networking Library
#    Copyright (C) 2006-2007 Seek You Too B.V. (CQ2) http://www.cq2.nl
#
#    This file is part of Weightless
#
#    Weightless is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    Weightless is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Weightless; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
## end license ##
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
